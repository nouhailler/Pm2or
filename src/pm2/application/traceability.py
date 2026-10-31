from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.infrastructure.orm import (
    AcceptanceCriterionModel,
    AcceptanceTestModel,
    ChangeImpactModel,
    ChangeModel,
    DecisionModel,
    DeliverableModel,
    DocumentModel,
    IssueModel,
    RequirementDeliverableModel,
    RequirementModel,
    RequirementTaskModel,
    RiskActionModel,
    RiskModel,
    TaskModel,
    TraceLinkModel,
    TransitionActivityModel,
    WbsNodeModel,
)
from pm2.infrastructure.repositories import Repository


@dataclass(frozen=True, slots=True)
class TraceGraphNode:
    entity_type: str
    entity_id: str
    label: str
    title: str
    page: str

    @property
    def key(self) -> str:
        return f"{self.entity_type}:{self.entity_id}"


@dataclass(frozen=True, slots=True)
class TraceGraphEdge:
    source: str
    target: str
    relation: str
    native: bool = False


@dataclass(frozen=True, slots=True)
class TraceabilityGraph:
    nodes: tuple[TraceGraphNode, ...]
    edges: tuple[TraceGraphEdge, ...]


@dataclass(frozen=True, slots=True)
class OrphanFinding:
    code: str
    label: str
    entity_type: str
    entity_ids: tuple[str, ...]
    entity_labels: tuple[str, ...]
    page: str

    @property
    def count(self) -> int:
        return len(self.entity_ids)


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
        "acceptance_criterion": AcceptanceCriterionModel,
        "risk_action": RiskActionModel,
        "change_impact": ChangeImpactModel,
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
        elif entity_type == "acceptance_criterion":
            statement = (
                select(AcceptanceCriterionModel.id)
                .join(
                    DeliverableModel,
                    AcceptanceCriterionModel.deliverable_id == DeliverableModel.id,
                )
                .where(
                    AcceptanceCriterionModel.id == entity_id,
                    DeliverableModel.project_id == project_id,
                )
            )
        elif entity_type == "risk_action":
            statement = (
                select(RiskActionModel.id)
                .join(RiskModel, RiskActionModel.risk_id == RiskModel.id)
                .where(RiskActionModel.id == entity_id, RiskModel.project_id == project_id)
            )
        elif entity_type == "change_impact":
            statement = (
                select(ChangeImpactModel.id)
                .join(ChangeModel, ChangeImpactModel.change_id == ChangeModel.id)
                .where(ChangeImpactModel.id == entity_id, ChangeModel.project_id == project_id)
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

    def graph(self, project_id: str) -> TraceabilityGraph:
        nodes: dict[str, TraceGraphNode] = {}
        edges: list[TraceGraphEdge] = []

        def add_node(
            entity_type: str, entity_id: str, label: str, title: str, page: str
        ) -> None:
            node = TraceGraphNode(entity_type, entity_id, label, title, page)
            nodes[node.key] = node

        requirements = list(
            self.session.scalars(
                select(RequirementModel)
                .where(
                    RequirementModel.project_id == project_id,
                    RequirementModel.archived.is_(False),
                )
                .order_by(RequirementModel.code)
            ).all()
        )
        tasks = list(
            self.session.scalars(
                select(TaskModel)
                .join(WbsNodeModel)
                .where(
                    WbsNodeModel.project_id == project_id,
                    WbsNodeModel.archived.is_(False),
                    TaskModel.archived.is_(False),
                )
                .order_by(WbsNodeModel.code)
            ).all()
        )
        deliverables = list(
            self.session.scalars(
                select(DeliverableModel)
                .where(
                    DeliverableModel.project_id == project_id,
                    DeliverableModel.archived.is_(False),
                )
                .order_by(DeliverableModel.code)
            ).all()
        )
        risks = list(
            self.session.scalars(
                select(RiskModel)
                .where(RiskModel.project_id == project_id, RiskModel.archived.is_(False))
                .order_by(RiskModel.code)
            ).all()
        )
        changes = list(
            self.session.scalars(
                select(ChangeModel)
                .where(ChangeModel.project_id == project_id, ChangeModel.archived.is_(False))
                .order_by(ChangeModel.code)
            ).all()
        )
        for requirement in requirements:
            add_node(
                "requirement", requirement.id, requirement.code, requirement.title, "Données métier"
            )
        for task in tasks:
            add_node("task", task.id, task.wbs_node.code, task.wbs_node.name, "Plan de travail")
        for deliverable in deliverables:
            add_node(
                "deliverable", deliverable.id, deliverable.code, deliverable.name, "Données métier"
            )
        for risk in risks:
            add_node("risk", risk.id, risk.code, risk.title, "Registres")
        for change in changes:
            add_node("change", change.id, change.code, change.title, "Registres")
            hub_id = f"{change.id}:impact"
            add_node(
                "change_impact", hub_id, "Impact", "Analyse d'impact", "Registres"
            )
            edges.append(
                TraceGraphEdge(
                    f"change:{change.id}",
                    f"change_impact:{hub_id}",
                    "impacts",
                    True,
                )
            )
            for category, value in (
                ("Schedule", change.impact_schedule),
                ("Cost", change.impact_cost),
            ):
                if value in (None, "", 0):
                    continue
                category_id = f"{change.id}:{category.lower()}"
                add_node(
                    "change_impact",
                    category_id,
                    category,
                    str(value),
                    "Registres",
                )
                edges.append(
                    TraceGraphEdge(
                        f"change_impact:{hub_id}",
                        f"change_impact:{category_id}",
                        "includes",
                        True,
                    )
                )

        project_deliverable_ids = [item.id for item in deliverables]
        criteria = (
            list(
                self.session.scalars(
                    select(AcceptanceCriterionModel)
                    .where(
                        AcceptanceCriterionModel.deliverable_id.in_(project_deliverable_ids),
                        AcceptanceCriterionModel.archived.is_(False),
                    )
                    .order_by(AcceptanceCriterionModel.code)
                ).all()
            )
            if project_deliverable_ids
            else []
        )
        criterion_ids = [item.id for item in criteria]
        tests = (
            list(
                self.session.scalars(
                    select(AcceptanceTestModel)
                    .where(
                        AcceptanceTestModel.criterion_id.in_(criterion_ids),
                        AcceptanceTestModel.archived.is_(False),
                    )
                    .order_by(AcceptanceTestModel.code)
                ).all()
            )
            if criterion_ids
            else []
        )
        for criterion in criteria:
            add_node(
                "acceptance_criterion",
                criterion.id,
                criterion.code,
                criterion.description,
                "Données métier",
            )
            edges.append(
                TraceGraphEdge(
                    f"deliverable:{criterion.deliverable_id}",
                    f"acceptance_criterion:{criterion.id}",
                    "has criterion",
                    True,
                )
            )
        for test in tests:
            add_node(
                "acceptance_test", test.id, test.code, test.description, "Données métier"
            )
            edges.append(
                TraceGraphEdge(
                    f"acceptance_criterion:{test.criterion_id}",
                    f"acceptance_test:{test.id}",
                    "verified by",
                    True,
                )
            )

        risk_ids = [item.id for item in risks]
        risk_actions = (
            self.session.scalars(
                select(RiskActionModel)
                .where(
                    RiskActionModel.risk_id.in_(risk_ids),
                    RiskActionModel.archived.is_(False),
                )
                .order_by(RiskActionModel.title)
            ).all()
            if risk_ids
            else []
        )
        for action in risk_actions:
            add_node(
                "risk_action",
                action.id,
                "Mitigation",
                action.title,
                "Registres",
            )
            edges.append(
                TraceGraphEdge(
                    f"risk:{action.risk_id}",
                    f"risk_action:{action.id}",
                    "mitigated by",
                    True,
                )
            )

        change_ids = [item.id for item in changes]
        impacts = (
            self.session.scalars(
                select(ChangeImpactModel)
                .where(ChangeImpactModel.change_id.in_(change_ids))
                .order_by(ChangeImpactModel.impact_type)
            ).all()
            if change_ids
            else []
        )
        for impact in impacts:
            add_node(
                "change_impact",
                impact.id,
                impact.impact_type.title(),
                impact.description,
                "Registres",
            )
            edges.append(
                TraceGraphEdge(
                    f"change_impact:{impact.change_id}:impact",
                    f"change_impact:{impact.id}",
                    "impacts",
                    True,
                )
            )

        requirement_ids = [item.id for item in requirements]
        for requirement_task in self.session.scalars(
            select(RequirementTaskModel).where(
                RequirementTaskModel.requirement_id.in_(requirement_ids)
            )
        ).all():
            edges.append(
                TraceGraphEdge(
                    f"requirement:{requirement_task.requirement_id}",
                    f"task:{requirement_task.task_id}",
                    "implemented by",
                    True,
                )
            )
        for requirement_deliverable in self.session.scalars(
            select(RequirementDeliverableModel).where(
                RequirementDeliverableModel.requirement_id.in_(requirement_ids)
            )
        ).all():
            edges.append(
                TraceGraphEdge(
                    f"requirement:{requirement_deliverable.requirement_id}",
                    f"deliverable:{requirement_deliverable.deliverable_id}",
                    "delivered by",
                    True,
                )
            )

        explicit_links = self.session.scalars(
            select(TraceLinkModel).where(TraceLinkModel.project_id == project_id)
        ).all()
        for explicit_link in explicit_links:
            source = f"{explicit_link.source_type}:{explicit_link.source_id}"
            target = f"{explicit_link.target_type}:{explicit_link.target_id}"
            if source not in nodes:
                self._add_explicit_node(
                    nodes,
                    project_id,
                    explicit_link.source_type,
                    explicit_link.source_id,
                )
            if target not in nodes:
                self._add_explicit_node(
                    nodes,
                    project_id,
                    explicit_link.target_type,
                    explicit_link.target_id,
                )
            if source in nodes and target in nodes:
                graph_source = source
                if explicit_link.source_type == "change" and explicit_link.relation_type == "impacts":
                    hub = f"change_impact:{explicit_link.source_id}:impact"
                    if hub in nodes:
                        graph_source = hub
                edges.append(
                    TraceGraphEdge(graph_source, target, explicit_link.relation_type)
                )

        valid_edges = tuple(
            edge for edge in edges if edge.source in nodes and edge.target in nodes
        )
        return TraceabilityGraph(tuple(nodes.values()), valid_edges)

    def orphan_findings(self, project_id: str) -> tuple[OrphanFinding, ...]:
        graph = self.graph(project_id)
        connected_pairs = {(edge.source, edge.target) for edge in graph.edges}
        nodes_by_type: dict[str, list[TraceGraphNode]] = {}
        for node in graph.nodes:
            nodes_by_type.setdefault(node.entity_type, []).append(node)

        def unconnected(source_type: str, target_types: set[str]) -> list[TraceGraphNode]:
            targets = {
                node.key for kind in target_types for node in nodes_by_type.get(kind, [])
            }
            return [
                node
                for node in nodes_by_type.get(source_type, [])
                if not any(
                    (node.key, target) in connected_pairs
                    or (target, node.key) in connected_pairs
                    for target in targets
                )
            ]

        requirements = unconnected("requirement", {"deliverable"})
        responded_risks = {
            edge.source
            for edge in graph.edges
            if edge.source.startswith("risk:")
            and (edge.target.startswith("risk_action:") or edge.relation == "mitigates")
        }
        risks = [
            node for node in nodes_by_type.get("risk", []) if node.key not in responded_risks
        ]
        tested_criteria = {
            edge.source
            for edge in graph.edges
            if edge.target.startswith("acceptance_test:")
        }
        tested_deliverables = {
            edge.source
            for edge in graph.edges
            if edge.target.startswith("acceptance_test:")
            or (
                edge.target.startswith("acceptance_criterion:")
                and edge.target in tested_criteria
            )
        }
        deliverables = [
            node
            for node in nodes_by_type.get("deliverable", [])
            if node.key not in tested_deliverables
        ]
        root_tasks = [
            task
            for task in self.session.scalars(
                select(TaskModel)
                .join(WbsNodeModel)
                .where(
                    WbsNodeModel.project_id == project_id,
                    WbsNodeModel.parent_id.is_(None),
                    WbsNodeModel.archived.is_(False),
                    TaskModel.archived.is_(False),
                )
            ).all()
        ]
        task_nodes = {node.entity_id: node for node in nodes_by_type.get("task", [])}
        tasks = [task_nodes[task.id] for task in root_tasks if task.id in task_nodes]
        return (
            self._finding(
                "REQ_WITHOUT_DELIVERABLE",
                "Exigences sans livrable",
                "requirement",
                requirements,
                "Données métier",
            ),
            self._finding(
                "RISK_WITHOUT_RESPONSE",
                "Risques sans réponse",
                "risk",
                risks,
                "Registres",
            ),
            self._finding(
                "DELIVERABLE_WITHOUT_TEST",
                "Livrables sans test",
                "deliverable",
                deliverables,
                "Données métier",
            ),
            self._finding(
                "TASK_WITHOUT_WBS_PARENT",
                "Tâches sans parent WBS",
                "task",
                tasks,
                "Plan de travail",
            ),
        )

    @staticmethod
    def _finding(
        code: str,
        label: str,
        entity_type: str,
        nodes: list[TraceGraphNode],
        page: str,
    ) -> OrphanFinding:
        return OrphanFinding(
            code,
            label,
            entity_type,
            tuple(node.entity_id for node in nodes),
            tuple(node.label for node in nodes),
            page,
        )

    def _add_explicit_node(
        self,
        nodes: dict[str, TraceGraphNode],
        project_id: str,
        entity_type: str,
        entity_id: str,
    ) -> None:
        model = self.TRACEABLE_MODELS.get(entity_type)
        if model is None:
            return
        entity = self.session.get(model, entity_id)
        if entity is None or bool(getattr(entity, "archived", False)):
            return
        label = str(
            getattr(entity, "code", None)
            or getattr(entity, "title", None)
            or entity_id[:8]
        )
        title = str(
            getattr(entity, "title", None)
            or getattr(entity, "name", None)
            or getattr(entity, "description", None)
            or label
        )
        pages = {
            "task": "Plan de travail",
            "risk": "Registres",
            "risk_action": "Registres",
            "issue": "Registres",
            "decision": "Registres",
            "change": "Registres",
            "change_impact": "Registres",
            "document": "Documents",
        }
        node = TraceGraphNode(
            entity_type,
            entity_id,
            label,
            title,
            pages.get(entity_type, "Données métier"),
        )
        nodes[node.key] = node
