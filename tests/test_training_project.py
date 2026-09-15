import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from pm2.application.artifacts import ARTIFACT_SCHEMAS, ArtifactDataService
from pm2.application.context import ApplicationContext
from pm2.infrastructure.orm import ProjectModel


def test_example_populates_every_document_with_demonstration_content(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "training.db"
    environment = {**os.environ, "PYTHONPATH": str(root / "src")}
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/create_training_project.py"),
            "--database",
            str(database),
        ],
        check=True,
        env=environment,
        capture_output=True,
        text=True,
    )
    context = ApplicationContext.open(database)
    with context.database.session_factory() as session:
        project = session.scalar(
            select(ProjectModel).where(ProjectModel.reference == "FORMATION-2026-001")
        )
        assert project is not None
        data = ArtifactDataService(session)

        for code, schema in ARTIFACT_SCHEMAS.items():
            values = data.load(project.id, code)
            fields = [field for section in schema.sections for field in section.fields]
            assert set(values) == {field.code for field in fields}
            assert any(values[field.code].strip() for field in fields)
    context.database.dispose()
