from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from pm2.infrastructure.database import Database
from pm2.infrastructure.orm import ProjectModel
from pm2.methodology import MethodologyLoader, methodology_sha256
from pm2.methodology.loader import MethodologyLoadError


class ArchiveError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ProjectArchiveService:
    FORMAT_VERSION = "1.1"
    METHODOLOGY_PATH = "methodology/PM2_METHODOLOGY.yaml"

    def __init__(self, database: Database, session: Session) -> None:
        self.database = database
        self.session = session

    def save(
        self,
        project_id: str,
        destination: Path,
        *,
        documents_dir: Path | None = None,
        attachments_dir: Path | None = None,
        exports_dir: Path | None = None,
    ) -> Path:
        project = self.session.get(ProjectModel, project_id)
        if project is None:
            raise LookupError(f"Projet introuvable : {project_id}")
        if self.database.path is None:
            raise ArchiveError("Une base en mémoire ne peut pas être archivée.")
        if not project.methodology_snapshot or not project.methodology_hash:
            raise ArchiveError(
                "Le projet ne possède pas de snapshot méthodologique et ne peut pas être archivé."
            )
        if methodology_sha256(project.methodology_snapshot) != project.methodology_hash:
            raise ArchiveError("Le snapshot méthodologique du projet a une empreinte invalide.")
        try:
            snapshot_configuration = MethodologyLoader.load_text(
                project.methodology_snapshot, source=f"projet {project.reference}"
            )
        except MethodologyLoadError as exc:
            raise ArchiveError("Le snapshot méthodologique du projet est invalide.") from exc
        if (
            snapshot_configuration.methodology.id != project.methodology_id
            or snapshot_configuration.methodology.version != project.methodology_version
        ):
            raise ArchiveError(
                "Le snapshot méthodologique ne correspond pas à l’identité du projet."
            )
        destination = destination.with_suffix(".pm2")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.session.commit()
        with self.database.engine.connect() as connection:
            connection.execute(text("PRAGMA wal_checkpoint(FULL)"))
        with tempfile.TemporaryDirectory(prefix="pm2-archive-") as temp_name:
            temp = Path(temp_name)
            database_copy = temp / "project.db"
            shutil.copy2(self.database.path, database_copy)
            manifest = {
                "format": "pm2-desktop-project",
                "format_version": self.FORMAT_VERSION,
                "project_id": project.id,
                "project_reference": project.reference,
                "methodology": project.methodology_id,
                "methodology_version": project.methodology_version,
                "methodology_hash": project.methodology_hash,
                "methodology_snapshot": self.METHODOLOGY_PATH,
                "saved_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "database_sha256": sha256_file(database_copy),
            }
            (temp / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
            )
            methodology_target = temp / self.METHODOLOGY_PATH
            methodology_target.parent.mkdir()
            methodology_target.write_text(project.methodology_snapshot, encoding="utf-8")
            for name, source in (
                ("documents", documents_dir),
                ("attachments", attachments_dir),
                ("exports", exports_dir),
            ):
                target = temp / name
                target.mkdir()
                if source and source.exists():
                    for path in source.rglob("*"):
                        if path.is_file():
                            relative = path.relative_to(source)
                            (target / relative).parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(path, target / relative)
            temporary_archive = temp / "project.pm2"
            with zipfile.ZipFile(temporary_archive, "w", zipfile.ZIP_DEFLATED) as archive:
                for directory in ("methodology/", "documents/", "attachments/", "exports/"):
                    archive.writestr(directory, b"")
                for path in sorted(temp.rglob("*")):
                    if path.is_file() and path != temporary_archive:
                        archive.write(path, path.relative_to(temp).as_posix())
            shutil.copy2(temporary_archive, destination)
        return destination

    @classmethod
    def open(
        cls, archive_path: Path, database_destination: Path, *, overwrite: bool = False
    ) -> dict[str, object]:
        if database_destination.exists() and not overwrite:
            raise ArchiveError(f"La destination existe déjà : {database_destination}")
        try:
            with (
                zipfile.ZipFile(archive_path, "r") as archive,
                tempfile.TemporaryDirectory(prefix="pm2-open-") as temp_name,
            ):
                names = archive.namelist()
                if "manifest.json" not in names or "project.db" not in names:
                    raise ArchiveError("Archive invalide : manifest.json ou project.db absent.")
                for name in names:
                    path = PurePosixPath(name)
                    if path.is_absolute() or ".." in path.parts:
                        raise ArchiveError("Archive invalide : chemin non sûr détecté.")
                temp = Path(temp_name)
                archive.extractall(temp)
                try:
                    manifest = json.loads((temp / "manifest.json").read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as exc:
                    raise ArchiveError("Archive invalide : manifest illisible.") from exc
                if manifest.get("format") != "pm2-desktop-project":
                    raise ArchiveError("Archive invalide : format non reconnu.")
                snapshot: str | None = None
                snapshot_path = manifest.get("methodology_snapshot")
                if snapshot_path is not None:
                    if snapshot_path != cls.METHODOLOGY_PATH or snapshot_path not in names:
                        raise ArchiveError("Archive invalide : snapshot méthodologique absent.")
                    try:
                        snapshot = (temp / cls.METHODOLOGY_PATH).read_text(encoding="utf-8")
                    except (OSError, UnicodeError) as exc:
                        raise ArchiveError(
                            "Archive invalide : snapshot méthodologique illisible."
                        ) from exc
                    snapshot_hash = methodology_sha256(snapshot)
                    if snapshot_hash != manifest.get("methodology_hash"):
                        raise ArchiveError(
                            "Archive corrompue : empreinte de la méthodologie incorrecte."
                        )
                    configuration = MethodologyLoader.load_text(
                        snapshot, source=cls.METHODOLOGY_PATH
                    )
                    if configuration.methodology.id != manifest.get(
                        "methodology"
                    ) or configuration.methodology.version != manifest.get("methodology_version"):
                        raise ArchiveError(
                            "Archive invalide : identité méthodologique incohérente."
                        )
                elif manifest.get("format_version") != "1.0":
                    raise ArchiveError("Archive invalide : snapshot méthodologique obligatoire.")
                actual = sha256_file(temp / "project.db")
                if actual != manifest.get("database_sha256"):
                    raise ArchiveError("Archive corrompue : empreinte de la base incorrecte.")
                probe = Database(temp / "project.db")
                try:
                    probe.ensure_schema_compatibility()
                    with probe.session_factory() as session:
                        project = session.scalar(
                            select(ProjectModel).where(
                                ProjectModel.id == manifest.get("project_id")
                            )
                        )
                        if project is None:
                            raise ArchiveError("Archive invalide : projet absent de la base.")
                        if snapshot is not None and (
                            project.methodology_snapshot != snapshot
                            or project.methodology_hash != manifest.get("methodology_hash")
                            or project.methodology_id != manifest.get("methodology")
                            or project.methodology_version != manifest.get("methodology_version")
                        ):
                            raise ArchiveError(
                                "Archive invalide : méthodologie différente entre la base et le manifeste."
                            )
                finally:
                    probe.dispose()
                database_destination.parent.mkdir(parents=True, exist_ok=True)
                staging = database_destination.with_suffix(database_destination.suffix + ".opening")
                shutil.copy2(temp / "project.db", staging)
                staging.replace(database_destination)
                return manifest
        except zipfile.BadZipFile as exc:
            raise ArchiveError("Le fichier n'est pas une archive PM² valide.") from exc
        except MethodologyLoadError as exc:
            raise ArchiveError("Archive invalide : méthodologie illisible.") from exc
