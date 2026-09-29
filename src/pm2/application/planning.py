from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pm2.application.audit import AuditService
from pm2.application.traceability import TraceabilityService as TraceabilityService
from pm2.infrastructure.orm import (
    DeliverableModel,
    ProjectModel,
    RequirementDeliverableModel,
    RequirementModel,
    RequirementTaskModel,
    TaskDependencyModel,
    TaskModel,
    WbsNodeModel,
    row_to_dict,
)
from pm2.infrastructure.repositories import Repository


@dataclass(frozen=True, slots=True)
class TaskSchedule:
    task_id: str
    code: str
    name: str
    duration_days: int
    early_start: date
    early_finish: date
    late_start: date
    late_finish: date
    total_float_days: int
    critical: bool


@dataclass(frozen=True, slots=True)
class ScheduleResult:
    project_start: date
    project_finish: date
    duration_days: int
    tasks: tuple[TaskSchedule, ...]
    critical_paths: tuple[tuple[str, ...], ...]


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

    def calculate_schedule(
        self, project_id: str, *, project_start: date | None = None
    ) -> ScheduleResult:
        """Calculate a deterministic calendar-day CPM schedule without changing saved dates."""
        project = Repository(self.session, ProjectModel).require(project_id)
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
        base_date = project_start or project.start_date or min(
            (task.planned_start for task in tasks if task.planned_start),
            default=date.today(),
        )
        if not tasks:
            return ScheduleResult(base_date, base_date, 0, (), ())

        task_by_id = {task.id: task for task in tasks}
        durations = {
            task.id: self._duration_days(task)
            for task in tasks
        }
        dependencies = list(
            self.session.scalars(
                select(TaskDependencyModel).where(
                    TaskDependencyModel.predecessor_task_id.in_(task_by_id),
                    TaskDependencyModel.successor_task_id.in_(task_by_id),
                )
            ).all()
        )
        successors: dict[str, list[tuple[str, int]]] = {task.id: [] for task in tasks}
        predecessors: dict[str, list[tuple[str, int]]] = {task.id: [] for task in tasks}
        indegree = {task.id: 0 for task in tasks}
        for dependency in dependencies:
            predecessor_id = dependency.predecessor_task_id
            successor_id = dependency.successor_task_id
            weight = self._dependency_weight(
                dependency.dependency_type,
                durations[predecessor_id],
                durations[successor_id],
                dependency.lag_days,
            )
            successors[predecessor_id].append((successor_id, weight))
            predecessors[successor_id].append((predecessor_id, weight))
            indegree[successor_id] += 1

        codes = {task.id: task.wbs_node.code for task in tasks}
        ready = sorted(
            (task_id for task_id, value in indegree.items() if value == 0),
            key=lambda task_id: codes[task_id],
        )
        topological: list[str] = []
        while ready:
            current = ready.pop(0)
            topological.append(current)
            for successor_id, _weight in successors[current]:
                indegree[successor_id] -= 1
                if indegree[successor_id] == 0:
                    ready.append(successor_id)
                    ready.sort(key=lambda task_id: codes[task_id])
        if len(topological) != len(tasks):
            raise ValueError("Le réseau de dépendances contient un cycle.")

        early_starts = {task.id: 0 for task in tasks}
        for task_id in topological:
            if predecessors[task_id]:
                early_starts[task_id] = max(
                    0,
                    max(
                        early_starts[predecessor_id] + weight
                        for predecessor_id, weight in predecessors[task_id]
                    ),
                )
        project_duration = max(
            early_starts[task.id] + durations[task.id] for task in tasks
        )
        late_starts = {
            task.id: project_duration - durations[task.id]
            for task in tasks
        }
        for task_id in reversed(topological):
            if successors[task_id]:
                late_starts[task_id] = min(
                    late_starts[task_id],
                    min(
                        late_starts[successor_id] - weight
                        for successor_id, weight in successors[task_id]
                    ),
                )

        schedules: list[TaskSchedule] = []
        for task_id in topological:
            task = task_by_id[task_id]
            duration = durations[task_id]
            early_start_offset = early_starts[task_id]
            late_start_offset = late_starts[task_id]
            total_float = late_start_offset - early_start_offset
            schedules.append(
                TaskSchedule(
                    task_id=task_id,
                    code=task.wbs_node.code,
                    name=task.wbs_node.name,
                    duration_days=duration,
                    early_start=base_date + timedelta(days=early_start_offset),
                    early_finish=self._finish_date(base_date, early_start_offset, duration),
                    late_start=base_date + timedelta(days=late_start_offset),
                    late_finish=self._finish_date(base_date, late_start_offset, duration),
                    total_float_days=total_float,
                    critical=total_float == 0,
                )
            )

        critical_ids = {
            schedule.task_id for schedule in schedules if schedule.critical
        }
        critical_successors: dict[str, list[str]] = {task_id: [] for task_id in critical_ids}
        critical_incoming: set[str] = set()
        for predecessor_id in critical_ids:
            for successor_id, weight in successors[predecessor_id]:
                if (
                    successor_id in critical_ids
                    and early_starts[successor_id] == early_starts[predecessor_id] + weight
                ):
                    critical_successors[predecessor_id].append(successor_id)
                    critical_incoming.add(successor_id)
        critical_paths: list[tuple[str, ...]] = []
        roots = sorted(critical_ids - critical_incoming, key=lambda task_id: codes[task_id])
        for root in roots:
            self._collect_critical_paths(
                root, critical_successors, codes, (codes[root],), critical_paths
            )

        project_finish = self._finish_date(base_date, 0, project_duration)
        return ScheduleResult(
            project_start=base_date,
            project_finish=project_finish,
            duration_days=project_duration,
            tasks=tuple(schedules),
            critical_paths=tuple(critical_paths),
        )

    @staticmethod
    def _duration_days(task: TaskModel) -> int:
        if task.wbs_node.node_type == "milestone":
            return 0
        if task.planned_start and task.planned_end:
            return max(1, (task.planned_end - task.planned_start).days + 1)
        return 1

    @staticmethod
    def _dependency_weight(
        dependency_type: str,
        predecessor_duration: int,
        successor_duration: int,
        lag_days: int,
    ) -> int:
        weights = {
            "FS": predecessor_duration + lag_days,
            "SS": lag_days,
            "FF": predecessor_duration + lag_days - successor_duration,
            "SF": lag_days - successor_duration,
        }
        try:
            return weights[dependency_type]
        except KeyError as exc:
            raise ValueError(f"Type de dépendance inconnu : {dependency_type}") from exc

    @staticmethod
    def _finish_date(base_date: date, start_offset: int, duration: int) -> date:
        return base_date + timedelta(days=start_offset + max(0, duration - 1))

    @classmethod
    def _collect_critical_paths(
        cls,
        task_id: str,
        successors: dict[str, list[str]],
        codes: dict[str, str],
        path: tuple[str, ...],
        result: list[tuple[str, ...]],
    ) -> None:
        next_tasks = sorted(successors[task_id], key=lambda next_id: codes[next_id])
        if not next_tasks:
            result.append(path)
            return
        for successor_id in next_tasks:
            cls._collect_critical_paths(
                successor_id,
                successors,
                codes,
                (*path, codes[successor_id]),
                result,
            )

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
