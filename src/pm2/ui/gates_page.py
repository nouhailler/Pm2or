from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pm2.application.services import (
    GateService,
)
from pm2.domain.enums import GateDecisionType
from pm2.infrastructure.orm import (
    ProjectModel,
)
from pm2.methodology.models import PM2Configuration
from pm2.ui.page_base import Page as Page
from pm2.ui.traceability_page import TraceabilityPage as TraceabilityPage


class GatesPage(Page):
    def __init__(
        self, session: Session, project: ProjectModel, methodology: PM2Configuration
    ) -> None:
        super().__init__()
        self.session, self.project, self.methodology = session, project, methodology
        self.service = GateService(session, methodology)
        layout = QVBoxLayout(self)
        title = QLabel("Readiness gates")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.tabs = QTabWidget()
        self.checkboxes: dict[str, list[tuple[QCheckBox, str]]] = {}
        self.status_labels: dict[str, QLabel] = {}
        for definition in methodology.gates:
            widget = QWidget()
            gate_layout = QVBoxLayout(widget)
            summary = QLabel(f"{definition.label}\n{definition.from_phase} → {definition.to_phase}")
            summary.setObjectName("sectionTitle")
            gate_layout.addWidget(summary)
            status = QLabel()
            self.status_labels[definition.code] = status
            gate_layout.addWidget(status)
            group = QGroupBox("Checklist")
            group_layout = QVBoxLayout(group)
            review = self.service.get_or_create(project.id, definition.code)
            boxes: list[tuple[QCheckBox, str]] = []
            for item in self.service.checklist(review.id):
                box = QCheckBox(
                    f"{item.item_code} — {item.description}" + (" *" if item.required else "")
                )
                box.setChecked(item.satisfied)
                box.stateChanged.connect(
                    lambda state, item_id=item.id: self._set_item(item_id, bool(state))
                )
                group_layout.addWidget(box)
                boxes.append((box, item.id))
            self.checkboxes[definition.code] = boxes
            gate_layout.addWidget(group)
            action_layout = QHBoxLayout()
            decide = QPushButton("Enregistrer une décision")
            decide.clicked.connect(lambda _checked=False, code=definition.code: self._decide(code))
            action_layout.addStretch()
            action_layout.addWidget(decide)
            gate_layout.addLayout(action_layout)
            gate_layout.addStretch()
            self.tabs.addTab(widget, definition.name)
        self.session.commit()
        layout.addWidget(self.tabs)
        self.reload()

    def _set_item(self, item_id: str, satisfied: bool) -> None:
        try:
            self.service.set_item(item_id, satisfied)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Mise à jour impossible", str(exc))

    def _decide(self, gate_code: str) -> None:
        review = self.service.get_or_create(self.project.id, gate_code)
        options = [item.value for item in GateDecisionType]
        decision, ok = QInputDialog.getItem(self, "Décision de gate", "Décision", options, 0, False)
        if not ok:
            return
        decider, ok = QInputDialog.getText(self, "Décision de gate", "Décideur *")
        if not ok:
            return
        try:
            self.service.decide(review.id, decision, decider)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Décision refusée", str(exc))

    def reload(self) -> None:
        self.session.refresh(self.project)
        for definition in self.methodology.gates:
            review = self.service.get_or_create(self.project.id, definition.code)
            self.status_labels[definition.code].setText(
                f"Phase actuelle : {self.project.current_phase} · Statut : {review.status}"
            )
            for box, item_id in self.checkboxes[definition.code]:
                item = self.session.get(
                    __import__(
                        "pm2.infrastructure.orm", fromlist=["GateChecklistItemModel"]
                    ).GateChecklistItemModel,
                    item_id,
                )
                if item:
                    box.blockSignals(True)
                    box.setChecked(item.satisfied)
                    box.blockSignals(False)

    def focus_section(self, gate_code: str) -> None:
        codes = [definition.code for definition in self.methodology.gates]
        if gate_code in codes:
            self.tabs.setCurrentIndex(codes.index(gate_code))

