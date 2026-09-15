from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


def _cell_text(table: QTableWidget, row: int, column: int) -> str:
    item = table.item(row, column)
    if item is not None:
        return item.text().strip()
    widget = table.cellWidget(row, column)
    if isinstance(widget, QComboBox):
        return widget.currentText().strip()
    if isinstance(widget, QAbstractButton):
        label = widget.text().strip()
        state = "Oui" if widget.isChecked() else "Non"
        return f"{label} : {state}" if label else state
    if isinstance(widget, (QLineEdit, QPlainTextEdit)):
        return (
            widget.text().strip()
            if isinstance(widget, QLineEdit)
            else widget.toPlainText().strip()
        )
    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
        return widget.text().strip()
    return ""


def _column_label(table: QTableWidget, column: int) -> str:
    item = table.horizontalHeaderItem(column)
    label = item.text().strip() if item is not None else ""
    return label or f"Colonne {column + 1}"


def _context_title(table: QTableWidget) -> str:
    explicit = str(table.property("rowDetailTitle") or "").strip()
    if explicit:
        return explicit
    parent: QWidget | None = table.parentWidget()
    while parent is not None:
        if isinstance(parent, QTabWidget):
            for index in range(parent.count()):
                page = parent.widget(index)
                if page is table or page.isAncestorOf(table):
                    label = parent.tabText(index).replace("&", "").strip()
                    if label:
                        return label
        headings = [
            label
            for label in parent.findChildren(QLabel)
            if label.objectName() in {"pageTitle", "sectionTitle"} and label.text().strip()
        ]
        if headings:
            return headings[0].text().strip()
        parent = parent.parentWidget()
    return "Ligne du tableau"


def show_row_detail(table: QTableWidget, row: int) -> None:
    if row < 0 or row >= table.rowCount():
        return
    table.selectRow(row)
    context = _context_title(table)
    dialog = QDialog(table)
    dialog.setWindowTitle(f"Détail — {context}")
    dialog.setProperty("sourceRow", row)
    dialog.resize(720, min(760, 230 + table.columnCount() * 54))
    layout = QVBoxLayout(dialog)
    title = QLabel(context)
    title.setObjectName("pageTitle")
    subtitle = QLabel(f"Ligne {row + 1} · {table.columnCount()} champ(s)")
    subtitle.setObjectName("pageSubtitle")
    layout.addWidget(title)
    layout.addWidget(subtitle)

    details = QTableWidget(table.columnCount(), 2, dialog)
    details.setObjectName("rowDetailFields")
    details.setProperty("pm2DisableRowDetail", True)
    details.setHorizontalHeaderLabels(["Champ", "Valeur"])
    details.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    details.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    details.setWordWrap(True)
    details.verticalHeader().setVisible(False)
    details.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    details.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    for column in range(table.columnCount()):
        label_item = QTableWidgetItem(_column_label(table, column))
        details.setItem(column, 0, label_item)
        details.setItem(column, 1, QTableWidgetItem(_cell_text(table, row, column) or "—"))
    details.resizeRowsToContents()
    layout.addWidget(details, 1)

    close = QPushButton("Fermer")
    close.clicked.connect(dialog.accept)
    layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
    dialog.exec()


def enable_row_details(root: QWidget) -> None:
    """Enable a consistent detail window on every table below *root*."""
    tables = ([root] if isinstance(root, QTableWidget) else []) + root.findChildren(QTableWidget)
    for table in tables:
        if table.property("pm2DisableRowDetail") or table.property("pm2CustomRowDetail"):
            continue
        if table.property("pm2RowDetailEnabled"):
            continue
        table.setProperty("pm2RowDetailEnabled", True)
        table.setCursor(Qt.CursorShape.PointingHandCursor)
        if not table.toolTip():
            table.setToolTip(
                "Double-cliquez sur une ligne, ou sélectionnez-la et appuyez sur Entrée, "
                "pour afficher toutes ses informations."
            )
        table.itemActivated.connect(
            lambda item, source=table: show_row_detail(source, item.row())
        )


class _RowDetailEventFilter(QObject):
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show and isinstance(watched, QWidget):
            enable_row_details(watched)
        return False


def install_row_detail_support(application: QApplication) -> None:
    if getattr(application, "_pm2_row_detail_filter", None) is not None:
        return
    event_filter = _RowDetailEventFilter(application)
    application.installEventFilter(event_filter)
    application._pm2_row_detail_filter = event_filter  # type: ignore[attr-defined]
