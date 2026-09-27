from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pm2.application.audit import AuditService, AuditTrailService
from pm2.application.crud import EntityCrudService
from pm2.infrastructure.orm import AuditEventModel, ProjectModel
from pm2.ui.audit_trail_page import AuditTrailPage


def test_audit_event_contains_professional_context(
    session: Session, project: ProjectModel, monkeypatch: Any
) -> None:
    monkeypatch.setattr("pm2.application.audit.getpass.getuser", lambda: "Patrick")
    event = AuditService(session).record(
        project.id,
        "change",
        "change-id",
        "TRANSITION:SUBMITTED→IMPACT_ANALYSIS",
        old={"code": "CR-007", "status": "SUBMITTED"},
        new={"code": "CR-007", "status": "IMPACT_ANALYSIS"},
        origin="workflow",
        reason="Demande du comité de pilotage",
    )
    session.commit()

    assert event.actor == "Patrick"
    assert event.object_label == "ChangeRequest CR-007"
    assert event.origin == "workflow"
    assert event.reason == "Demande du comité de pilotage"
    changes = AuditTrailService.changes(event)
    assert [(item.field, item.before, item.after) for item in changes] == [
        ("status", "SUBMITTED", "IMPACT_ANALYSIS")
    ]


def test_audit_trail_filters_and_exports_json(
    session: Session, project: ProjectModel, tmp_path: Path
) -> None:
    event = AuditService(session).record(
        project.id,
        "risk",
        "risk-id",
        "CREATE",
        new={"code": "R-003", "title": "Retard fournisseur", "status": "OPEN"},
        actor="Alice",
        origin="registre",
    )
    session.commit()
    service = AuditTrailService(session)

    assert event in service.list(project.id, entity_type="risk")
    assert event in service.list(project.id, actor="Alice")
    assert event in service.list(project.id, search="R-003")
    assert "Alice" in service.actors(project.id)
    assert "risk" in service.entity_types(project.id)

    destination = service.export_json(project.id, tmp_path / "audit.json")
    payload = json.loads(destination.read_text(encoding="utf-8"))
    exported = next(item for item in payload if item["id"] == event.id)
    assert exported["object"] == "Risk R-003"
    assert exported["after"]["status"] == "OPEN"


def test_audit_events_are_append_only(session: Session, project: ProjectModel) -> None:
    event = AuditService(session).record(
        project.id,
        "risk",
        "risk-id",
        "CREATE",
        new={"code": "R-004"},
    )
    session.commit()

    with pytest.raises(IntegrityError, match="audit event immutable"):
        session.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == event.id)
            .values(reason="altérée")
        )
    session.rollback()
    with pytest.raises(IntegrityError, match="audit event immutable"):
        session.execute(delete(AuditEventModel).where(AuditEventModel.id == event.id))
    session.rollback()

    service = EntityCrudService(session, project.id)
    with pytest.raises(ValueError, match="append-only"):
        service.create("audit_events", {})
    with pytest.raises(ValueError, match="immuable"):
        service.update("audit_events", event.id, {"reason": "altérée"})
    with pytest.raises(ValueError, match="immuable"):
        service.remove("audit_events", event.id)


def test_audit_trail_page_timeline_and_export(
    qtbot: Any,
    session: Session,
    project: ProjectModel,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    AuditService(session).record(
        project.id,
        "deliverable",
        "deliverable-id",
        "TRANSITION:READY_FOR_ACCEPTANCE→ACCEPTED",
        old={"code": "D-007", "status": "READY_FOR_ACCEPTANCE"},
        new={"code": "D-007", "status": "ACCEPTED"},
        actor="Porteur",
        origin="acceptation",
        reason="Critères satisfaits",
    )
    session.commit()
    page = AuditTrailPage(session, project)
    qtbot.addWidget(page)

    assert page.timeline.topLevelItemCount() >= 2
    assert "Deliverable D-007" in page.timeline.topLevelItem(0).text(1)
    assert page.event_title.text().startswith("Deliverable D-007")
    assert page.changes.rowCount() == 1
    assert page.changes.item(0, 0).text() == "status"

    page.search.setText("introuvable")
    assert page.timeline.topLevelItemCount() == 0
    page.search.clear()
    assert page.timeline.topLevelItemCount() >= 2

    destination = tmp_path / "timeline.json"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *_args, **_kwargs: (str(destination), "")
    )
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, _title, message: messages.append(message),
    )
    page._export()
    assert destination.exists()
    assert messages
