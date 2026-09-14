from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.context import ApplicationContext
from pm2.application.services import AcceptanceService, DeliverableService
from pm2.config import AppPaths
from pm2.infrastructure.orm import (
    ChangeModel,
    DecisionModel,
    DeliverableModel,
    IssueModel,
    RiskModel,
    StakeholderModel,
    TaskModel,
)
from pm2.methodology import bundle_methodology
from pm2.ui.acceptance import AcceptanceExecutionWidget
from pm2.ui.crud import EntityCatalogPage
from pm2.ui.main_window import MainWindow
from pm2.ui.pages import DocumentsPage, GovernancePage, RegisterTab, WorkPlanPage
from pm2.ui.wizards import GateAssistant, PhaseAssistantPage


@pytest.mark.parametrize("decisions", [("Conserver",), ("Examiner", "Conserver"), ("Mettre",)])
def test_ui_project_methodology_choices(
    qtbot: Any,
    tmp_path: Path,
    context: ApplicationContext,
    project: Any,
    monkeypatch: Any,
    decisions: tuple[str, ...],
) -> None:
    future = context.methodology.model_copy(
        update={
            "methodology": context.methodology.methodology.model_copy(update={"version": "3.2"})
        }
    )
    context.methodology_bundle = bundle_methodology(future)
    pending = list(decisions)
    examined: list[str] = []
    original_exec = QMessageBox.exec

    def choose(message: QMessageBox) -> int:
        prefix = pending.pop(0)
        button = next(button for button in message.buttons() if button.text().startswith(prefix))
        QTimer.singleShot(0, button.click)
        return original_exec(message)

    monkeypatch.setattr(QMessageBox, "exec", choose)
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(
        MainWindow, "_show_methodology_diff", lambda _self, value: examined.append(value.id)
    )
    window = MainWindow(context, paths(tmp_path, context.database.path))
    qtbot.addWidget(window)
    expected = "3.2" if decisions == ("Mettre",) else "3.1"
    assert window.project_methodology.methodology.version == expected
    assert window.project.methodology_version == expected
    assert all(
        page.methodology.methodology.version == expected
        for page in window.pages
        if isinstance(page, PhaseAssistantPage)
    )
    assert bool(examined) == ("Examiner" in decisions)
    assert not pending
    window.close()


class AcceptedDialog:
    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def exec(self) -> QDialog.DialogCode:
        return QDialog.DialogCode.Accepted

    def values(self) -> dict[str, Any]:
        return dict(self._values)


def paths(tmp_path: Path, database: Path) -> AppPaths:
    return AppPaths(
        tmp_path,
        database,
        tmp_path / "app.log",
        tmp_path / "recent.json",
    )


def test_ui_create_project(qtbot: Any, tmp_path: Path, monkeypatch: Any) -> None:
    database = tmp_path / "create-project.db"
    context = ApplicationContext.open(database)
    window = MainWindow(context, paths(tmp_path, database))
    qtbot.addWidget(window)
    values = {
        "reference": "UI-001",
        "name": "Projet créé dans l’UI",
        "description": "Parcours pytest-qt",
        "project_manager": "Alice",
        "project_owner": "Bob",
        "approved_budget": Decimal("25000"),
        "currency": "CHF",
        "start_date": date(2026, 1, 1),
        "target_end_date": date(2026, 12, 31),
    }
    monkeypatch.setattr("pm2.ui.main_window.ProjectDialog", lambda _parent: AcceptedDialog(values))

    window.new_project()

    assert window.project is not None
    assert window.project.reference == "UI-001"
    assert window.navigation.count() >= 16
    window.close()


def test_ui_navigate_all_phase_assistants(
    qtbot: Any,
    tmp_path: Path,
    context: ApplicationContext,
    project: Any,
) -> None:
    window = MainWindow(context, paths(tmp_path, context.database.path))
    qtbot.addWidget(window)

    for name, phase in (
        ("Lancement", "LAUNCH"),
        ("Planification", "PLANNING"),
        ("Exécution", "EXECUTION"),
        ("Clôture", "CLOSING"),
    ):
        window.navigate_to(name)
        page = window.stack.currentWidget()
        assert isinstance(page, PhaseAssistantPage)
        assert page.phase == phase
        assert page.tabs.count() >= len(page.editors) + 1

    window.close()


