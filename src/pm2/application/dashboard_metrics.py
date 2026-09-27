from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pm2.application.traceability import TraceabilityService as TraceabilityService
from pm2.application.validation import ValidationService
from pm2.infrastructure.orm import (
    ChangeModel,
    DecisionModel,
    DeliverableModel,
    DocumentModel,
    IssueModel,
    ProjectModel,
    ProjectRoleAssignmentModel,
    QualityControlModel,
    QualityFindingModel,
    RequirementModel,
    RiskActionModel,
    RiskModel,
    TaskModel,
    WbsNodeModel,
)


@dataclass(frozen=True, slots=True)
class CockpitKpis:
    progress_percent: int
    budget_percent: int | None
    budget_actual: float
    budget_approved: float
    schedule_variance_days: int | None
    risks: int
    issues: int
    changes: int
    decisions: int


@dataclass(frozen=True, slots=True)
class HealthIndicator:
    name: str
    status: str
    detail: str
    page: str
    section: str = ""


@dataclass(frozen=True, slots=True)
class CockpitAction:
    label: str
    detail: str
    severity: str
    page: str
    section: str = ""


@dataclass(frozen=True, slots=True)
class ProjectCockpit:
    kpis: CockpitKpis
    health: tuple[HealthIndicator, ...]
    actions: tuple[CockpitAction, ...]


