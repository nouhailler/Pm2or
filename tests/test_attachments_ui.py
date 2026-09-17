from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
from sqlalchemy.orm import Session

from pm2.infrastructure.orm import ProjectModel
from pm2.ui.attachments_page import AttachmentsPage


def test_attachment_page_add_open_and_remove(
    qtbot: Any,
    session: Session,
    project: ProjectModel,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    source = tmp_path / "preuve.txt"
    source.write_text("preuve", encoding="utf-8")
    page = AttachmentsPage(session, project, tmp_path / "cache")
    qtbot.addWidget(page)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (str(source), ""))
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args: ("Justificatif", True))
    page._add()
    assert page.table.rowCount() == 1
    page.table.selectRow(0)

    opened: list[QUrl] = []
    monkeypatch.setattr(
        "pm2.ui.attachments_page.QDesktopServices.openUrl",
        lambda url: (opened.append(url), True)[1],
    )
    page._open()
    assert opened and Path(opened[0].toLocalFile()).read_text(encoding="utf-8") == "preuve"

    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes
    )
    page._remove()
    assert page.table.rowCount() == 0


def test_attachment_page_handles_cancel_selection_and_errors(
    qtbot: Any,
    session: Session,
    project: ProjectModel,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    page = AttachmentsPage(session, project, tmp_path / "cache")
    qtbot.addWidget(page)
    information: list[str] = []
    errors: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: information.append("info"))
    monkeypatch.setattr(QMessageBox, "critical", lambda *_args: errors.append(str(_args[-1])))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: ("", ""))
    page._add()
    page._open()
    page._remove()
    assert information == ["info"]
    assert page._selected_id() is None

    source = tmp_path / "preuve.txt"
    source.write_text("preuve", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (str(source), ""))
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args: ("", False))
    page._add()
    assert page.table.rowCount() == 0

    monkeypatch.setattr(QInputDialog, "getText", lambda *_args: ("", True))
    monkeypatch.setattr(page.service, "add", lambda *_args: (_ for _ in ()).throw(OSError("denied")))
    page._add()
    assert errors == ["denied"]
