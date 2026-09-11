from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pm2.application.context import ApplicationContext
from pm2.application.services import ProjectService
from pm2.infrastructure.orm import ProjectModel


@pytest.fixture
def context(tmp_path: Path) -> Iterator[ApplicationContext]:
    value = ApplicationContext.open(tmp_path / "test.db")
    yield value
    value.database.dispose()


@pytest.fixture
def session(context: ApplicationContext) -> Iterator[Session]:
    value = context.database.session_factory()
    yield value
    value.rollback()
    value.close()


@pytest.fixture
def project(session: Session, context: ApplicationContext) -> ProjectModel:
    value = ProjectService(session, context.methodology).create(
        reference="TEST-001",
        name="Projet de test",
        description="Projet PM²",
        project_manager="Alice Martin",
        project_owner="Bob Dupont",
    )
    session.commit()
    return value