class DashboardService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def cockpit(self, project_id: str, *, today: date | None = None) -> ProjectCockpit:
        today = today or date.today()
        project = self.session.get(ProjectModel, project_id)
        if project is None:
            raise LookupError(f"Projet introuvable : {project_id}")
        tasks = list(
            self.session.scalars(
                select(TaskModel).join(WbsNodeModel).where(WbsNodeModel.project_id == project_id)
            )
        )
        progress = round(sum(task.progress_percent for task in tasks) / len(tasks)) if tasks else 0
        actual_cost = float(sum((task.actual_cost for task in tasks), start=0))
        approved_budget = float(project.approved_budget)
        budget_percent = (
            round(actual_cost * 100 / approved_budget) if approved_budget > 0 else None
        )
        overdue_delays = [
            (today - task.planned_end).days
            for task in tasks
            if task.planned_end and task.planned_end < today and task.progress_percent < 100
        ]
        schedule_variance = max(overdue_delays, default=0) if tasks else None
        if project.target_end_date:
            actual_ends = [task.actual_end for task in tasks if task.actual_end]
            if actual_ends:
                schedule_variance = max(
                    schedule_variance or 0,
                    (max(actual_ends) - project.target_end_date).days,
                )

        risks = self._rows(
            RiskModel,
            RiskModel.project_id == project_id,
            RiskModel.status != "CLOSED",
        )
        issues = self._rows(
            IssueModel,
            IssueModel.project_id == project_id,
            IssueModel.status != "CLOSED",
        )
        changes = self._rows(
            ChangeModel,
            ChangeModel.project_id == project_id,
            ~ChangeModel.status.in_(["CLOSED", "REJECTED"]),
        )
        decisions = self._rows(
            DecisionModel,
            DecisionModel.project_id == project_id,
            DecisionModel.status != "CLOSED",
        )
        kpis = CockpitKpis(
            progress,
            budget_percent,
            actual_cost,
            approved_budget,
            schedule_variance,
            len(risks),
            len(issues),
            len(changes),
            len(decisions),
        )
        return ProjectCockpit(
            kpis=kpis,
            health=self._health(project, kpis, risks, today),
            actions=self._actions(project_id, changes, decisions, today),
        )

    def _health(
        self,
        project: ProjectModel,
        kpis: CockpitKpis,
        risks: list[Any],
        today: date,
    ) -> tuple[HealthIndicator, ...]:
        problems = ValidationService(self.session).validate_project(project.id)
        governance_errors = sum(
            problem.severity == "ERROR" and problem.entity == "governance"
            for problem in problems
        )
        governance_warnings = sum(
            problem.severity == "WARNING" and problem.entity == "governance"
            for problem in problems
        )
        active_roles = self._count(
            ProjectRoleAssignmentModel,
            ProjectRoleAssignmentModel.project_id == project.id,
            ProjectRoleAssignmentModel.active.is_(True),
        )
        governance = self._indicator(
            "Gouvernance",
            "RED" if governance_errors else "ORANGE" if governance_warnings else "GREEN",
            f"{active_roles} rôle(s) actif(s)",
            "Gouvernance",
        )
        delay = kpis.schedule_variance_days
        planning = self._indicator(
            "Planning",
            "GRAY" if delay is None else "RED" if delay > 14 else "ORANGE" if delay > 0 else "GREEN",
            "Aucun planning" if delay is None else f"Dérive maximale : {delay:+d} j",
            "Plan de travail",
        )
        critical_risks = sum(
            bool(risk.score and risk.score >= 15) or bool(risk.due_date and risk.due_date < today)
            for risk in risks
        )
        risk_health = self._indicator(
            "Risques",
            "RED" if critical_risks >= 2 else "ORANGE" if critical_risks else "GREEN",
            f"{critical_risks} critique(s) ou échu(s)",
            "Registres",
            "risk",
        )
        budget = self._indicator(
            "Budget",
            "GRAY"
            if kpis.budget_percent is None
            else "RED"
            if kpis.budget_percent > 100
            or kpis.budget_percent - kpis.progress_percent > 10
            else "ORANGE"
            if kpis.budget_percent >= 85
            or kpis.budget_percent - kpis.progress_percent > 5
            else "GREEN",
            "Budget non défini"
            if kpis.budget_percent is None
            else f"{kpis.budget_percent} % consommé",
            "Projet",
        )
        open_findings = self._count(
            QualityFindingModel,
            QualityFindingModel.quality_control_id.in_(
                select(QualityControlModel.id).where(
                    QualityControlModel.project_id == project.id
                )
            ),
            QualityFindingModel.status != "CLOSED",
        )
        quality_controls = self._count(
            QualityControlModel, QualityControlModel.project_id == project.id
        )
        quality_errors = sum(
            problem.severity == "ERROR" and problem.entity == "quality_action"
            for problem in problems
        )
        quality = self._indicator(
            "Qualité",
            "GRAY"
            if not quality_controls
            else "RED"
            if quality_errors
            else "ORANGE"
            if open_findings
            else "GREEN",
            "Aucun contrôle qualité"
            if not quality_controls
            else f"{open_findings} constat(s) ouvert(s)",
            "Données métier",
            "quality",
        )
        return governance, planning, risk_health, budget, quality

    def _actions(
        self,
        project_id: str,
        changes: list[Any],
        decisions: list[Any],
        today: date,
    ) -> tuple[CockpitAction, ...]:
        actions: list[CockpitAction] = []
        for change in changes:
            if change.status == "APPROVAL":
                actions.append(
                    CockpitAction(
                        change.code,
                        "Décision d’approbation attendue",
                        "HIGH",
                        "Registres",
                        "change",
                    )
                )
        risk_actions = self.session.execute(
            select(RiskActionModel, RiskModel)
            .join(RiskModel, RiskActionModel.risk_id == RiskModel.id)
            .where(
                RiskModel.project_id == project_id,
                RiskActionModel.status != "CLOSED",
                RiskActionModel.due_date < today,
            )
            .order_by(RiskActionModel.due_date)
        ).all()
        for action, risk in risk_actions:
            actions.append(
                CockpitAction(
                    risk.code,
                    f"Mitigation échue : {action.title}",
                    "HIGH",
                    "Registres",
                    "risk",
                )
            )
        deliverables = self._rows(
            DeliverableModel,
            DeliverableModel.project_id == project_id,
            DeliverableModel.status == "READY_FOR_ACCEPTANCE",
        )
        for deliverable in deliverables:
            actions.append(
                CockpitAction(
                    deliverable.code,
                    "Acceptation requise",
                    "HIGH",
                    "Données métier",
                    "deliverables",
                )
            )
        for decision in decisions:
            if decision.status in {"OPEN", "ANALYSIS"}:
                actions.append(
                    CockpitAction(
                        decision.code,
                        "Décision à instruire",
                        "MEDIUM",
                        "Registres",
                        "decision",
                    )
                )
        overdue_issues = self._rows(
            IssueModel,
            IssueModel.project_id == project_id,
            IssueModel.status != "CLOSED",
            IssueModel.due_date < today,
        )
        for issue in overdue_issues:
            actions.append(
                CockpitAction(
                    issue.code,
                    "Problème arrivé à échéance",
                    "MEDIUM",
                    "Registres",
                    "issue",
                )
            )
        priority = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        return tuple(sorted(actions, key=lambda item: (priority[item.severity], item.label))[:8])

    @staticmethod
    def _indicator(
        name: str, status: str, detail: str, page: str, section: str = ""
    ) -> HealthIndicator:
        return HealthIndicator(name, status, detail, page, section)

    def _rows(self, model: Any, *conditions: Any) -> list[Any]:
        return list(self.session.scalars(select(model).where(*conditions)))

    def _count(self, model: Any, *conditions: Any) -> int:
        return int(
            self.session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
        )


def project_counts(session: Session, project_id: str) -> dict[str, int | float]:
    def count(model: Any, *conditions: Any) -> int:
        return int(session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)

    tasks = session.scalars(
        select(TaskModel).join(WbsNodeModel).where(WbsNodeModel.project_id == project_id)
    ).all()
    progress = sum(task.progress_percent for task in tasks) / len(tasks) if tasks else 0.0
    return {
        "risks": count(RiskModel, RiskModel.project_id == project_id, RiskModel.status != "CLOSED"),
        "issues": count(
            IssueModel, IssueModel.project_id == project_id, IssueModel.status != "CLOSED"
        ),
        "changes": count(
            ChangeModel,
            ChangeModel.project_id == project_id,
            ~ChangeModel.status.in_(["CLOSED", "REJECTED"]),
        ),
        "deliverables": count(DeliverableModel, DeliverableModel.project_id == project_id),
        "requirements": count(RequirementModel, RequirementModel.project_id == project_id),
        "documents": count(DocumentModel, DocumentModel.project_id == project_id),
        "progress": round(progress, 1),
    }