def test_ui_create_stakeholder(
    qtbot: Any, session: Session, project: Any, context: ApplicationContext, monkeypatch: Any
) -> None:
    page = GovernancePage(session, project, context.methodology)
    qtbot.addWidget(page)
    answers: Iterator[tuple[str, bool]] = iter(
        [("Claire Client", True), ("Direction métier", True)]
    )
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: next(answers))

    page._add_stakeholder()

    stakeholder = session.scalar(
        select(StakeholderModel).where(StakeholderModel.name == "Claire Client")
    )
    assert stakeholder is not None
    assert stakeholder.organisation == "Direction métier"
    assert page.stakeholders.rowCount() == 1


def test_ui_create_wbs_and_task(
    qtbot: Any, session: Session, project: Any, monkeypatch: Any
) -> None:
    page = WorkPlanPage(session, project)
    qtbot.addWidget(page)
    responses = [
        {
            "code": "1",
            "name": "Lot principal",
            "node_type": "work_package",
            "description": "Lot UI",
            "planned_start": date(2026, 1, 1),
            "planned_end": date(2026, 1, 5),
            "progress_percent": 0,
            "planned_cost": Decimal("0"),
        },
        {
            "code": "1.1",
            "name": "Tâche UI",
            "node_type": "task",
            "description": "Créée par le parcours UI",
            "planned_start": date(2026, 1, 2),
            "planned_end": date(2026, 1, 4),
            "progress_percent": 25,
            "planned_cost": Decimal("1200"),
        },
    ]
    monkeypatch.setattr(
        "pm2.ui.pages.WbsNodeDialog",
        lambda *_args, **_kwargs: AcceptedDialog(responses.pop(0)),
    )

    page._add()
    page.tree.setCurrentItem(page.tree.topLevelItem(0))
    page._add()

    task = session.scalar(select(TaskModel))
    assert task is not None
    assert task.progress_percent == 25
    assert page.tree.topLevelItem(0).childCount() == 1
    assert page.gantt.rowCount() == 1


def _register_page(
    qtbot: Any,
    session: Session,
    project: Any,
    monkeypatch: Any,
    kind: str,
    values: dict[str, Any],
) -> RegisterTab:
    page = RegisterTab(session, project, kind)
    qtbot.addWidget(page)
    monkeypatch.setattr(
        "pm2.ui.pages.RegisterItemDialog",
        lambda *_args, **_kwargs: AcceptedDialog(values),
    )
    page._add()
    return page


def test_ui_create_risk(qtbot: Any, session: Session, project: Any, monkeypatch: Any) -> None:
    page = _register_page(
        qtbot,
        session,
        project,
        monkeypatch,
        "risk",
        {
            "code": "R-UI",
            "title": "Risque UI",
            "description": "Risque saisi",
            "owner": "Alice",
            "probability": 4,
            "impact": 5,
            "strategy": "Escalade au PSC",
        },
    )
    risk = session.scalar(select(RiskModel).where(RiskModel.code == "R-UI"))
    assert risk is not None and risk.score == 20
    assert page.table.rowCount() == 1


def test_ui_create_issue(qtbot: Any, session: Session, project: Any, monkeypatch: Any) -> None:
    page = _register_page(
        qtbot,
        session,
        project,
        monkeypatch,
        "issue",
        {
            "code": "I-UI",
            "title": "Problème UI",
            "description": "Incident déclaré",
            "owner": "Alice",
            "priority": "HIGH",
            "impact": "Délai",
        },
    )
    assert session.scalar(select(IssueModel).where(IssueModel.code == "I-UI")) is not None
    assert page.table.rowCount() == 1


def test_ui_create_decision(qtbot: Any, session: Session, project: Any, monkeypatch: Any) -> None:
    page = _register_page(
        qtbot,
        session,
        project,
        monkeypatch,
        "decision",
        {
            "code": "D-UI",
            "title": "Décision UI",
            "description": "Choix enregistré",
            "outcome": "Option A",
            "rationale": "Meilleur rapport valeur/risque",
        },
    )
    decision = session.scalar(select(DecisionModel).where(DecisionModel.code == "D-UI"))
    assert decision is not None and decision.outcome == "Option A"
    assert page.table.rowCount() == 1


def test_ui_submit_change(qtbot: Any, session: Session, project: Any, monkeypatch: Any) -> None:
    page = _register_page(
        qtbot,
        session,
        project,
        monkeypatch,
        "change",
        {
            "code": "C-UI",
            "title": "Modification UI",
            "description": "Demande soumise",
            "priority": "MEDIUM",
            "reason": "Évolution métier",
        },
    )
    page.table.selectRow(0)
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *_args, **_kwargs: ("SUBMITTED", True),
    )

    page._transition()

    change = session.scalar(select(ChangeModel).where(ChangeModel.code == "C-UI"))
    assert change is not None and change.status == "SUBMITTED"


