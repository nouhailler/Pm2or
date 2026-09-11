from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.orm import Session

from pm2.application.documents import DocumentService, GeneratedArtifact
from pm2.application.validation import ValidationService
from pm2.infrastructure.archive import ProjectArchiveService
from pm2.infrastructure.database import Database
from pm2.methodology.models import PM2Configuration


class ExportService:
    def __init__(self, session: Session, database: Database, methodology: PM2Configuration) -> None:
        self.session = session
        self.database = database
        self.methodology = methodology
        self.documents = DocumentService(session, methodology)

    def generate_artifact(
        self, project_id: str, artifact_code: str, format: str, output_dir: Path
    ) -> GeneratedArtifact:
        fmt = "md" if format.lower() == "markdown" else format.lower().lstrip(".")
        safe_code = artifact_code.lower().replace("_", "-")
        return self.documents.generate(
            project_id, artifact_code, output_dir / f"{safe_code}.{fmt}", fmt
        )

    def generate_project_bundle(
        self,
        project_id: str,
        destination: Path,
        formats: tuple[str, ...] = ("md", "html", "docx", "pdf"),
    ) -> Path:
        workspace = destination.parent / f".{destination.stem}-content"
        documents_dir = workspace / "documents"
        exports_dir = workspace / "exports"
        attachments_dir = workspace / "attachments"
        for directory in (documents_dir, exports_dir, attachments_dir):
            directory.mkdir(parents=True, exist_ok=True)
        report: list[dict[str, str]] = []
        for artifact_code in self.methodology.artifacts:
            for fmt in formats:
                generated = self.generate_artifact(project_id, artifact_code, fmt, documents_dir)
                report.append(
                    {
                        "artifact": artifact_code,
                        "format": generated.format,
                        "path": generated.path.name,
                        "sha256": generated.sha256,
                    }
                )
        problems = ValidationService(self.session).validate_project(project_id)
        (exports_dir / "validation-report.json").write_text(
            json.dumps([asdict(problem) for problem in problems], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (exports_dir / "export-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.session.commit()
        return ProjectArchiveService(self.database, self.session).save(
            project_id,
            destination,
            documents_dir=documents_dir,
            attachments_dir=attachments_dir,
            exports_dir=exports_dir,
        )
