from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pm2.application.attachments import AttachmentService
from pm2.infrastructure.orm import ProjectModel


def test_attachment_lifecycle_and_materialization(
    session: Session, project: ProjectModel, tmp_path: Path
) -> None:
    source = tmp_path / "preuve.txt"
    source.write_text("preuve d'acceptation", encoding="utf-8")
    service = AttachmentService(session)

    attachment = service.add(project.id, source, "Recette utilisateur")
    session.commit()
    assert service.list(project.id) == [attachment]
    assert attachment.media_type == "text/plain"
    assert len(attachment.content_hash) == 64

    output = service.materialize(project.id, attachment.id, tmp_path / "cache")
    assert output.read_text(encoding="utf-8") == "preuve d'acceptation"

    service.remove(project.id, attachment.id)
    session.commit()
    assert service.list(project.id) == []
    with pytest.raises(LookupError, match="introuvable"):
        service.materialize(project.id, attachment.id, tmp_path / "removed")


def test_attachment_rejects_missing_and_oversized_files(
    session: Session, project: ProjectModel, tmp_path: Path, monkeypatch
) -> None:
    service = AttachmentService(session)
    with pytest.raises(ValueError, match="introuvable"):
        service.add(project.id, tmp_path / "absent.txt")

    source = tmp_path / "large.bin"
    source.write_bytes(b"large")
    monkeypatch.setattr(AttachmentService, "MAX_SIZE", 2)
    with pytest.raises(ValueError, match="25 Mo"):
        service.add(project.id, source)


def test_attachment_detects_corrupt_content(
    session: Session, project: ProjectModel, tmp_path: Path
) -> None:
    source = tmp_path / "preuve.txt"
    source.write_text("preuve", encoding="utf-8")
    service = AttachmentService(session)
    attachment = service.add(project.id, source)
    attachment.content = b"contenu altere"
    session.flush()

    with pytest.raises(OSError, match="intégrité"):
        service.materialize(project.id, attachment.id, tmp_path / "cache")
    assert not (tmp_path / "cache" / "preuve.txt").exists()


def test_attachment_propagates_destination_permission_error(
    session: Session,
    project: ProjectModel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "preuve.txt"
    source.write_text("preuve", encoding="utf-8")
    attachment = AttachmentService(session).add(project.id, source)

    def deny_write(_path: Path, _content: bytes) -> int:
        raise PermissionError("permission denied")

    monkeypatch.setattr(Path, "write_bytes", deny_write)
    with pytest.raises(PermissionError, match="permission denied"):
        AttachmentService(session).materialize(project.id, attachment.id, tmp_path / "cache")
