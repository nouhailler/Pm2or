from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from pm2.infrastructure.orm import ProjectModel, RoleModel
from pm2.infrastructure.repositories import Repository


def test_repository_crud_and_guards(session: Session) -> None:
    repository = Repository(session, ProjectModel)
    project = repository.add(ProjectModel(reference="REPO-1", name="Repository"))
    assert repository.get(project.id) is project
    assert repository.require(project.id) is project
    assert project in repository.list(ProjectModel.reference == "REPO-1")

    updated = repository.update(project.id, name="Modifié")
    assert updated.name == "Modifié"
    with pytest.raises(ValueError, match="Champ non modifiable"):
        repository.update(project.id, id="forbidden")
    with pytest.raises(LookupError, match="introuvable"):
        repository.require("missing")
    assert repository.archive(project.id).archived is True


def test_repository_rejects_archive_for_non_archivable_model(session: Session) -> None:
    repository = Repository(session, RoleModel)
    role = repository.add(RoleModel(code="TST", name="Test"))
    with pytest.raises(TypeError, match="ne peut pas être archivé"):
        repository.archive(role.code)
