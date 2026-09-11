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
        assert {"project.db", "manifest.json"} <= set(bundle.namelist())
        assert {"documents/", "attachments/", "exports/"} <= set(bundle.namelist())
        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["project_id"] == project.id
    restored = tmp_path / "restored.db"
    opened = ProjectArchiveService.open(archive, restored)
    assert opened["project_id"] == project.id
    probe = Database(restored)
    with probe.session_factory() as restored_session:
        assert restored_session.get(ProjectModel, project.id).name == project.name
    probe.dispose()


def test_corrupt_archive_does_not_overwrite(tmp_path: Path) -> None:
    corrupt = tmp_path / "broken.pm2"
    corrupt.write_bytes(b"not a zip")
    destination = tmp_path / "safe.db"
    destination.write_bytes(b"keep")
    with pytest.raises(ArchiveError):
        ProjectArchiveService.open(corrupt, destination, overwrite=True)
    assert destination.read_bytes() == b"keep"
