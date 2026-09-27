from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pm2.application.validation import ComplianceReport, ValidationService
from pm2.domain.entities import ValidationProblem
from pm2.infrastructure.orm import ProjectModel
from pm2.methodology.models import PM2Configuration
from pm2.ui.page_base import Page


class ValidationPage(Page):
    navigate_requested = Signal(str)
    correction_requested = Signal(str, str)

    def __init__(
        self,
        session: Session,
        project: ProjectModel,
        methodology: PM2Configuration | None = None,
    ) -> None:
        super().__init__()
        self.session = session
        self.project = project
        self.methodology = methodology
        self.service = ValidationService(session)
        self.report: ComplianceReport | None = None

        outer = QVBoxLayout(self)
        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Centre de conformité PM²")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Mesurez la préparation du projet, corrigez les écarts et sécurisez les gates."
        )
        subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        heading.addLayout(title_box)
        heading.addStretch()
        recalculate = QPushButton("Recalculer")
        recalculate.setObjectName("primaryButton")
        recalculate.clicked.connect(self.reload)
        heading.addWidget(recalculate)
        outer.addLayout(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        root = QVBoxLayout(content)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        project_group = QGroupBox("Conformité du projet")
        project_layout = QVBoxLayout(project_group)
        score_line = QHBoxLayout()
        self.score_label = QLabel("—")
        self.score_label.setObjectName("metricValue")
        self.score_label.setMinimumWidth(90)
        self.score_progress = QProgressBar()
        self.score_progress.setRange(0, 100)
        self.score_progress.setTextVisible(True)
        score_line.addWidget(self.score_label)
        score_line.addWidget(self.score_progress, 1)
        project_layout.addLayout(score_line)
        self.phase_table = QTableWidget(0, 5)
        self.phase_table.setHorizontalHeaderLabels(
            ["Domaine", "Progression", "Statut", "Erreurs", "Avertissements"]
        )
        self.phase_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.phase_table.setProperty("pm2CustomRowDetail", True)
        self.phase_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.phase_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        project_layout.addWidget(self.phase_table)
        root.addWidget(project_group)

        gates_group = QGroupBox("Readiness gates")
        gates_layout = QVBoxLayout(gates_group)
        self.gate_tabs = QTabWidget()
        gates_layout.addWidget(self.gate_tabs)
        root.addWidget(gates_group)

        findings_group = QGroupBox("Écarts et actions correctives")
        findings_layout = QVBoxLayout(findings_group)
        toolbar = QHBoxLayout()
        self.summary = QLabel()
        self.summary.setObjectName("pageSubtitle")
        toolbar.addWidget(self.summary)
        toolbar.addStretch()
        self.filter = QComboBox()
        self.filter.addItem("Toutes les sévérités", "")
        for value, label in (
            ("ERROR", "Erreurs"),
            ("WARNING", "Avertissements"),
            ("INFO", "Informations"),
        ):
            self.filter.addItem(label, value)
        self.filter.currentIndexChanged.connect(self._reload_findings)
        toolbar.addWidget(self.filter)
        findings_layout.addLayout(toolbar)
        self.findings = QTableWidget(0, 5)
        self.findings.setHorizontalHeaderLabels(
            ["Sévérité", "Code", "Constat", "Nombre", "Action corrective"]
        )
        self.findings.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.findings.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.findings.setProperty("pm2CustomRowDetail", True)
        self.findings.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.findings.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.findings.doubleClicked.connect(self._open_selected_finding)
        findings_layout.addWidget(self.findings)
        root.addWidget(findings_group)
        self.reload()

    def reload(self) -> None:
        self.report = self.service.compliance_report(self.project.id, self.methodology)
        self.score_label.setText(f"{self.report.score} %")
        self.score_progress.setValue(self.report.score)
        self._reload_phases()
        self._reload_gates()
        self._reload_findings()

    def _reload_phases(self) -> None:
        assert self.report is not None
        self.phase_table.setRowCount(len(self.report.phases))
        for row, phase in enumerate(self.report.phases):
            score_text = "— Non commencée" if phase.score is None else f"{phase.score} %"
            values = (phase.name, score_text, phase.status, phase.errors, phase.warnings)
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column in {1, 3, 4}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.phase_table.setItem(row, column, item)

    def _reload_gates(self) -> None:
        assert self.report is not None
        while self.gate_tabs.count():
            widget = self.gate_tabs.widget(0)
            self.gate_tabs.removeTab(0)
            if widget is not None:
                widget.deleteLater()
        for gate in self.report.gates:
            page = QWidget()
            layout = QVBoxLayout(page)
            header = QHBoxLayout()
            status = QLabel(f"{gate.label} · {gate.score} % · {gate.status}")
            status.setObjectName("sectionTitle")
            header.addWidget(status)
            header.addStretch()
            open_gate = QPushButton("Examiner le gate")
            open_gate.clicked.connect(
                lambda _checked=False, code=gate.code: self._request_correction(
                    "Gates", code
                )
            )
            header.addWidget(open_gate)
            layout.addLayout(header)
            table = QTableWidget(len(gate.checks), 3)
            table.setHorizontalHeaderLabels(["État", "Contrôle", "Exigence"])
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setProperty("pm2CustomRowDetail", True)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            for row, check in enumerate(gate.checks):
                state = "✓" if check.satisfied else "✗" if check.required else "⚠"
                for column, value in enumerate(
                    (state, check.description, "Obligatoire" if check.required else "Optionnel")
                ):
                    item = QTableWidgetItem(value)
                    if column == 0:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row, column, item)
            layout.addWidget(table)
            self.gate_tabs.addTab(page, f"{gate.name} · {gate.status}")

    def _reload_findings(self) -> None:
        if self.report is None:
            return
        severity = str(self.filter.currentData() or "")
        groups: dict[tuple[str, str, str], list[ValidationProblem]] = defaultdict(list)
        for problem in self.report.problems:
            if not severity or problem.severity == severity:
                groups[(problem.severity, problem.code, problem.message)].append(problem)
        rows = list(groups.values())
        self.findings.setRowCount(len(rows))
        colors = {
            "ERROR": QColor("#f8d7da"),
            "WARNING": QColor("#fff3cd"),
            "INFO": QColor("#dbeafe"),
        }
        errors = sum(problem.severity == "ERROR" for problem in self.report.problems)
        warnings = sum(problem.severity == "WARNING" for problem in self.report.problems)
        self.summary.setText(f"{errors} erreur(s) · {warnings} avertissement(s)")
        for row, problems in enumerate(rows):
            problem = problems[0]
            for column, value in enumerate(
                (problem.severity, problem.code, problem.message, len(problems))
            ):
                item = QTableWidgetItem(str(value))
                item.setBackground(colors[problem.severity])
                item.setData(Qt.ItemDataRole.UserRole, problem)
                self.findings.setItem(row, column, item)
            action = QPushButton(self._action_label(problem))
            target = self._target_page(problem)
            section = self._target_section(problem)
            action.clicked.connect(
                lambda _checked=False, destination=target, target_section=section:
                self._request_correction(destination, target_section)
            )
            self.findings.setCellWidget(row, 4, action)

    def _open_selected_finding(self) -> None:
        item = self.findings.item(self.findings.currentRow(), 0)
        if item is None:
            return
        problem = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(problem, ValidationProblem):
            self._request_correction(
                self._target_page(problem), self._target_section(problem)
            )

    def _request_correction(self, page: str, section: str) -> None:
        self.navigate_requested.emit(page)
        self.correction_requested.emit(page, section)

    @staticmethod
    def _target_page(problem: ValidationProblem) -> str:
        pages = {
            "project": "Projet",
            "governance": "Gouvernance",
            "task": "Plan de travail",
            "requirement": "Données métier",
            "deliverable": "Données métier",
            "acceptance": "Données métier",
            "acceptance_test": "Données métier",
            "quality_action": "Données métier",
            "risk": "Registres",
            "issue": "Registres",
            "change": "Registres",
            "decision": "Registres",
            "gate": "Gates",
            "traceability": "Traçabilité",
        }
        return pages.get(problem.entity, "Catalogue")

    @staticmethod
    def _target_section(problem: ValidationProblem) -> str:
        if problem.code == "PM2-DEL-003":
            return "criteria"
        sections = {
            "requirement": "requirements",
            "deliverable": "deliverables",
            "acceptance": "criteria",
            "acceptance_test": "tests",
            "quality_action": "quality",
            "risk": "risk",
            "issue": "issue",
            "decision": "decision",
            "change": "change",
        }
        return sections.get(problem.entity, "")

    @staticmethod
    def _action_label(problem: ValidationProblem) -> str:
        labels = {
            "PM2-DEL-003": "Créer les critères",
            "PM2-REQ-003": "Relier les tests",
            "PM2-TRACE-001": "Créer une relation",
            "PM2-GATE-001": "Examiner le gate",
        }
        return labels.get(problem.code, "Corriger")
