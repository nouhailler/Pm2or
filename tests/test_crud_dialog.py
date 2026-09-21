from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

import pytest
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QMessageBox, QWidget
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import Column

from pm2.infrastructure.orm import Base, ProjectModel
from pm2.ui.crud import EntityEditDialog, entity_label


def test_entity_edit_dialog_builds_widgets_and_converts_project_values(
    qtbot: Any, session: Session, project: ProjectModel
) -> None:
    dialog = EntityEditDialog(session, "projects", project, project_id=project.id)
    qtbot.addWidget(dialog)
    assert "Modifier" in dialog.windowTitle()
    assert entity_label(project).startswith(project.reference)
    assert isinstance(dialog.widgets["outsourcing_required"], QCheckBox)
    assert isinstance(dialog.widgets["approved_budget"], QLineEdit)

    cast(QLineEdit, dialog.widgets["approved_budget"]).setText("123.45")
    values = dialog.values()
    assert values["approved_budget"] == Decimal("123.45")
    assert values["description"] == project.description


def test_entity_edit_dialog_handles_foreign_keys_invalid_values_and_widgets(
    qtbot: Any,
    session: Session,
    project: ProjectModel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialog = EntityEditDialog(session, "stakeholders", project_id=project.id)
    qtbot.addWidget(dialog)
    assert "person_id" in dialog.widgets
    assert cast(QComboBox, dialog.widgets["person_id"]).currentData() is None

    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _parent, _title, message: warnings.append(message)
    )
    dialog._validate()
    assert warnings and "obligatoire" in warnings[-1]

    cast(QLineEdit, dialog.widgets["name"]).setText("Partie prenante")
    dialog._validate()
    assert dialog.result() == dialog.DialogCode.Accepted

    dialog.widgets["name"] = QWidget()
    with pytest.raises(TypeError, match="non pris en charge"):
        dialog.values()

    numeric_column = cast(Column[Any], ProjectModel.__table__.columns["approved_budget"])
    with pytest.raises(ValueError, match="Valeur invalide"):
        EntityEditDialog._convert(numeric_column, "not-a-number")


def test_entity_label_falls_back_to_identity() -> None:
    entity = Base()
    entity.id = "12345678-identity"  # type: ignore[attr-defined]
    assert entity_label(entity) == "12345678-identity"
