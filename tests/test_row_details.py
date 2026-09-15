from pathlib import Path

from PySide6.QtWidgets import QDialog, QTableWidget, QTableWidgetItem

from pm2.config import AppPaths
from pm2.ui.main_window import MainWindow
from pm2.ui.row_details import enable_row_details


def test_table_row_opens_generic_detail_window(qtbot, monkeypatch) -> None:
    table = QTableWidget(1, 3)
    table.setHorizontalHeaderLabels(["Code", "Titre", "Statut"])
    table.setProperty("rowDetailTitle", "Risques")
    for column, value in enumerate(("R-01", "Retard du fournisseur", "OPEN")):
        table.setItem(0, column, QTableWidgetItem(value))
    qtbot.addWidget(table)
    dialogs: list[QDialog] = []

    def capture(dialog: QDialog) -> QDialog.DialogCode:
        dialogs.append(dialog)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", capture)
    enable_row_details(table)

    table.itemActivated.emit(table.item(0, 0))

    assert table.currentRow() == 0
    assert len(dialogs) == 1
    assert dialogs[0].windowTitle() == "Détail — Risques"
    details = dialogs[0].findChild(QTableWidget, "rowDetailFields")
    assert details is not None
    assert [details.item(row, 0).text() for row in range(3)] == ["Code", "Titre", "Statut"]
    assert [details.item(row, 1).text() for row in range(3)] == [
        "R-01",
        "Retard du fournisseur",
        "OPEN",
    ]


def test_custom_and_internal_tables_are_not_overridden(qtbot) -> None:
    custom = QTableWidget(1, 1)
    custom.setProperty("pm2CustomRowDetail", True)
    internal = QTableWidget(1, 1)
    internal.setProperty("pm2DisableRowDetail", True)
    qtbot.addWidget(custom)
    qtbot.addWidget(internal)

    enable_row_details(custom)
    enable_row_details(internal)

    assert not custom.property("pm2RowDetailEnabled")
    assert not internal.property("pm2RowDetailEnabled")


def test_every_application_table_has_a_detail_handler(
    qtbot, context, project, tmp_path: Path
) -> None:
    paths = AppPaths(
        tmp_path,
        context.database.path,
        tmp_path / "app.log",
        tmp_path / "recent.json",
    )
    window = MainWindow(context, paths)
    qtbot.addWidget(window)
    tables = window.findChildren(QTableWidget)

    assert len(tables) >= 20
    assert all(
        table.property("pm2RowDetailEnabled") or table.property("pm2CustomRowDetail")
        for table in tables
    )
