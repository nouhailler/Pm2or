from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.infrastructure.orm import (
    AcceptanceCriterionModel,
    AcceptanceTestModel,
    ChangeModel,
    DecisionModel,
    DeliverableModel,
    DocumentModel,
    IssueModel,
    RequirementModel,
    RiskModel,
    TaskModel,
    TraceLinkModel,
    TransitionActivityModel,
    WbsNodeModel,
)
from pm2.infrastructure.repositories import Repository


class TraceabilityService:
    """Create and query typed, project-scoped traceability links."""

    RELATION_TYPES = {
        "supports",
        "derives_from",
        "impacts",
        "mitigates",
        "resolves",
        "decides",
        "implements",
        "verifies",
        "accepted_by",
        "produces",
        "depends_on",
        "assigned_to",
        "discussed_in",
        "referenced_by",
    }
    TRACEABLE_MODELS: dict[str, type[Any]] = {
        "requirement": RequirementModel,
        "deliverable": DeliverableModel,
        "task": TaskModel,
        "risk": RiskModel,
        "issue": IssueModel,
        "decision": DecisionModel,
        "change": ChangeModel,
        "document": DocumentModel,
        "acceptance_test": AcceptanceTestModel,
        "transition_activity": TransitionActivityModel,
    }

    def __init__(self, session: Session) -> None:
        self.session = session

    def link(
        self,
        project_id: str,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relation_type: str,
        *,
        critical: bool = False,
    ) -> TraceLinkModel:
        if relation_type not in self.RELATION_TYPES:
            raise ValueError(f"Type de relation inconnu : {relation_type}")
        if source_type == target_type and source_id == target_id:
            raise ValueError("Une entité ne peut pas être reliée à elle-même.")
        self._require_project_entity(project_id, source_type, source_id, "source")
        self._require_project_entity(project_id, target_type, target_id, "cible")
        link = TraceLinkModel(
            project_id=project_id,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relation_type=relation_type,
            critical=critical,
        )
        self.session.add(link)
        self.session.flush()
        return link

    def _require_project_entity(
        self, project_id: str, entity_type: str, entity_id: str, label: str
    ) -> None:
        model = self.TRACEABLE_MODELS.get(entity_type)
        if model is None:
            raise ValueError(f"Type d'entité de {label} inconnu : {entity_type}")
        if entity_type == "task":
            statement = (
                select(TaskModel.id)
                .join(WbsNodeModel, TaskModel.wbs_node_id == WbsNodeModel.id)
                .where(TaskModel.id == entity_id, WbsNodeModel.project_id == project_id)
            )
        elif entity_type == "acceptance_test":
            statement = (
                select(AcceptanceTestModel.id)
                .join(
                    AcceptanceCriterionModel,
                    AcceptanceTestModel.criterion_id == AcceptanceCriterionModel.id,
                )
                .join(
                    DeliverableModel,
                    AcceptanceCriterionModel.deliverable_id == DeliverableModel.id,
                )
                .where(
                    AcceptanceTestModel.id == entity_id,
                    DeliverableModel.project_id == project_id,
                )
            )
        else:
            statement = select(model.id).where(
                model.id == entity_id, model.project_id == project_id
            )
        if self.session.scalar(statement) is None:
            raise ValueError(
                f"Entité {label} introuvable dans ce projet : {entity_type}/{entity_id}"
            )

    def unlink(self, link_id: str) -> None:
        link = Repository(self.session, TraceLinkModel).require(link_id)
        if link.critical:
            raise ValueError("Un lien critique ne peut pas être supprimé.")
        self.session.delete(link)
        self.session.flush()

    def links_for(self, entity_type: str, entity_id: str) -> Sequence[TraceLinkModel]:
        return self.session.scalars(
            select(TraceLinkModel).where(
                (TraceLinkModel.source_type == entity_type)
                & (TraceLinkModel.source_id == entity_id)
                | (TraceLinkModel.target_type == entity_type)
                & (TraceLinkModel.target_id == entity_id)
            )
        ).all()
