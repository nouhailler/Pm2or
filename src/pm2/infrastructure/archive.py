from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from sqlalchemy import select
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
    FORMAT_VERSION = "1.2"
    SUPPORTED_FORMAT_VERSIONS = {"1.0", "1.1", FORMAT_VERSION}
    METHODOLOGY_PATH = "methodology/PM2_METHODOLOGY.yaml"
    MAX_ENTRIES = 2_000
    MAX_ENTRY_SIZE = 512 * 1024 * 1024
    MAX_UNCOMPRESSED_SIZE = 1024 * 1024 * 1024

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
        if self.session.new or self.session.dirty or self.session.deleted:
            raise ArchiveError(
                "Des modifications ne sont pas encore validées. Enregistrez-les avant l'export."
            )
        with tempfile.TemporaryDirectory(prefix="pm2-archive-") as temp_name:
            temp = Path(temp_name)
            database_copy = temp / "project.db"
            with (
                sqlite3.connect(self.database.path) as source_database,
                sqlite3.connect(database_copy) as target_database,
            ):
                source_database.backup(target_database)
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
            files = {
                path.relative_to(temp).as_posix(): {
                    "sha256": sha256_file(path),
                    "size": path.stat().st_size,
                }
                for path in sorted(temp.rglob("*"))
                if path.is_file()
            }
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
                "files": files,
            }
            (temp / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
            )
            temporary_archive = temp / "project.pm2"
            with zipfile.ZipFile(temporary_archive, "w", zipfile.ZIP_DEFLATED) as archive:
                for directory in ("methodology/", "documents/", "attachments/", "exports/"):
                    archive.writestr(directory, b"")
                for path in sorted(temp.rglob("*")):
                    if path.is_file() and path != temporary_archive:
                        archive.write(path, path.relative_to(temp).as_posix())
            staging = destination.with_suffix(destination.suffix + ".saving")
            shutil.copy2(temporary_archive, staging)
            staging.replace(destination)
        return destination

    @classmethod
    def open(
        cls,
        archive_path: Path,
        database_destination: Path,
        *,
        overwrite: bool = False,
        content_destination: Path | None = None,
    ) -> dict[str, object]:
        if database_destination.exists() and not overwrite:
            raise ArchiveError(f"La destination existe déjà : {database_destination}")
        try:
            with (
                zipfile.ZipFile(archive_path, "r") as archive,
                tempfile.TemporaryDirectory(prefix="pm2-open-") as temp_name,
            ):
                infos = archive.infolist()
                names = [info.filename for info in infos]
                if len(infos) > cls.MAX_ENTRIES:
                    raise ArchiveError("Archive invalide : trop de fichiers.")
                if len(names) != len(set(names)):
                    raise ArchiveError("Archive invalide : chemins dupliqués.")
                total_size = sum(info.file_size for info in infos)
                if total_size > cls.MAX_UNCOMPRESSED_SIZE:
                    raise ArchiveError("Archive invalide : contenu décompressé trop volumineux.")
                if "manifest.json" not in names or "project.db" not in names:
                    raise ArchiveError("Archive invalide : manifest.json ou project.db absent.")
                for info in infos:
                    name = info.filename
                    path = PurePosixPath(name)
                    if (
                        path.is_absolute()
                        or ".." in path.parts
                        or "\\" in name
                        or "\x00" in name
                        or info.file_size > cls.MAX_ENTRY_SIZE
                        or info.flag_bits & 0x1
                    ):
                        raise ArchiveError("Archive invalide : chemin non sûr détecté.")
                temp = Path(temp_name)
                for info in infos:
                    target = temp.joinpath(*PurePosixPath(info.filename).parts)
                    if info.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
                try:
                    loaded_manifest = json.loads(
                        (temp / "manifest.json").read_text(encoding="utf-8")
                    )
                except (json.JSONDecodeError, OSError) as exc:
                    raise ArchiveError("Archive invalide : manifest illisible.") from exc
                if not isinstance(loaded_manifest, dict):
                    raise ArchiveError("Archive invalide : manifest illisible.")
                manifest: dict[str, object] = loaded_manifest
                if manifest.get("format") != "pm2-desktop-project":
                    raise ArchiveError("Archive invalide : format non reconnu.")
                format_version = manifest.get("format_version")
                if format_version not in cls.SUPPORTED_FORMAT_VERSIONS:
                    raise ArchiveError("Archive invalide : version de format non prise en charge.")
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
                if format_version == cls.FORMAT_VERSION:
                    cls._verify_file_manifest(temp, manifest, names)
                probe = Database(temp / "project.db")
                try:
                    probe.upgrade_schema()
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
                if content_destination is not None:
                    cls._restore_content(temp, content_destination, overwrite=overwrite)
                staging.replace(database_destination)
                return manifest
        except zipfile.BadZipFile as exc:
            raise ArchiveError("Le fichier n'est pas une archive PM² valide.") from exc
        except MethodologyLoadError as exc:
            raise ArchiveError("Archive invalide : méthodologie illisible.") from exc

    @classmethod
    def _verify_file_manifest(
        cls, temp: Path, manifest: dict[str, object], archive_names: list[str]
    ) -> None:
        files = manifest.get("files")
        if not isinstance(files, dict):
            raise ArchiveError("Archive invalide : manifeste des fichiers absent.")
        actual_names = {name for name in archive_names if name and not name.endswith("/")}
        expected_names = {"manifest.json", *files}
        if actual_names != expected_names:
            raise ArchiveError("Archive invalide : liste de fichiers incohérente.")
        for name, metadata in files.items():
            if not isinstance(name, str) or not isinstance(metadata, dict):
                raise ArchiveError("Archive invalide : manifeste des fichiers illisible.")
            path = temp.joinpath(*PurePosixPath(name).parts)
            if metadata.get("size") != path.stat().st_size or metadata.get(
                "sha256"
            ) != sha256_file(path):
                raise ArchiveError(f"Archive corrompue : fichier altéré ({name}).")

    @staticmethod
    def _restore_content(temp: Path, destination: Path, *, overwrite: bool) -> None:
        if destination.exists() and not overwrite:
            raise ArchiveError(f"La destination du contenu existe déjà : {destination}")
        staging = destination.with_name(destination.name + ".opening")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        for name in ("documents", "attachments", "exports"):
            source = temp / name
            target = staging / name
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                target.mkdir()
        backup = destination.with_name(destination.name + ".previous")
        if backup.exists():
            shutil.rmtree(backup)
        try:
            if destination.exists():
                destination.replace(backup)
            staging.replace(destination)
        except Exception:
            if backup.exists() and not destination.exists():
                backup.replace(destination)
            raise
        finally:
            if backup.exists():
                shutil.rmtree(backup)
