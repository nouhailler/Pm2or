from __future__ import annotations

from datetime import date
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pm2.application.audit import AuditService
from pm2.application.traceability import TraceabilityService as TraceabilityService
from pm2.domain.enums import WorkflowError
from pm2.domain.workflows import DEFAULT_WORKFLOW_ENGINE
from pm2.infrastructure.orm import (
    MODEL_BY_KIND,
    AcceptanceModel,
    ChangeApprovalModel,
    ChangeModel,
    IssueModel,
    RiskModel,
    TraceLinkModel,
    row_to_dict,
)
from pm2.infrastructure.repositories import Repository


class RegisterService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, kind: str, project_id: str, **values: Any) -> Any:
        if kind not in {"risk", "issue", "decision", "change"}:
            raise ValueError(f"Registre inconnu : {kind}")
        model: Any = MODEL_BY_KIND[kind]
        if model is RiskModel:
            probability = values.get("probability")
            impact = values.get("impact")
            values["score"] = probability * impact if probability and impact else None
        item = model(project_id=project_id, **values)
        self.session.add(item)
        self.session.flush()
        AuditService(self.session).record(
            project_id, kind, item.id, "CREATE", new=row_to_dict(item)
        )
        return item


class RiskService(RegisterService):
    def create_risk(self, project_id: str, **values: Any) -> RiskModel:
        return cast(RiskModel, self.create("risk", project_id, **values))


class IssueService(RegisterService):
    def create_issue(self, project_id: str, **values: Any) -> IssueModel:
        return cast(IssueModel, self.create("issue", project_id, **values))


class DecisionService(RegisterService):
    def create_decision(self, project_id: str, **values: Any) -> Any:
        return self.create("decision", project_id, **values)


class ChangeService(RegisterService):
    def create_change(self, project_id: str, **values: Any) -> ChangeModel:
        return cast(ChangeModel, self.create("change", project_id, **values))


class WorkflowService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def transition(self, kind: str, entity_id: str, target: str, *, actor: str = "local") -> Any:
        model = MODEL_BY_KIND.get(kind)
        if model is None or kind == "project":
            raise ValueError(f"Workflow non pris en charge : {kind}")
        entity: Any = Repository(self.session, model).require(entity_id)
        current = str(entity.status)
        DEFAULT_WORKFLOW_ENGINE.validate(kind, current, target)
        if kind == "issue" and target == "CLOSED" and not entity.resolution.strip():
            raise WorkflowError("Un problème ne peut pas être clôturé sans résolution.")
        if kind == "change" and target == "IMPLEMENTING":
            approval = self.session.scalar(
                select(ChangeApprovalModel).where(
                    ChangeApprovalModel.change_id == entity_id,
                    ChangeApprovalModel.decision == "APPROVED",
                )
            )
            if approval is None:
                raise WorkflowError(
                    "La modification ne peut pas passer à IMPLEMENTING sans approbation enregistrée."
                )
        if kind == "requirement" and target == "VERIFIED":
            linked = self.session.scalar(
                select(func.count())
                .select_from(TraceLinkModel)
                .where(
                    TraceLinkModel.source_type == "requirement",
                    TraceLinkModel.source_id == entity_id,
                    TraceLinkModel.target_type == "acceptance_test",
                )
            )
            if not linked:
                raise WorkflowError(
                    "Une exigence vérifiée doit avoir au moins un test d'acceptation lié."
                )
        if kind == "deliverable" and target == "ACCEPTED":
            acceptance = self.session.scalar(
                select(AcceptanceModel).where(
                    AcceptanceModel.deliverable_id == entity_id,
                    AcceptanceModel.status == "ACCEPTED",
                )
            )
            if acceptance is None:
                raise WorkflowError(
                    "Un livrable ne peut être accepté sans enregistrement d'acceptation."
                )
        old = row_to_dict(entity)
        entity.status = target
        AuditService(self.session).record(
            getattr(entity, "project_id", None),
            kind,
            entity_id,
            f"TRANSITION:{current}→{target}",
            old=old,
            new=row_to_dict(entity),
            actor=actor,
        )
        self.session.flush()
        return entity

    def approve_change(
        self, change_id: str, approver: str, comments: str = ""
    ) -> ChangeApprovalModel:
        change = Repository(self.session, ChangeModel).require(change_id)
        if change.status != "APPROVAL":
            raise WorkflowError("La modification doit être à l'état APPROVAL.")
        approval = ChangeApprovalModel(
            change_id=change_id, decision="APPROVED", approver=approver, comments=comments
        )
        self.session.add(approval)
        change.status = "APPROVED"
        change.approver = approver
        change.approval_date = date.today()
        AuditService(self.session).record(
            change.project_id,
            "change",
            change.id,
            "APPROVE",
            new=row_to_dict(change),
            actor=approver,
        )
        self.session.flush()
        return approval