def test_ui_evaluate_gate(
    qtbot: Any, session: Session, project: Any, context: ApplicationContext
) -> None:
    assistant = GateAssistant(session, project, context.methodology, "RFP")
    qtbot.addWidget(assistant)
    for checkbox, evidence, _item_id in assistant.items:
        checkbox.setChecked(True)
        evidence.setText("Preuve vérifiée")
    assistant.decision.setCurrentText("APPROVED")
    assistant.decider.setText("Comité de pilotage")

    assistant.save_decision()

    session.refresh(project)
    assert project.current_phase == "PLANNING"
    assert assistant.review.status == "APPROVED"


def test_ui_generate_artifact(
    qtbot: Any,
    session: Session,
    project: Any,
    context: ApplicationContext,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    output = tmp_path / "exports"
    page = DocumentsPage(session, context.database, project, context.methodology, output)
    qtbot.addWidget(page)
    for row in range(page.table.rowCount()):
        if page.table.item(row, 0).text() == "PROJECT_CHARTER":
            page.table.selectRow(row)
            break
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_args, **_kwargs: str(output))
    monkeypatch.setattr(QMessageBox, "information", lambda *_args, **_kwargs: None)

    page._generate()

    generated = output / "project-charter.md"
    assert generated.exists()
    assert "PROJECT_CHARTER" in generated.read_text(encoding="utf-8")
    assert page.history.rowCount() == 1


def test_ui_execute_test_and_accept_deliverable(
    qtbot: Any,
    session: Session,
    project: Any,
    monkeypatch: Any,
) -> None:
    deliverable = DeliverableService(session).create(
        project.id, "DEL-UI", "Livrable accepté", owner="Alice"
    )
    deliverable.status = "READY_FOR_ACCEPTANCE"
    criterion = AcceptanceService(session).add_criterion(
        deliverable.id, "AC-UI", "Le livrable est conforme"
    )
    AcceptanceService(session).add_test(criterion.id, "AT-UI", "Vérifier la conformité", "Conforme")
    session.commit()
    widget = AcceptanceExecutionWidget(session, project)
    qtbot.addWidget(widget)
    widget.tests.selectRow(0)
    monkeypatch.setattr(QInputDialog, "getItem", lambda *_args, **_kwargs: ("PASSED", True))
    monkeypatch.setattr(
        QInputDialog,
        "getMultiLineText",
        lambda *_args, **_kwargs: ("Preuve jointe", True),
    )
    widget.record_test()
    widget.deliverables.selectRow(0)
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: ("Porteur", True))
    widget.accept_deliverable()

    accepted = session.scalar(select(DeliverableModel).where(DeliverableModel.code == "DEL-UI"))
    assert accepted is not None
    assert accepted.status == "ACCEPTED"
    assert accepted.acceptance_status == "ACCEPTED"
    assert "Porteur" in widget.history.toPlainText()


def test_ui_catalog_crud_details_audit_and_restore(
    qtbot: Any,
    session: Session,
    project: Any,
    monkeypatch: Any,
) -> None:
    page = EntityCatalogPage(session, project.id)
    qtbot.addWidget(page)
    assert page.selector.count() == 47
    page.selector.setCurrentIndex(page.selector.findData("stakeholders"))
    monkeypatch.setattr(
        "pm2.ui.crud.EntityEditDialog",
        lambda *_args, **_kwargs: AcceptedDialog(
            {"name": "Partie prenante CRUD", "organisation": "PMO"}
        ),
    )
    page._create()
    assert page.table.rowCount() == 1
    page.table.selectRow(0)
    assert page.data_view.rowCount() > 5
    assert page.audit_view.rowCount() == 1
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    page._remove()
    assert page.table.rowCount() == 0
    page.include_archived.setChecked(True)
    assert page.table.rowCount() == 1
    page.table.selectRow(0)
    assert page.audit_view.rowCount() == 2
    page._restore()
    restored = session.scalar(
        select(StakeholderModel).where(StakeholderModel.name == "Partie prenante CRUD")
    )
    assert restored is not None and not restored.archived
    page.table.selectRow(0)
    assert page.audit_view.rowCount() == 3
