from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pm2.application.audit import AuditService
from pm2.application.traceability import TraceabilityService as TraceabilityService
from pm2.infrastructure.orm import (
    DeliverableModel,
    RequirementDeliverableModel,
    RequirementModel,
    RequirementTaskModel,
    TaskDependencyModel,
    TaskModel,
    WbsNodeModel,
    row_to_dict,
)
from pm2.infrastructure.repositories import Repository


class WorkPlanService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_node(
        self,
        project_id: str,
        code: str,
        name: str,
        *,
        node_type: str = "work_package",
        parent_id: str | None = None,
        description: str = "",
        sequence: int = 0,
    ) -> WbsNodeModel:
        if node_type not in {"phase", "work_package", "task", "milestone"}:
            raise ValueError("Type de nœud WBS invalide.")
        if parent_id:
            parent = Repository(self.session, WbsNodeModel).require(parent_id)
            if parent.project_id != project_id:
                raise ValueError("Le parent WBS appartient à un autre projet.")
            if parent.node_type in {"task", "milestone"}:
                raise ValueError("Une tâche ou un jalon ne peut pas contenir d'autres éléments.")
        if sequence == 0:
            maximum = self.session.scalar(
                select(func.max(WbsNodeModel.sequence)).where(
                    WbsNodeModel.project_id == project_id,
                    WbsNodeModel.parent_id == parent_id,
                )
            )
            sequence = int(maximum) + 1 if maximum is not None else 0
        node = WbsNodeModel(
            project_id=project_id,
            parent_id=parent_id,
            code=code.strip(),
            name=name.strip(),
            node_type=node_type,
            description=description,
            sequence=sequence,
        )
        if not node.code or not node.name:
            raise ValueError("Le code et le nom WBS sont obligatoires.")
        self.session.add(node)
        self.session.flush()
        return node

    def create_task(self, node_id: str, **values: Any) -> TaskModel:
        node = Repository(self.session, WbsNodeModel).require(node_id)
        if node.node_type not in {"task", "milestone"}:
            raise ValueError("Une tâche ne peut être associée qu'à un nœud task ou milestone.")
        progress = int(values.get("progress_percent", 0))
        if not 0 <= progress <= 100:
            raise ValueError("L'avancement doit être compris entre 0 et 100.")
        start = values.get("planned_start")
        end = values.get("planned_end")
        if start and end and end < start:
            raise ValueError("La date de fin doit suivre la date de début.")
        task = TaskModel(wbs_node_id=node_id, **values)
        self.session.add(task)
        self.session.flush()
        return task

    def update_node(
        self,
        node_id: str,
        *,
        code: str,
        name: str,
        description: str = "",
        planned_start: date | None = None,
        planned_end: date | None = None,
        progress_percent: int = 0,
        planned_cost: Decimal = Decimal("0"),
    ) -> WbsNodeModel:
        node = Repository(self.session, WbsNodeModel).require(node_id)
        if not code.strip() or not name.strip():
            raise ValueError("Le code et le nom WBS sont obligatoires.")
        if planned_start and planned_end and planned_end < planned_start:
            raise ValueError("La date de fin doit suivre la date de début.")
        if not 0 <= progress_percent <= 100:
            raise ValueError("L'avancement doit être compris entre 0 et 100.")
        old = row_to_dict(node)
        node.code, node.name, node.description = code.strip(), name.strip(), description
        if node.task:
            node.task.planned_start = planned_start
            node.task.planned_end = planned_end
            node.task.progress_percent = progress_percent
            node.task.planned_cost = planned_cost
        AuditService(self.session).record(
            node.project_id, "wbs_node", node.id, "UPDATE", old=old, new=row_to_dict(node)
        )
        self.session.flush()
        return node

    def move(self, node_id: str, new_parent_id: str | None, sequence: int = 0) -> None:
        node = Repository(self.session, WbsNodeModel).require(node_id)
        cursor_id = new_parent_id
        while cursor_id:
            if cursor_id == node.id:
                raise ValueError("Un nœud WBS ne peut pas devenir son propre descendant.")
            cursor = Repository(self.session, WbsNodeModel).require(cursor_id)
            if cursor.project_id != node.project_id:
                raise ValueError("Le nouveau parent appartient à un autre projet.")
            cursor_id = cursor.parent_id
        node.parent_id = new_parent_id
        node.sequence = sequence
        AuditService(self.session).record(
            node.project_id,
            "wbs_node",
            node.id,
            "MOVE",
            new={"parent_id": new_parent_id, "sequence": sequence},
        )

    def move_sibling(self, node_id: str, offset: int) -> None:
        if offset not in {-1, 1}:
            raise ValueError("Le déplacement doit être de -1 ou +1.")
        node = Repository(self.session, WbsNodeModel).require(node_id)
        siblings = list(
            self.session.scalars(
                select(WbsNodeModel)
                .where(
                    WbsNodeModel.project_id == node.project_id,
                    WbsNodeModel.parent_id == node.parent_id,
                    WbsNodeModel.archived.is_(False),
                )
                .order_by(WbsNodeModel.sequence, WbsNodeModel.code)
            ).all()
        )
        for index, sibling in enumerate(siblings):
            sibling.sequence = index
        index = siblings.index(node)
        target_index = index + offset
        if not 0 <= target_index < len(siblings):
            return
        target = siblings[target_index]
        node.sequence, target.sequence = target.sequence, node.sequence
        AuditService(self.session).record(
            node.project_id,
            "wbs_node",
            node.id,
            "REORDER",
            new={"sequence": node.sequence},
        )
        self.session.flush()

    def indent(self, node_id: str) -> None:
        node = Repository(self.session, WbsNodeModel).require(node_id)
        siblings = list(
            self.session.scalars(
                select(WbsNodeModel)
                .where(
                    WbsNodeModel.project_id == node.project_id,
                    WbsNodeModel.parent_id == node.parent_id,
                    WbsNodeModel.archived.is_(False),
                )
                .order_by(WbsNodeModel.sequence, WbsNodeModel.code)
            ).all()
        )
        index = siblings.index(node)
        if index == 0:
            raise ValueError("Aucun élément précédent ne peut devenir le parent.")
        new_parent = siblings[index - 1]
        if new_parent.node_type in {"task", "milestone"}:
            raise ValueError("Une tâche ou un jalon ne peut pas contenir d'autres éléments.")
        self.move(node.id, new_parent.id, len(new_parent.children))

    def outdent(self, node_id: str) -> None:
        node = Repository(self.session, WbsNodeModel).require(node_id)
        if node.parent_id is None:
            raise ValueError("L'élément est déjà au niveau racine.")
        parent = Repository(self.session, WbsNodeModel).require(node.parent_id)
        self.move(node.id, parent.parent_id, parent.sequence + 1)

    def archive_node(self, node_id: str) -> None:
        node = Repository(self.session, WbsNodeModel).require(node_id)
        old = row_to_dict(node)
        node.archived = True
        AuditService(self.session).record(
            node.project_id,
            "wbs_node",
            node.id,
            "ARCHIVE",
            old=old,
            new=row_to_dict(node),
        )
        self.session.flush()

    def remove_dependency(self, dependency_id: str) -> None:
        dependency = Repository(self.session, TaskDependencyModel).require(dependency_id)
        predecessor = Repository(self.session, TaskModel).require(dependency.predecessor_task_id)
        project_id = predecessor.wbs_node.project_id
        old = row_to_dict(dependency)
        self.session.delete(dependency)
        AuditService(self.session).record(
            project_id, "task_dependency", dependency_id, "DELETE", old=old
        )
        self.session.flush()

    def add_dependency(
        self, predecessor_id: str, successor_id: str, dependency_type: str = "FS", lag_days: int = 0
    ) -> TaskDependencyModel:
        if predecessor_id == successor_id:
            raise ValueError("Une tâche ne peut pas dépendre d'elle-même.")
        if dependency_type not in {"FS", "SS", "FF", "SF"}:
            raise ValueError("Type de dépendance invalide.")
        predecessor = Repository(self.session, TaskModel).require(predecessor_id)
        successor = Repository(self.session, TaskModel).require(successor_id)
        if predecessor.wbs_node.project_id != successor.wbs_node.project_id:
            raise ValueError("Les deux tâches doivent appartenir au même projet.")
        if self._reachable(successor_id, predecessor_id):
            raise ValueError("Cette dépendance créerait un cycle.")
        dependency = TaskDependencyModel(
            predecessor_task_id=predecessor_id,
            successor_task_id=successor_id,
            dependency_type=dependency_type,
            lag_days=lag_days,
        )
        self.session.add(dependency)
        self.session.flush()
        AuditService(self.session).record(
            predecessor.wbs_node.project_id,
            "task_dependency",
            dependency.id,
            "CREATE",
            new=row_to_dict(dependency),
        )
        return dependency

    def _reachable(self, start: str, target: str) -> bool:
        seen: set[str] = set()
        frontier = [start]
        while frontier:
            current = frontier.pop()
            if current == target:
                return True
            if current in seen:
                continue
            seen.add(current)
            frontier.extend(
                self.session.scalars(
                    select(TaskDependencyModel.successor_task_id).where(
                        TaskDependencyModel.predecessor_task_id == current
                    )
                )
            )
        return False


