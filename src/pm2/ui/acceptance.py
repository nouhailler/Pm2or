from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.services import AcceptanceService, WorkflowService
from pm2.infrastructure.orm import (
    AcceptanceCriterionModel,
    AcceptanceModel,
    AcceptanceTestModel,
    DeliverableModel,
    ProjectModel,
)


class AcceptanceExecutionWidget(QWidget):
    changed = Signal()

    def __init__(self, session: Session, project: ProjectModel) -> None:
        super().__init__()
        self.session, self.project = session, project
        root = QVBoxLayout(self)
        title = QLabel("Exécution des tests & acceptation finale")
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        toolbar = QHBoxLayout()
        run_test = QPushButton("Enregistrer le résultat du test")
        run_test.clicked.connect(self.record_test)
        accept = QPushButton("Accepter le livrable sélectionné")
        accept.setObjectName("primaryButton")
        accept.clicked.connect(self.accept_deliverable)
        toolbar.addWidget(run_test)
        toolbar.addWidget(accept)
        toolbar.addStretch()
        root.addLayout(toolbar)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.deliverables = QTableWidget(0, 5)
        self.deliverables.setHorizontalHeaderLabels(
            ["Code", "Livrable", "Workflow", "Acceptation", "Responsable"]
        )
        self.deliverables.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.deliverables.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.deliverables.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        splitter.addWidget(self.deliverables)
        self.tests = QTableWidget(0, 6)
        self.tests.setHorizontalHeaderLabels(
            ["Test", "Critère", "Livrable", "Résultat attendu", "Résultat réel", "Verdict"]
        )
        self.tests.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tests.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tests.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        splitter.addWidget(self.tests)
        root.addWidget(splitter)
        self.history = QPlainTextEdit()
        self.history.setReadOnly(True)
        self.history.setMaximumHeight(100)
        root.addWidget(self.history)
        self.reload()

    def record_test(self) -> None:
        row = self.tests.currentRow()
        if row < 0:
            QMessageBox.information(self, "Test", "Sélectionnez un test d’acceptation.")
            return
        test_id = self.tests.item(row, 0).data(Qt.ItemDataRole.UserRole)
        outcome, ok = QInputDialog.getItem(
            self, "Résultat du test", "Verdict", ["PASSED", "FAILED", "BLOCKED"], 0, False
        )
        if not ok:
            return
        actual, ok = QInputDialog.getMultiLineText(
            self, "Résultat du test", "Résultat réel / preuve"
        )
        if not ok:
            return
        try:
            AcceptanceService(self.session).record_test(test_id, outcome, actual)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Résultat refusé", str(exc))

    def accept_deliverable(self) -> None:
        row = self.deliverables.currentRow()
        if row < 0:
            QMessageBox.information(self, "Acceptation", "Sélectionnez un livrable.")
            return
        deliverable_id = self.deliverables.item(row, 0).data(Qt.ItemDataRole.UserRole)
        deliverable = self.session.get(DeliverableModel, deliverable_id)
        if deliverable is None:
            return
        if deliverable.status != "READY_FOR_ACCEPTANCE":
            QMessageBox.warning(
                self,
                "État incorrect",
                "Le livrable doit être à l’état READY_FOR_ACCEPTANCE. Utilisez son workflow d’abord.",
            )
            return
        accepted_by, ok = QInputDialog.getText(self, "Acceptation finale", "Accepté par *")
        if not ok or not accepted_by.strip():
            return
        comments, ok = QInputDialog.getMultiLineText(
            self, "Acceptation finale", "Commentaires / réserves"
        )
        if not ok:
            return
        try:
            AcceptanceService(self.session).accept(
                deliverable.id, accepted_by.strip(), comments, final=True
            )
            WorkflowService(self.session).transition(
                "deliverable", deliverable.id, "ACCEPTED", actor=accepted_by.strip()
            )
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Acceptation refusée", str(exc))

    def reload(self) -> None:
        deliverables = self.session.scalars(
            select(DeliverableModel)
            .where(
                DeliverableModel.project_id == self.project.id,
                DeliverableModel.deleted_at.is_(None),
            )
            .order_by(DeliverableModel.code)
        ).all()
        self.deliverables.setRowCount(len(deliverables))
        for row, deliverable in enumerate(deliverables):
            values = (
                deliverable.code,
                deliverable.name,
                deliverable.status,
                deliverable.acceptance_status,
                deliverable.owner or "—",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, deliverable.id)
                self.deliverables.setItem(row, column, item)
        tests = self.session.execute(
            select(AcceptanceTestModel, AcceptanceCriterionModel, DeliverableModel)
            .join(
                AcceptanceCriterionModel,
                AcceptanceTestModel.criterion_id == AcceptanceCriterionModel.id,
            )
            .join(
                DeliverableModel,
                AcceptanceCriterionModel.deliverable_id == DeliverableModel.id,
            )
            .where(DeliverableModel.project_id == self.project.id)
        ).all()
        self.tests.setRowCount(len(tests))
        for row, (test, criterion, deliverable) in enumerate(tests):
            values = (
                test.code,
                criterion.code,
                deliverable.code,
                test.expected_result,
                test.actual_result,
                test.outcome or "PENDING",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, test.id)
                self.tests.setItem(row, column, item)
        acceptances = self.session.scalars(
            select(AcceptanceModel)
            .join(DeliverableModel)
            .where(DeliverableModel.project_id == self.project.id)
            .order_by(AcceptanceModel.accepted_at.desc())
        ).all()
        self.history.setPlainText(
            "\n".join(
                f"{item.accepted_at} — {item.status} par {item.accepted_by}: {item.comments}"
                for item in acceptances
            )
            or "Aucune acceptation enregistrée."
        )
