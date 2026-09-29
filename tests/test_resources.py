from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from PySide6.QtWidgets import QInputDialog, QMessageBox
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pm2.application.baselines import BaselineService
from pm2.application.governance import GovernanceService
from pm2.application.planning import WorkPlanService
from pm2.application.resources import ResourceService
from pm2.infrastructure.orm import ProjectModel, TaskResourceAllocationModel
from pm2.ui.resources_page import ResourcesPage


def _planned_task(session: Session, project: ProjectModel):
    planning = WorkPlanService(session)
    node = planning.create_node(project.id, "T-034", "Préparer le lot", node_type="task")
    return planning.create_task(
        node.id,
        planned_start=date(2026, 9, 14),
        planned_end=date(2026, 9, 25),
        planned_effort=Decimal("12"),
    )


def test_resource_allocations_and_weekly_overload(
    session: Session, project: ProjectModel
) -> None:
    people = GovernanceService(session)
    patrick = people.add_person(name="Patrick")
    marie = people.add_person(name="Marie")
    task = _planned_task(session, project)
    resources = ResourceService(session)
    patrick_resource = resources.create(
        project.id,
        "Patrick",
        "PERSON",
        person_id=patrick.id,
        default_availability_percent=Decimal("80"),
    )
    marie_resource = resources.create(
        project.id, "Marie", "PERSON", person_id=marie.id
    )
    resources.allocate(task.id, patrick_resource.id, Decimal("8"))
    resources.allocate(task.id, marie_resource.id, Decimal("4"))
    resources.set_weekly_availability(
        patrick_resource.id, date(2026, 9, 14), Decimal("100")
    )
    resources.set_weekly_availability(
        patrick_resource.id, date(2026, 9, 21), Decimal("70")
    )

    loads = {
        (item.resource_name, item.week_start): item
        for item in resources.utilization(project.id)
    }

    week_38 = loads[("Patrick", date(2026, 9, 14))]
    week_39 = loads[("Patrick", date(2026, 9, 21))]
    assert week_38.allocated_days == Decimal("4.00")
    assert week_38.capacity_days == Decimal("5.00")
    assert week_38.utilization_percent == Decimal("80.0")
    assert not week_38.overloaded
    assert week_39.capacity_days == Decimal("3.50")
    assert week_39.utilization_percent == Decimal("114.3")
    assert week_39.overloaded


def test_allocations_cannot_exceed_task_effort(
    session: Session, project: ProjectModel
) -> None:
    task = _planned_task(session, project)
    resources = ResourceService(session)
    team = resources.create(project.id, "Équipe interne", "TEAM")
    supplier = resources.create(project.id, "Fournisseur", "SUPPLIER")
    resources.allocate(task.id, team.id, Decimal("8"))
    resources.allocate(task.id, supplier.id, Decimal("4"))

    with pytest.raises(ValueError, match="dépasserait"):
        resources.allocate(task.id, team.id, Decimal("9"))


def test_database_rejects_allocation_beyond_task_effort(
    session: Session, project: ProjectModel
) -> None:
    task = _planned_task(session, project)
    resource = ResourceService(session).create(project.id, "Équipe", "TEAM")
    session.add(
        TaskResourceAllocationModel(
            task_id=task.id,
            resource_id=resource.id,
            effort_days=Decimal("13"),
        )
    )

    with pytest.raises(IntegrityError, match="exceed planned effort"):
        session.flush()


@pytest.mark.parametrize("resource_type", ["TEAM", "SUPPLIER", "EQUIPMENT", "BUDGET"])
def test_non_person_resource_types(
    session: Session, project: ProjectModel, resource_type: str
) -> None:
    resource = ResourceService(session).create(project.id, resource_type, resource_type)
    assert resource.resource_type == resource_type
    assert resource.person_id is None


def test_resources_page_shows_capacity_warning(
    qtbot: Any, session: Session, project: ProjectModel
) -> None:
    task = _planned_task(session, project)
    resources = ResourceService(session)
    team = resources.create(
        project.id,
        "Équipe",
        "TEAM",
        default_availability_percent=Decimal("50"),
    )
    resources.allocate(task.id, team.id, Decimal("12"))

    page = ResourcesPage(session, project)
    qtbot.addWidget(page)

    assert page.resources.rowCount() == 1
    assert page.allocations.item(0, 3).text() == "12 j"
    assert "2 surcharge(s)" in page.capacity_summary.text()
    assert "⚠" in page.capacity.item(0, 7).text()


def test_resources_are_frozen_in_project_baseline(
    session: Session, project: ProjectModel
) -> None:
    task = _planned_task(session, project)
    resources = ResourceService(session)
    equipment = resources.create(project.id, "Banc de test", "EQUIPMENT")
    resources.allocate(task.id, equipment.id, Decimal("2"))

    snapshot = json.loads(BaselineService(session).capture(project.id))

    frozen = snapshot["resources"]["EQUIPMENT:Banc de test"]
    assert frozen["resource_type"] == "EQUIPMENT"
    assert frozen["task_allocations"][0]["effort_days"] == "2.00"


def test_resources_page_creation_availability_allocation_and_archive(
    qtbot: Any,
    session: Session,
    project: ProjectModel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    GovernanceService(session).add_person(name="Patrick")
    _planned_task(session, project)
    page = ResourcesPage(session, project)
    qtbot.addWidget(page)

    item_answers = iter(
        [
            ("PERSON — Personne", True),
            ("Patrick", True),
        ]
    )
    monkeypatch.setattr(
        QInputDialog, "getItem", lambda *_args, **_kwargs: next(item_answers)
    )
    monkeypatch.setattr(
        QInputDialog, "getDouble", lambda *_args, **_kwargs: (80.0, True)
    )
    page._add_resource()
    assert page.resources.rowCount() == 1

    page.resources.setCurrentCell(0, 0)
    monkeypatch.setattr(
        QInputDialog, "getText", lambda *_args, **_kwargs: ("2026-09-17", True)
    )
    monkeypatch.setattr(
        QInputDialog, "getDouble", lambda *_args, **_kwargs: (70.0, True)
    )
    page._set_availability()
    assert page.capacity.item(0, 2).text() == "2026-S38"

    allocation_answers = iter(
        [
            ("T-034 — Préparer le lot", True),
            ("Patrick — Personne", True),
        ]
    )
    monkeypatch.setattr(
        QInputDialog, "getItem", lambda *_args, **_kwargs: next(allocation_answers)
    )
    monkeypatch.setattr(
        QInputDialog, "getDouble", lambda *_args, **_kwargs: (8.0, True)
    )
    page._add_allocation()
    assert page.allocations.rowCount() == 1

    page.allocations.setCurrentCell(0, 0)
    page._remove_allocation()
    assert page.allocations.rowCount() == 0

    page.resources.setCurrentCell(0, 0)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    page._archive_resource()
    assert page.resources.rowCount() == 0
