from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pm2.application.context import ApplicationContext
from pm2.application.documents import DocumentService
from pm2.infrastructure.archive import ArchiveError, ProjectArchiveService
from pm2.infrastructure.database import Database
from pm2.infrastructure.orm import ProjectModel


@pytest.mark.parametrize("fmt", ["md", "html", "docx", "pdf"])
def test_document_formats(
    session: Session, project: ProjectModel, context: ApplicationContext, tmp_path: Path, fmt: str
) -> None:
    service = DocumentService(session, context.methodology, Path("templates"))
    service.ensure_catalog(project.id)
    output = tmp_path / f"charter.{fmt}"
    result = service.generate(project.id, "PROJECT_CHARTER", output, fmt)
    assert result.path.exists()
    assert result.path.stat().st_size > 100
    assert len(result.sha256) == 64


def test_archive_roundtrip_and_integrity(
    session: Session, project: ProjectModel, context: ApplicationContext, tmp_path: Path
) -> None:
    archive = ProjectArchiveService(context.database, session).save(
        project.id, tmp_path / "demo.pm2"
    )
    with zipfile.ZipFile(archive) as bundle:
        assert {
            "project.db",
            "manifest.json",
            "methodology/PM2_METHODOLOGY.yaml",
        } <= set(bundle.namelist())
        assert {"methodology/", "documents/", "attachments/", "exports/"} <= set(bundle.namelist())
        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["project_id"] == project.id
        assert manifest["methodology_hash"] == project.methodology_hash
        assert (
            bundle.read("methodology/PM2_METHODOLOGY.yaml").decode("utf-8")
            == project.methodology_snapshot
        )
    restored = tmp_path / "restored.db"
    opened = ProjectArchiveService.open(archive, restored)
    assert opened["project_id"] == project.id
    probe = Database(restored)
    with probe.session_factory() as restored_session:
        assert restored_session.get(ProjectModel, project.id).name == project.name
    probe.dispose()


def test_archive_rejects_tampered_methodology(
    session: Session, project: ProjectModel, context: ApplicationContext, tmp_path: Path
) -> None:
    source = ProjectArchiveService(context.database, session).save(
        project.id, tmp_path / "source.pm2"
    )
    tampered = tmp_path / "tampered.pm2"
    with (
        zipfile.ZipFile(source, "r") as original,
        zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as changed,
    ):
        for info in original.infolist():
            data = original.read(info.filename)
            if info.filename == "methodology/PM2_METHODOLOGY.yaml":
                data += b"\n# alteration\n"
            changed.writestr(info, data)

    with pytest.raises(ArchiveError, match="méthodologie"):
        ProjectArchiveService.open(tampered, tmp_path / "tampered.db")


def test_corrupt_archive_does_not_overwrite(tmp_path: Path) -> None:
    corrupt = tmp_path / "broken.pm2"
    corrupt.write_bytes(b"not a zip")
    destination = tmp_path / "safe.db"
    destination.write_bytes(b"keep")
    with pytest.raises(ArchiveError):
        ProjectArchiveService.open(corrupt, destination, overwrite=True)
    assert destination.read_bytes() == b"keep"
