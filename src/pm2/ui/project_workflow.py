from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.infrastructure.orm import GateReviewModel, PhaseModel, ProjectModel
from pm2.methodology.models import PM2Configuration

PHASE_PAGES = {
    "LAUNCH": "Lancement",
    "PLANNING": "Planification",
    "EXECUTION": "Exécution",
    "CLOSING": "Clôture",
}


class ProjectWorkflow(QGroupBox):
    """A navigation guide driven by the project's frozen methodology and live state."""

    navigate_requested = Signal(str)

    def __init__(
        self, session: Session, project: ProjectModel, methodology: PM2Configuration
    ) -> None:
        super().__init__("Votre parcours PM²")
        self.session, self.project, self.methodology = session, project, methodology
        self.phases = sorted(methodology.lifecycle.phases, key=lambda phase: phase.order)
        self.phase_buttons: dict[str, QPushButton] = {}
        self.gate_buttons: dict[str, QPushButton] = {}
        self.setStyleSheet(
            'QPushButton#workflowStep[current="true"] '
            "{ background: #255f85; color: white; border-color: #255f85; }"
        )
        root = QVBoxLayout(self)
        self.position = QLabel()
        self.position.setWordWrap(True)
        root.addWidget(self.position)
        self.route = QGridLayout()
        self.route_widgets: list[QPushButton] = []
        self.route_compact = True
        for index, phase in enumerate(self.phases):
            button = QPushButton()
            button.setObjectName("workflowStep")
            button.setMinimumHeight(70)
            button.setToolTip(f"Ouvrir l’assistant {phase.name}. {phase.purpose}")
            button.clicked.connect(
                lambda _checked=False, code=phase.code: self.navigate_requested.emit(
                    PHASE_PAGES[code]
                )
            )
            self.route_widgets.append(button)
            self.phase_buttons[phase.code] = button
            if index < len(self.phases) - 1:
                gate = next(
                    (gate for gate in methodology.gates if gate.from_phase == phase.code), None
                )
                if gate:
                    gate_button = QPushButton(f"→\n{gate.name}")
                    gate_button.setMinimumHeight(70)
                    gate_button.setToolTip(f"{gate.label} — ouvrir les revues de passage")
                    gate_button.clicked.connect(
                        lambda _checked=False: self.navigate_requested.emit("Gates")
                    )
                    self.route_widgets.append(gate_button)
                    self.gate_buttons[gate.code] = gate_button
        self.layout_route()
        root.addLayout(self.route)
        self.purpose = QLabel()
        self.purpose.setWordWrap(True)
        root.addWidget(self.purpose)
        self.activities = QLabel()
        self.activities.setWordWrap(True)
        root.addWidget(self.activities)
        actions = QHBoxLayout()
        self.continue_button = QPushButton()
        self.continue_button.setObjectName("primaryButton")
        self.continue_button.clicked.connect(self.open_current)
        actions.addWidget(self.continue_button)
        self.next_gate = QLabel()
        self.next_gate.setWordWrap(True)
        actions.addWidget(self.next_gate, 1)
        root.addLayout(actions)
        monitoring = QHBoxLayout()
        monitoring_label = QLabel(
            "À chaque étape : suivi des risques, problèmes, changements, dates et coûts."
        )
        monitoring_label.setWordWrap(True)
        monitoring.addWidget(monitoring_label, 1)
        for label, destination in (
            ("Registres", "Registres"),
            ("Planning", "Plan de travail"),
            ("Contrôles", "Validation"),
        ):
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, page=destination: self.navigate_requested.emit(page)
            )
            monitoring.addWidget(button)
        root.addLayout(monitoring)
        self.reload()

    def layout_route(self, available_width: int | None = None) -> None:
        if available_width is not None:
            self.route_compact = available_width < 780
        narrow = self.route_compact
        for button in self.route_widgets:
            self.route.removeWidget(button)
        for column in range(7):
            self.route.setColumnStretch(column, 0)
        for index, button in enumerate(self.route_widgets):
            row, column = (index // 2, index % 2) if narrow else (0, index)
            self.route.addWidget(button, row, column)
            self.route.setColumnStretch(column, 1 if column % 2 == 0 else 0)

    def open_current(self) -> None:
        destination = (
            "Documents"
            if self.project.status in {"CLOSED", "ARCHIVED"}
            else PHASE_PAGES.get(self.project.current_phase, "Projet")
        )
        self.navigate_requested.emit(destination)

    def reload(self) -> None:
        self.session.refresh(self.project)
        closed = self.project.status in {"CLOSED", "ARCHIVED"}
        phases = {
            phase.methodology_phase_code: phase.status
            for phase in self.session.scalars(
                select(PhaseModel).where(PhaseModel.project_id == self.project.id)
            )
        }
        reviews = {
            review.gate_code: review.status
            for review in self.session.scalars(
                select(GateReviewModel).where(GateReviewModel.project_id == self.project.id)
            )
        }
        for phase in self.phases:
            current = phase.code == self.project.current_phase and not closed
            state = (
                "Vous êtes ici"
                if current
                else {
                    "COMPLETED": "Terminée",
                    "IN_PROGRESS": "En cours",
                    "NOT_STARTED": "À venir",
                }.get(phases.get(phase.code, ""), "À venir")
            )
            button = self.phase_buttons[phase.code]
            button.setText(f"{phase.order} · {phase.name}\n{state}")
            button.setAccessibleName(f"{phase.name} : {state}. Ouvrir l’assistant.")
            button.setProperty("current", current)
            button.style().unpolish(button)
            button.style().polish(button)
        for gate in self.methodology.gates:
            if gate.code in self.gate_buttons:
                status = {
                    "APPROVED": "Approuvé",
                    "APPROVED_WITH_RESERVES": "Avec réserves",
                    "REJECTED": "Refusé",
                }.get(reviews.get(gate.code, ""), "À préparer")
                self.gate_buttons[gate.code].setText(f"→ {gate.name}\n{status}")
        phase = next(
            (phase for phase in self.phases if phase.code == self.project.current_phase), None
        )
        self.position.setText(
            "Projet clos — le parcours est terminé."
            if closed
            else f"Vous êtes ici : {phase.name if phase else self.project.current_phase}. Cliquez sur une étape pour ouvrir son assistant."
        )
        self.purpose.setText(
            "Conservez le bilan et l’archive du projet."
            if closed
            else (phase.purpose if phase else "")
        )
        activities = [
            activity.name
            for activity in self.methodology.activities
            if activity.phase == self.project.current_phase and not activity.optional
        ][:3]
        self.activities.setText(
            ""
            if closed
            else "Repères pour cette étape :\n" + "\n".join(f"• {name}" for name in activities)
        )
        self.activities.setVisible(not closed)
        gate = next(
            (
                gate
                for gate in self.methodology.gates
                if gate.from_phase == self.project.current_phase
            ),
            None,
        )
        self.next_gate.setText(
            ""
            if closed
            else (
                f"Prochain passage : {gate.name} · {gate.label}"
                if gate
                else "Après les contrôles : Projet → Fermer administrativement."
            )
        )
        self.continue_button.setText(
            "Ouvrir les documents" if closed else "Continuer l’étape actuelle"
        )