class RequirementService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        project_id: str,
        code: str,
        title: str,
        *,
        description: str = "",
        source: str | None = None,
        priority: str | None = None,
        verification_method: str | None = None,
    ) -> RequirementModel:
        if not code.strip() or not title.strip():
            raise ValueError("Le code et le titre de l'exigence sont obligatoires.")
        requirement = RequirementModel(
            project_id=project_id,
            code=code.strip(),
            title=title.strip(),
            description=description,
            source=source,
            priority=priority,
            verification_method=verification_method,
            status="DRAFT",
        )
        self.session.add(requirement)
        self.session.flush()
        AuditService(self.session).record(
            project_id, "requirement", requirement.id, "CREATE", new=row_to_dict(requirement)
        )
        return requirement

    def link_task(self, requirement_id: str, task_id: str) -> RequirementTaskModel:
        link = RequirementTaskModel(requirement_id=requirement_id, task_id=task_id)
        self.session.add(link)
        self.session.flush()
        return link

    def link_deliverable(
        self, requirement_id: str, deliverable_id: str
    ) -> RequirementDeliverableModel:
        link = RequirementDeliverableModel(
            requirement_id=requirement_id, deliverable_id=deliverable_id
        )
        self.session.add(link)
        self.session.flush()
        return link


class DeliverableService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        project_id: str,
        code: str,
        name: str,
        *,
        description: str = "",
        owner: str | None = None,
        planned_date: date | None = None,
    ) -> DeliverableModel:
        if not code.strip() or not name.strip():
            raise ValueError("Le code et le nom du livrable sont obligatoires.")
        deliverable = DeliverableModel(
            project_id=project_id,
            code=code.strip(),
            name=name.strip(),
            description=description,
            owner=owner,
            planned_date=planned_date,
            status="PLANNED",
            acceptance_status="NOT_STARTED",
        )
        self.session.add(deliverable)
        self.session.flush()
        AuditService(self.session).record(
            project_id, "deliverable", deliverable.id, "CREATE", new=row_to_dict(deliverable)
        )
        return deliverable


