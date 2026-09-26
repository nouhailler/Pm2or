from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pm2.application.baselines import BaselineService, baseline_sha256
from pm2.infrastructure.orm import BaselineModel, ProjectModel


def test_baseline_freezes_project_and_reports_current_differences(
    session: Session, project: ProjectModel
) -> None:
    service = BaselineService(session)
    baseline = service.create(
        project.id,
        name="Planning de référence",
        baseline_type="planning",
        created_by="Alice",
    )
    session.commit()

    payload = json.loads(baseline.snapshot)
    assert baseline.code == "B-001"
    assert baseline.type == "PLANNING"
    assert baseline.hash == baseline_sha256(baseline.snapshot)
    assert payload["format"] == "pm2-desktop-baseline"
    assert {
        "artifact_data",
        "budget",
        "deliverables",
        "documents",
        "milestones",
        "requirements",
        "risks",
        "work_plan",
    } <= payload.keys()
    assert service.compare(baseline.id).differences == ()

    project.approved_budget = Decimal("125000")
    session.commit()
    comparison = service.compare(baseline.id)

    assert comparison.changed >= 1
    assert {item.path for item in comparison.differences} >= {
        "budget/approved",
        "project/approved_budget",
    }
    assert baseline.snapshot == service.require(baseline.id).snapshot


def test_baseline_approval_is_the_only_allowed_update(
    session: Session, project: ProjectModel
) -> None:
    service = BaselineService(session)
    baseline = service.create(
        project.id, name="Référence approuvée", baseline_type="PROJECT", created_by="PM"
    )
    session.commit()

    service.approve(baseline.id, approved_by="PO")
    session.commit()
    assert baseline.approved_at is not None
    assert baseline.approved_by == "PO"

    with pytest.raises(ValueError, match="déjà approuvée"):
        service.approve(baseline.id, approved_by="PO")

    with pytest.raises(IntegrityError, match="baseline immutable"):
        session.execute(
            update(BaselineModel).where(BaselineModel.id == baseline.id).values(name="Altérée")
        )
    session.rollback()


def test_baseline_cannot_be_deleted_even_with_direct_sql(
    session: Session, project: ProjectModel
) -> None:
    baseline = BaselineService(session).create(
        project.id, name="Référence conservée", baseline_type="SCOPE", created_by="PM"
    )
    session.commit()

    with pytest.raises(IntegrityError, match="baseline immutable"):
        session.execute(delete(BaselineModel).where(BaselineModel.id == baseline.id))
    session.rollback()
    assert session.get(BaselineModel, baseline.id) is not None


def test_baseline_codes_are_monotonic(session: Session, project: ProjectModel) -> None:
    service = BaselineService(session)
    first = service.create(project.id, name="Initiale", created_by="PM")
    second = service.create(project.id, name="Révisée", created_by="PM")
    assert (first.code, second.code) == ("B-001", "B-002")
