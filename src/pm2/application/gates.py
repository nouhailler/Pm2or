from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.audit import AuditService
from pm2.application.traceability import TraceabilityService as TraceabilityService
from pm2.domain.enums import GateDecisionType, WorkflowError
from pm2.domain.workflows import DEFAULT_WORKFLOW_ENGINE
from pm2.infrastructure.orm import (
    GateChecklistItemModel,
    GateDecisionModel,
    GateReviewModel,
    PhaseModel,
    ProjectModel,
    utcnow,
)
from pm2.infrastructure.repositories import Repository
from pm2.methodology.models import PM2Configuration


class GateService:
    def __init__(self, session: Session, methodology: PM2Configuration) -> None:
        self.session = session
        self.methodology = methodology

    def get_or_create(self, project_id: str, gate_code: str) -> GateReviewModel:
        definition = self.methodology.gate(gate_code)
        review = self.session.scalar(
            select(GateReviewModel).where(
                GateReviewModel.project_id == project_id,
                GateReviewModel.gate_code == gate_code,
            )
        )
        if review:
            return review
        review = GateReviewModel(
            project_id=project_id,
            gate_code=gate_code,
            from_phase=definition.from_phase,
            to_phase=definition.to_phase,
            status="NOT_READY",
        )
        self.session.add(review)
        self.session.flush()
        self.session.add_all(
            GateChecklistItemModel(
                gate_review_id=review.id,
                item_code=item.id,
                description=item.description,
                required=item.required,
                satisfied=False,
            )
            for item in definition.checklist
        )
        self.session.flush()
        return review

    def checklist(self, review_id: str) -> Sequence[GateChecklistItemModel]:
        return self.session.scalars(
            select(GateChecklistItemModel)
            .where(GateChecklistItemModel.gate_review_id == review_id)
            .order_by(GateChecklistItemModel.item_code)
        ).all()

    def set_item(self, item_id: str, satisfied: bool, evidence: str = "") -> None:
        item = Repository(self.session, GateChecklistItemModel).require(item_id)
        item.satisfied = satisfied
        item.evidence = evidence
        review = Repository(self.session, GateReviewModel).require(item.gate_review_id)
        missing = any(item.required and not item.satisfied for item in self.checklist(review.id))
        review.status = "NOT_READY" if missing else "READY_FOR_REVIEW"

    def decide(
        self, review_id: str, decision: GateDecisionType | str, decided_by: str, comments: str = ""
    ) -> GateDecisionModel:
        review = Repository(self.session, GateReviewModel).require(review_id)
        project = Repository(self.session, ProjectModel).require(review.project_id)
        decision_value = str(decision)
        if decision_value not in {item.value for item in GateDecisionType}:
            raise ValueError("Décision de gate invalide.")
        if project.current_phase != review.from_phase:
            raise WorkflowError(
                f"Le gate {review.gate_code} ne peut être évalué que depuis {review.from_phase}."
            )
        if decision_value in {"APPROVED", "APPROVED_WITH_RESERVES"}:
            missing = [
                item.item_code
                for item in self.checklist(review.id)
                if item.required and not item.satisfied
            ]
            if missing:
                raise WorkflowError(
                    "Approbation impossible : éléments obligatoires non satisfaits : "
                    + ", ".join(missing)
                )
        decision_model = GateDecisionModel(
            gate_review_id=review.id,
            decision=decision_value,
            decided_by=decided_by.strip() or "local",
            comments=comments,
        )
        self.session.add(decision_model)
        review.status = decision_value
        if decision_value in {"APPROVED", "APPROVED_WITH_RESERVES"}:
            DEFAULT_WORKFLOW_ENGINE.validate("project", project.status, review.to_phase)
            old_phase = project.current_phase
            current_phase = self.session.scalar(
                select(PhaseModel).where(
                    PhaseModel.project_id == project.id,
                    PhaseModel.methodology_phase_code == old_phase,
                )
            )
            next_phase = self.session.scalar(
                select(PhaseModel).where(
                    PhaseModel.project_id == project.id,
                    PhaseModel.methodology_phase_code == review.to_phase,
                )
            )
            if current_phase:
                current_phase.status = "COMPLETED"
                current_phase.completed_at = utcnow()
            if next_phase:
                next_phase.status = "IN_PROGRESS"
                next_phase.started_at = utcnow()
            project.current_phase = review.to_phase
            project.status = review.to_phase
            AuditService(self.session).record(
                project.id,
                "gate",
                review.id,
                f"{review.gate_code}:{decision_value}",
                new={"phase": project.current_phase},
                actor=decided_by,
            )
        else:
            AuditService(self.session).record(
                project.id, "gate", review.id, f"{review.gate_code}:REJECTED", actor=decided_by
            )
        self.session.flush()
        return decision_model


