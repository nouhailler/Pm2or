from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from sqlalchemy.orm import Session

from pm2.application.validation import ValidationService
from pm2.infrastructure.orm import (
    ProjectModel,
)
from pm2.ui.page_base import Page as Page
from pm2.ui.traceability_page import TraceabilityPage as TraceabilityPage


class ValidationPage(Page):
    def __init__(self, session: Session, project: ProjectModel) -> None:
        super().__init__()
        self.session, self.project = session, project
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel("Validation PM²")
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        heading.addStretch()
        self.filter = QComboBox()
        self.filter.addItem("Toutes les sévérités", "")
        for value in ("ERROR", "WARNING", "INFO"):
            self.filter.addItem(value, value)
        self.filter.currentIndexChanged.connect(self.reload)
        heading.addWidget(self.filter)
        layout.addLayout(heading)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Sévérité", "Code", "Entité", "Message"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.reload()

    def reload(self) -> None:
        problems = ValidationService(self.session).validate_project(self.project.id)
        severity = self.filter.currentData()
        problems = [problem for problem in problems if not severity or problem.severity == severity]
        self.table.setRowCount(len(problems))
        colors = {
            "ERROR": QColor("#f8d7da"),
            "WARNING": QColor("#fff3cd"),
            "INFO": QColor("#dbeafe"),
        }
        for row, problem in enumerate(problems):
            for column, value in enumerate(
                (problem.severity, problem.code, problem.entity, problem.message)
            ):
                item = QTableWidgetItem(str(value))
                item.setBackground(colors[problem.severity])
                self.table.setItem(row, column, item)


