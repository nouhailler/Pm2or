from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDialog, QMessageBox

from pm2.ui.dialogs import ProjectDialog, RegisterItemDialog, TraceLinkDialog, WbsNodeDialog


@pytest.fixture
def warnings(monkeypatch: Any) -> list[str]:
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: messages.append(message),
    )
    return messages


def test_project_dialog_validation_and_values(qtbot: Any, warnings: list[str]) -> None:
    dialog = ProjectDialog()
    qtbot.addWidget(dialog)
    dialog._validate()
    assert warnings == ["Le nom et la référence sont obligatoires."]

    dialog.name.setText(" Projet ")
    dialog.reference.setText(" REF-1 ")
    dialog.start.setDate(QDate(2026, 2, 2))
    dialog.end.setDate(QDate(2026, 2, 1))
    dialog._validate()
    assert warnings[-1] == "La fin cible doit suivre le début."

    dialog.end.setDate(QDate(2026, 3, 2))
    dialog.description.setPlainText(" Description ")
    dialog.pm.setText(" Alice ")
    dialog.po.setText(" Bob ")
    dialog.budget.setValue(12.50)
    dialog.currency.setCurrentText("CHF")
    dialog._validate()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.values() == {
        "name": "Projet",
        "reference": "REF-1",
        "description": "Description",
        "project_manager": "Alice",
        "project_owner": "Bob",
        "approved_budget": Decimal("12.5"),
        "currency": "CHF",
        "start_date": date(2026, 2, 2),
        "target_end_date": date(2026, 3, 2),
    }


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("risk", {"owner": "Alice", "probability": 4, "impact": 5, "strategy": "Réduire"}),
        ("issue", {"owner": "Alice", "priority": "HIGH", "impact": ""}),
        ("decision", {"outcome": "Validé", "rationale": ""}),
        ("change", {"priority": "HIGH", "reason": "Nouveau besoin"}),
    ],
)
def test_register_dialog_variants(
    qtbot: Any, warnings: list[str], kind: str, expected: dict[str, Any]
) -> None:
    dialog = RegisterItemDialog(kind)
    qtbot.addWidget(dialog)
    dialog._validate()
    assert warnings[-1] == "Le code et le titre sont obligatoires."
    dialog.code.setText(" X-1 ")
    dialog.title.setText(" Élément ")
    dialog.description.setPlainText(" Détail ")
    dialog.owner.setText(" Alice ")
    dialog.priority.setCurrentText("HIGH")
    dialog.probability.setValue(4)
    dialog.impact.setValue(5)
    dialog.strategy.setPlainText("Réduire")
    dialog.outcome.setPlainText("Validé")
    dialog.reason.setPlainText("Nouveau besoin")
    dialog._validate()
    assert dialog.result() == QDialog.DialogCode.Accepted
    values = dialog.values()
    assert values | expected == values
    assert values["code"] == "X-1"
    assert values["title"] == "Élément"


def test_wbs_dialog_create_edit_and_milestone(qtbot: Any, warnings: list[str]) -> None:
    dialog = WbsNodeDialog()
    qtbot.addWidget(dialog)
    dialog._validate()
    assert warnings[-1] == "Le code et le nom sont obligatoires."
    dialog.code.setText("1.1")
    dialog.name.setText("Jalon")
    dialog.node_type.setCurrentIndex(dialog.node_type.findData("milestone"))
    dialog.start.setDate(QDate(2026, 5, 4))
    dialog.end.setDate(QDate(2026, 5, 3))
    dialog._validate()
    assert warnings[-1] == "La fin doit suivre le début."
    dialog.end.setDate(QDate(2026, 5, 5))
    dialog.cost.setValue(80)
    values = dialog.values()
    assert values["planned_end"] == date(2026, 5, 4)
    assert values["planned_cost"] == Decimal("80.0")

    task = SimpleNamespace(
        planned_start=date(2026, 1, 2),
        planned_end=date(2026, 1, 8),
        progress_percent=40,
        planned_cost=Decimal("25"),
    )
    node = SimpleNamespace(code="2", name="Tâche", description=None, node_type="task", task=task)
    edited = WbsNodeDialog(node=node)
    qtbot.addWidget(edited)
    assert not edited.node_type.isEnabled()
    assert edited.values()["progress_percent"] == 40


def test_trace_link_dialog_validation_and_values(qtbot: Any, warnings: list[str]) -> None:
    dialog = TraceLinkDialog()
    qtbot.addWidget(dialog)
    dialog._validate()
    assert warnings[-1] == "Les deux identifiants sont obligatoires."
    dialog.source_id.setText(" source ")
    dialog.target_id.setText(" target ")
    dialog.relation.setCurrentText("verifies")
    dialog._validate()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.values()["relation_type"] == "verifies"
