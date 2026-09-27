from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pm2.domain.entities import ValidationProblem
from pm2.infrastructure.orm import (
    AcceptanceCriterionModel,
    AcceptanceModel,
    AcceptanceTestModel,
    ChangeApprovalModel,
    ChangeModel,
    DecisionModel,
    DeliverableModel,
    GateChecklistItemModel,
    GateReviewModel,
    IssueModel,
    PhaseModel,
    ProjectModel,
    ProjectRoleAssignmentModel,
    QualityActionModel,
    QualityControlModel,
    QualityFindingModel,
    RequirementModel,
    RiskModel,
    TaskModel,
    TraceLinkModel,
    WbsNodeModel,
)
from pm2.methodology.models import PM2Configuration


@dataclass(frozen=True, slots=True)
class PhaseCompliance:
    code: str
    name: str
    score: int | None
    status: str
    errors: int
    warnings: int


@dataclass(frozen=True, slots=True)
class GateComplianceCheck:
    code: str
    description: str
    required: bool
    satisfied: bool


@dataclass(frozen=True, slots=True)
class GateCompliance:
    code: str
    name: str
    label: str
    status: str
    score: int
    checks: tuple[GateComplianceCheck, ...]


@dataclass(frozen=True, slots=True)
class ComplianceReport:
    score: int
    phases: tuple[PhaseCompliance, ...]
    gates: tuple[GateCompliance, ...]
    problems: tuple[ValidationProblem, ...]


class ValidationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def validate_project(self, project_id: str) -> list[ValidationProblem]:
        project = self.session.get(ProjectModel, project_id)
        if project is None:
            raise LookupError(f"Projet introuvable : {project_id}")
        problems: list[ValidationProblem] = []

        def add(
            code: str, severity: str, message: str, entity: str, entity_id: str | None = None
        ) -> None:
            problems.append(ValidationProblem(code, severity, message, entity, entity_id))

        if not project.name.strip() or not project.reference.strip():
            add(
                "PM2-PROJECT-001",
                "ERROR",
                "Le nom et la référence sont obligatoires.",
                "project",
                project.id,
            )
        if project.methodology_id != "pm2":
            add(
                "PM2-PROJECT-002",
                "ERROR",
                "La méthodologie PM² est obligatoire.",
                "project",
                project.id,
            )

        assignments = self.session.scalars(
            select(ProjectRoleAssignmentModel).where(
                ProjectRoleAssignmentModel.project_id == project_id,
                ProjectRoleAssignmentModel.active.is_(True),
            )
        ).all()
        pm_count = sum(item.role_code == "PM" for item in assignments)
        if pm_count == 0:
            add(
                "PM2-GOV-001",
                "ERROR",
                "Au moins un Chef de Projet (PM) actif doit être désigné.",
                "governance",
            )
        elif pm_count > 1:
            add(
                "PM2-GOV-002",
                "ERROR",
                "Un seul Chef de Projet (PM) actif est autorisé.",
                "governance",
            )
        if not any(item.role_code == "PO" for item in assignments):
            add(
                "PM2-GOV-003",
                "WARNING",
                "Aucun Porteur du Projet (PO) n'est désigné.",
                "governance",
            )
        if not any(item.role_code == "PSC" for item in assignments):
            add(
                "PM2-GOV-004",
                "WARNING",
                "Aucun Comité de Pilotage (PSC) n'est désigné.",
                "governance",
            )

        tasks = self.session.scalars(
            select(TaskModel).join(WbsNodeModel).where(WbsNodeModel.project_id == project_id)
        ).all()
        for task in tasks:
            if task.planned_start and task.planned_end and task.planned_end < task.planned_start:
                add("PM2-TASK-001", "ERROR", "Fin de tâche antérieure au début.", "task", task.id)
            if not 0 <= task.progress_percent <= 100:
                add("PM2-TASK-002", "ERROR", "Avancement hors de 0..100.", "task", task.id)
            if task.status == "COMPLETED" and (not task.actual_start or not task.actual_end):
                add(
                    "PM2-TASK-003", "WARNING", "Tâche terminée sans dates réelles.", "task", task.id
                )
            if task.owner_person_id is None:
                add("PM2-TASK-004", "WARNING", "Tâche sans responsable.", "task", task.id)

        deliverables = self.session.scalars(
            select(DeliverableModel).where(
                DeliverableModel.project_id == project_id,
                DeliverableModel.deleted_at.is_(None),
            )
        ).all()
        for deliverable in deliverables:
            criteria = int(
                self.session.scalar(
                    select(func.count())
                    .select_from(AcceptanceCriterionModel)
                    .where(AcceptanceCriterionModel.deliverable_id == deliverable.id)
                )
                or 0
            )
            acceptance = int(
                self.session.scalar(
                    select(func.count())
                    .select_from(AcceptanceModel)
                    .where(
                        AcceptanceModel.deliverable_id == deliverable.id,
                        AcceptanceModel.status == "ACCEPTED",
                    )
                )
                or 0
            )
            if not deliverable.owner:
                add(
                    "PM2-DEL-001",
                    "ERROR",
                    "Livrable sans responsable.",
                    "deliverable",
                    deliverable.id,
                )
            if not deliverable.planned_date:
                add(
                    "PM2-DEL-002",
                    "WARNING",
                    "Livrable sans date planifiée.",
                    "deliverable",
                    deliverable.id,
                )
            if not criteria:
                add(
                    "PM2-DEL-003",
                    "WARNING",
                    "Livrable sans critère d'acceptation.",
                    "deliverable",
                    deliverable.id,
                )
            if deliverable.status == "ACCEPTED" and not acceptance:
                add(
                    "PM2-DEL-004",
                    "ERROR",
                    "Livrable accepté sans enregistrement d'acceptation.",
                    "deliverable",
                    deliverable.id,
                )

        acceptance_tests = self.session.scalars(
            select(AcceptanceTestModel)
            .join(AcceptanceCriterionModel)
            .join(DeliverableModel)
            .where(DeliverableModel.project_id == project_id)
        ).all()
        for test in acceptance_tests:
            if not test.expected_result.strip() or not test.outcome:
                add(
                    "PM2-ACC-001",
                    "ERROR",
                    "Test d'acceptation sans résultat attendu ou sans verdict exécuté.",
                    "acceptance_test",
                    test.id,
                )
            criterion = self.session.get(AcceptanceCriterionModel, test.criterion_id)
            if criterion:
                linked_deliverable = self.session.get(DeliverableModel, criterion.deliverable_id)
                if (
                    linked_deliverable
                    and linked_deliverable.status == "ACCEPTED"
                    and test.outcome == "FAILED"
                ):
                    add(
                        "PM2-ACC-002",
                        "WARNING",
                        "Test échoué sur un livrable accepté.",
                        "acceptance_test",
                        test.id,
                    )

        requirements = self.session.scalars(
            select(RequirementModel).where(
                RequirementModel.project_id == project_id,
                RequirementModel.deleted_at.is_(None),
            )
        ).all()
        for requirement in requirements:
            if requirement.status in {"APPROVED", "IMPLEMENTED", "VERIFIED", "ACCEPTED"}:
                if not requirement.source or not requirement.priority:
                    add(
                        "PM2-REQ-001",
                        "ERROR",
                        "Exigence approuvée sans source ou priorité.",
                        "requirement",
                        requirement.id,
                    )
                if not requirement.verification_method:
                    add(
                        "PM2-REQ-002",
                        "WARNING",
                        "Exigence approuvée sans méthode de vérification.",
                        "requirement",
                        requirement.id,
                    )
            if requirement.status in {"VERIFIED", "ACCEPTED"} and not self._has_test_link(
                requirement.id
            ):
                add(
                    "PM2-REQ-003",
                    "ERROR",
                    "Exigence vérifiée sans test lié.",
                    "requirement",
                    requirement.id,
                )

        risks = self.session.scalars(
            select(RiskModel).where(RiskModel.project_id == project_id)
        ).all()
        for risk in risks:
            if risk.status != "OPEN" and (risk.probability is None or risk.impact is None):
                add(
                    "PM2-RISK-001",
                    "ERROR",
                    "Probabilité et impact requis avant évaluation.",
                    "risk",
                    risk.id,
                )
            if risk.probability and risk.impact and risk.score != risk.probability * risk.impact:
                add(
                    "PM2-RISK-002",
                    "ERROR",
                    "Le score doit être probabilité × impact.",
                    "risk",
                    risk.id,
                )
            if risk.score and risk.score >= 15 and (not risk.strategy.strip() or not risk.owner):
                add(
                    "PM2-RISK-003",
                    "WARNING",
                    "Risque élevé sans stratégie ou responsable.",
                    "risk",
                    risk.id,
                )
            if risk.tolerance_status == "BEYOND" and "escal" not in risk.strategy.lower():
                add(
                    "PM2-RISK-004",
                    "WARNING",
                    "Risque hors tolérance sans escalade.",
                    "risk",
                    risk.id,
                )

        issues = self.session.scalars(
            select(IssueModel).where(IssueModel.project_id == project_id)
        ).all()
        for issue in issues:
            if issue.status == "CLOSED" and not issue.resolution.strip():
                add(
                    "PM2-ISSUE-001", "ERROR", "Problème clôturé sans résolution.", "issue", issue.id
                )
            if issue.status != "CLOSED" and issue.due_date and issue.due_date < date.today():
                add("PM2-ISSUE-002", "WARNING", "Problème ouvert en retard.", "issue", issue.id)

        changes = self.session.scalars(
            select(ChangeModel).where(ChangeModel.project_id == project_id)
        ).all()
        for change in changes:
            has_impact = any(
                (
                    change.impact_scope,
                    change.impact_schedule,
                    change.impact_cost,
                    change.impact_quality,
                )
            )
            if (
                change.status in {"APPROVED", "IMPLEMENTING", "VERIFIED", "CLOSED"}
                and not has_impact
            ):
                add(
                    "PM2-CHANGE-001",
                    "ERROR",
                    "Modification approuvée sans analyse d'impact.",
                    "change",
                    change.id,
                )
            if change.status == "IMPLEMENTING":
                approved = self.session.scalar(
                    select(ChangeApprovalModel.id).where(
                        ChangeApprovalModel.change_id == change.id,
                        ChangeApprovalModel.decision == "APPROVED",
                    )
                )
                if not approved:
                    add(
                        "PM2-CHANGE-002",
                        "ERROR",
                        "Modification en implémentation sans approbation.",
                        "change",
                        change.id,
                    )

        actions = self.session.scalars(
            select(QualityActionModel)
            .join(QualityFindingModel, QualityActionModel.finding_id == QualityFindingModel.id)
            .join(
                QualityControlModel,
                QualityFindingModel.quality_control_id == QualityControlModel.id,
            )
            .where(QualityControlModel.project_id == project_id)
        ).all()
        for action in actions:
            if (
                action.status == "CLOSED"
                and action.evidence_required
                and not action.evidence.strip()
            ):
                add(
                    "PM2-QUAL-001",
                    "ERROR",
                    "Action qualité clôturée sans preuve requise.",
                    "quality_action",
                    action.id,
                )

        gates = self.session.scalars(
            select(GateReviewModel).where(GateReviewModel.project_id == project_id)
        ).all()
        for gate in gates:
            unmet = self.session.scalar(
                select(func.count())
                .select_from(GateChecklistItemModel)
                .where(
                    GateChecklistItemModel.gate_review_id == gate.id,
                    GateChecklistItemModel.required.is_(True),
                    GateChecklistItemModel.satisfied.is_(False),
                )
            )
            if gate.status in {"APPROVED", "APPROVED_WITH_RESERVES"} and unmet:
                add(
                    "PM2-GATE-001",
                    "ERROR",
                    "Gate approuvé avec élément obligatoire non satisfait.",
                    "gate",
                    gate.id,
                )
            if gate.status == "APPROVED_WITH_RESERVES":
                add("PM2-GATE-002", "INFO", "Gate approuvé avec réserves.", "gate", gate.id)

        self._validate_orphans(project_id, problems)
        return sorted(
            problems, key=lambda p: ({"ERROR": 0, "WARNING": 1, "INFO": 2}[p.severity], p.code)
        )

    def compliance_report(
        self, project_id: str, methodology: PM2Configuration | None = None
    ) -> ComplianceReport:
        project = self.session.get(ProjectModel, project_id)
        if project is None:
            raise LookupError(f"Projet introuvable : {project_id}")
        problems = tuple(self.validate_project(project_id))
        gates = self._gate_compliance(project_id, methodology)
        gate_by_phase = {
            "LAUNCH": next((gate for gate in gates if gate.code == "RFP"), None),
            "PLANNING": next((gate for gate in gates if gate.code == "RFE"), None),
            "EXECUTION": next((gate for gate in gates if gate.code == "RFC"), None),
        }
        phase_rows = {
            phase.methodology_phase_code: phase
            for phase in self.session.scalars(
                select(PhaseModel).where(PhaseModel.project_id == project_id)
            )
        }
        order = ("LAUNCH", "PLANNING", "EXECUTION", "CLOSING")
        names = {
            "LAUNCH": "Lancement",
            "PLANNING": "Planification",
            "EXECUTION": "Exécution",
            "CLOSING": "Clôture",
            "MONITORING_CONTROL": "Suivi & Contrôle",
        }
        current_index = order.index(project.current_phase) if project.current_phase in order else 3
        phases: list[PhaseCompliance] = []
        for index, code in enumerate(order):
            row = phase_rows.get(code)
            started = index <= current_index or (row is not None and row.status != "NOT_STARTED")
            relevant = [problem for problem in problems if self._problem_phase(problem) == code]
            errors = sum(problem.severity == "ERROR" for problem in relevant)
            warnings = sum(problem.severity == "WARNING" for problem in relevant)
            if not started:
                phases.append(PhaseCompliance(code, names[code], None, "Non commencée", 0, 0))
                continue
            quality = max(
                0,
                100
                - errors * 18
                - warnings * 7
                - sum(problem.severity == "INFO" for problem in relevant) * 2,
            )
            gate = gate_by_phase.get(code)
            score = round(quality if gate is None else quality * 0.35 + gate.score * 0.65)
            status = "Conforme" if score == 100 else "À renforcer" if score >= 70 else "Bloquée"
            phases.append(PhaseCompliance(code, names[code], score, status, errors, warnings))

        monitoring = [
            problem
            for problem in problems
            if self._problem_phase(problem) == "MONITORING_CONTROL"
        ]
        monitoring_errors = sum(problem.severity == "ERROR" for problem in monitoring)
        monitoring_warnings = sum(problem.severity == "WARNING" for problem in monitoring)
        monitoring_score = max(0, 100 - monitoring_errors * 18 - monitoring_warnings * 7)
        phases.insert(
            3,
            PhaseCompliance(
                "MONITORING_CONTROL",
                names["MONITORING_CONTROL"],
                monitoring_score,
                "Conforme" if monitoring_score == 100 else "À renforcer",
                monitoring_errors,
                monitoring_warnings,
            ),
        )
        scored = [phase.score for phase in phases if phase.score is not None]
        return ComplianceReport(
            score=round(sum(scored) / len(scored)) if scored else 0,
            phases=tuple(phases),
            gates=gates,
            problems=problems,
        )

    def _gate_compliance(
        self, project_id: str, methodology: PM2Configuration | None
    ) -> tuple[GateCompliance, ...]:
        reviews = {
            review.gate_code: review
            for review in self.session.scalars(
                select(GateReviewModel).where(GateReviewModel.project_id == project_id)
            )
        }
        definitions = {gate.code: gate for gate in methodology.gates} if methodology else {}
        codes = tuple(definitions) or ("RFP", "RFE", "RFC")
        results: list[GateCompliance] = []
        for code in codes:
            definition = definitions.get(code)
            review = reviews.get(code)
            stored = (
                self.session.scalars(
                    select(GateChecklistItemModel)
                    .where(GateChecklistItemModel.gate_review_id == review.id)
                    .order_by(GateChecklistItemModel.item_code)
                ).all()
                if review is not None
                else []
            )
            if stored:
                checks = tuple(
                    GateComplianceCheck(
                        item.item_code,
                        item.description,
                        item.required,
                        item.satisfied,
                    )
                    for item in stored
                )
            elif definition is not None:
                checks = tuple(
                    GateComplianceCheck(item.id, item.description, item.required, False)
                    for item in definition.checklist
                )
            else:
                checks = ()
            required = [item for item in checks if item.required]
            score = round(
                100 * sum(item.satisfied for item in required) / len(required)
            ) if required else 0
            stored_status = review.status if review is not None else "NOT_READY"
            if stored_status in {"APPROVED", "APPROVED_WITH_RESERVES"}:
                status = "APPROUVÉ" if stored_status == "APPROVED" else "APPROUVÉ AVEC RÉSERVES"
            elif required and all(item.satisfied for item in required):
                status = "PRÊT"
            else:
                status = "BLOQUÉ"
            results.append(
                GateCompliance(
                    code=code,
                    name=definition.name if definition is not None else code,
                    label=definition.label if definition is not None else code,
                    status=status,
                    score=score,
                    checks=checks,
                )
            )
        return tuple(results)

    @staticmethod
    def _problem_phase(problem: ValidationProblem) -> str:
        if problem.entity in {"project", "governance", "stakeholder"}:
            return "LAUNCH"
        if problem.entity in {"task", "requirement", "deliverable"}:
            return "PLANNING"
        if problem.entity in {"acceptance", "acceptance_test", "quality_action"}:
            return "EXECUTION"
        if problem.entity in {"risk", "issue", "change", "decision", "traceability"}:
            return "MONITORING_CONTROL"
        if problem.entity == "gate":
            return "EXECUTION"
        return "MONITORING_CONTROL"

    def _has_test_link(self, requirement_id: str) -> bool:
        return bool(
            self.session.scalar(
                select(func.count())
                .select_from(TraceLinkModel)
                .where(
                    TraceLinkModel.source_type == "requirement",
                    TraceLinkModel.source_id == requirement_id,
                    TraceLinkModel.target_type == "acceptance_test",
                )
            )
        )

    def _validate_orphans(self, project_id: str, problems: list[ValidationProblem]) -> None:
        models = (
            ("risk", RiskModel),
            ("issue", IssueModel),
            ("change", ChangeModel),
            ("decision", DecisionModel),
            ("requirement", RequirementModel),
        )
        french_names = {
            "risk": "Risque",
            "issue": "Problème",
            "change": "Modification",
            "decision": "Décision",
            "requirement": "Exigence",
        }
        for kind, model in models:
            for entity_id in self.session.scalars(
                select(model.id).where(model.project_id == project_id)
            ):
                linked = self.session.scalar(
                    select(func.count())
                    .select_from(TraceLinkModel)
                    .where(
                        TraceLinkModel.project_id == project_id,
                        or_(
                            (TraceLinkModel.source_type == kind)
                            & (TraceLinkModel.source_id == entity_id),
                            (TraceLinkModel.target_type == kind)
                            & (TraceLinkModel.target_id == entity_id),
                        ),
                    )
                )
                if not linked:
                    problems.append(
                        ValidationProblem(
                            "PM2-TRACE-001",
                            "WARNING",
                            f"{french_names[kind]} sans relation de traçabilité.",
                            kind,
                            entity_id,
                        )
                    )

    @staticmethod
    def filtered(
        problems: list[ValidationProblem], severity: str | None
    ) -> list[ValidationProblem]:
        return [problem for problem in problems if severity is None or problem.severity == severity]
