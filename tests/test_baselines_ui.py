from __future__ import annotations

from decimal import Decimal
from typing import Any

from PySide6.QtWidgets import QInputDialog, QMessageBox
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.baselines import BaselineComparison, BaselineService
from pm2.infrastructure.orm import BaselineModel, ProjectModel
from pm2.ui.baselines_page import BaselinesPage


def test_baselines_page_creates_approves_and_compares(
    qtbot: Any,
    session: Session,
    project: ProjectModel,
    monkeypatch: Any,
) -> None:
    page = BaselinesPage(session, project)
    qtbot.addWidget(page)
    answers = iter([("Planning de référence", True), ("Alice", True), ("Bob", True)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: next(answers))
    monkeypatch.setattr(
        QInputDialog, "getItem", lambda *_args, **_kwargs: ("PLANNING", True)
    )
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, _title, message: messages.append(message),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, _title, message: messages.append(f"ERREUR:{message}"),
    )

    page._create()
    baseline = session.scalar(select(BaselineModel))
    assert baseline is not None
    assert page.table.rowCount() == 1
    assert baseline.approved_at is None

    page.table.selectRow(0)
    page._approve()
    assert baseline.approved_by == "Bob"
    assert baseline.approved_at is not None

    project.approved_budget = Decimal("42")
    session.commit()
    shown: list[BaselineComparison] = []
    monkeypatch.setattr(page, "_show_comparison", shown.append)
    page.table.selectRow(0)
    page._compare()

    assert shown and shown[0].changed >= 1
    text = page._comparison_text(shown[0])
    assert "budget/approved" in text
    assert not any(message.startswith("ERREUR:") for message in messages)


def test_baseline_comparison_text_without_difference(
    session: Session, project: ProjectModel
) -> None:
    baseline = BaselineService(session).create(project.id, name="Initiale", created_by="PM")
    comparison = BaselineService(session).compare(baseline.id)
    assert BaselinesPage._comparison_text(comparison).startswith("Aucun écart")
