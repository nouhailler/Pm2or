from __future__ import annotations

import hashlib
import mimetypes
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.services import AuditService
from pm2.infrastructure.orm import AttachmentModel, row_to_dict


class AttachmentService:
    MAX_SIZE = 25 * 1024 * 1024

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, project_id: str, source: Path, description: str = "") -> AttachmentModel:
        if not source.is_file():
            raise ValueError(f"Fichier introuvable : {source}")
        size = source.stat().st_size
        if size > self.MAX_SIZE:
            raise ValueError("La pièce jointe dépasse la limite de 25 Mo.")
        content = source.read_bytes()
        attachment = AttachmentModel(
            project_id=project_id,
            filename=source.name,
            media_type=mimetypes.guess_type(source.name)[0] or "application/octet-stream",
            size_bytes=size,
            content_hash=hashlib.sha256(content).hexdigest(),
            description=description.strip(),
            content=content,
        )
        self.session.add(attachment)
        self.session.flush()
        AuditService(self.session).record(
            project_id,
            "attachment",
            attachment.id,
            "CREATE",
            new={key: value for key, value in row_to_dict(attachment).items() if key != "content"},
        )
        return attachment

    def list(self, project_id: str) -> Sequence[AttachmentModel]:
        return self.session.scalars(
            select(AttachmentModel)
            .where(
                AttachmentModel.project_id == project_id,
                AttachmentModel.archived.is_(False),
            )
            .order_by(AttachmentModel.created_at.desc())
        ).all()

    def require(self, project_id: str, attachment_id: str) -> AttachmentModel:
        attachment = self.session.scalar(
            select(AttachmentModel).where(
                AttachmentModel.id == attachment_id,
                AttachmentModel.project_id == project_id,
                AttachmentModel.archived.is_(False),
            )
        )
        if attachment is None:
            raise LookupError(f"Pièce jointe introuvable : {attachment_id}")
        return attachment

    def materialize(self, project_id: str, attachment_id: str, directory: Path) -> Path:
        attachment = self.require(project_id, attachment_id)
        if hashlib.sha256(attachment.content).hexdigest() != attachment.content_hash:
            raise OSError("La pièce jointe a échoué son contrôle d'intégrité.")
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / attachment.filename
        destination.write_bytes(attachment.content)
        return destination

    def remove(self, project_id: str, attachment_id: str) -> None:
        attachment = self.require(project_id, attachment_id)
        attachment.archived = True
        AuditService(self.session).record(
            project_id, "attachment", attachment.id, "ARCHIVE", old={"filename": attachment.filename}
        )
        self.session.flush()
