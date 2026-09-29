from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pm2.application.audit import AuditService
from pm2.infrastructure.orm import (
    ResourceAvailabilityModel,
    ResourceModel,
    TaskModel,
    TaskResourceAllocationModel,
    WbsNodeModel,
    row_to_dict,
)
from pm2.infrastructure.repositories import Repository

RESOURCE_TYPES = {"PERSON", "TEAM", "SUPPLIER", "EQUIPMENT", "BUDGET"}


@dataclass(frozen=True, slots=True)
class ResourceWeekLoad:
    resource_id: str
    resource_name: str
    resource_type: str
    week_start: date
    availability_percent: Decimal
    capacity_days: Decimal
    allocated_days: Decimal
    utilization_percent: Decimal | None
    overloaded: bool


class ResourceService:
    """Manage project resources, weekly capacity and task effort allocations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        project_id: str,
        name: str,
        resource_type: str,
        *,
        person_id: str | None = None,
        description: str = "",
        default_availability_percent: Decimal = Decimal("100"),
    ) -> ResourceModel:
        name = name.strip()
        resource_type = resource_type.strip().upper()
        availability = Decimal(default_availability_percent)
        if not name:
            raise ValueError("Le nom de la ressource est obligatoire.")
        if resource_type not in RESOURCE_TYPES:
            raise ValueError("Type de ressource invalide.")
        if not Decimal("0") <= availability <= Decimal("100"):
            raise ValueError("La disponibilité doit être comprise entre 0 et 100 %.")
        if resource_type == "PERSON" and not person_id:
            raise ValueError("Une ressource de type personne doit référencer une personne.")
        if resource_type != "PERSON" and person_id:
            raise ValueError("Seule une ressource de type personne peut référencer une personne.")
        resource = ResourceModel(
            project_id=project_id,
            person_id=person_id,
            name=name,
            resource_type=resource_type,
            description=description.strip(),
            default_availability_percent=availability,
        )
        self.session.add(resource)
        self.session.flush()
        AuditService(self.session).record(
            project_id, "resource", resource.id, "CREATE", new=row_to_dict(resource)
        )
        return resource

    def set_weekly_availability(
        self, resource_id: str, week_start: date, availability_percent: Decimal
    ) -> ResourceAvailabilityModel:
        resource = Repository(self.session, ResourceModel).require(resource_id)
        availability = Decimal(availability_percent)
        if not Decimal("0") <= availability <= Decimal("100"):
            raise ValueError("La disponibilité doit être comprise entre 0 et 100 %.")
        monday = week_start - timedelta(days=week_start.weekday())
        existing = self.session.scalar(
            select(ResourceAvailabilityModel).where(
                ResourceAvailabilityModel.resource_id == resource_id,
                ResourceAvailabilityModel.week_start == monday,
            )
        )
        old = row_to_dict(existing) if existing else None
        if existing is None:
            existing = ResourceAvailabilityModel(
                resource=resource,
                week_start=monday,
                availability_percent=availability,
            )
            self.session.add(existing)
        else:
            existing.availability_percent = availability
        self.session.flush()
        AuditService(self.session).record(
            resource.project_id,
            "resource_availability",
            existing.id,
            "UPDATE" if old else "CREATE",
            old=old,
            new=row_to_dict(existing),
        )
        return existing

    def allocate(
        self, task_id: str, resource_id: str, effort_days: Decimal
    ) -> TaskResourceAllocationModel:
        task = Repository(self.session, TaskModel).require(task_id)
        resource = Repository(self.session, ResourceModel).require(resource_id)
        effort = Decimal(effort_days)
        if task.wbs_node.project_id != resource.project_id:
            raise ValueError("La tâche et la ressource doivent appartenir au même projet.")
        if resource.archived:
            raise ValueError("Une ressource archivée ne peut pas être affectée.")
        if effort <= 0:
            raise ValueError("L'effort affecté doit être strictement positif.")
        existing = self.session.scalar(
            select(TaskResourceAllocationModel).where(
                TaskResourceAllocationModel.task_id == task_id,
                TaskResourceAllocationModel.resource_id == resource_id,
            )
        )
        other_effort = Decimal(
            self.session.scalar(
                select(func.coalesce(func.sum(TaskResourceAllocationModel.effort_days), 0)).where(
                    TaskResourceAllocationModel.task_id == task_id,
                    TaskResourceAllocationModel.id != (existing.id if existing else ""),
                )
            )
            or 0
        )
        if task.planned_effort <= 0:
            raise ValueError("Définissez d'abord l'effort planifié de la tâche.")
        if other_effort + effort > task.planned_effort:
            raise ValueError(
                f"L'allocation dépasserait l'effort planifié de {task.planned_effort} j."
            )
        old = row_to_dict(existing) if existing else None
        if existing is None:
            existing = TaskResourceAllocationModel(
                task=task, resource=resource, effort_days=effort
            )
            self.session.add(existing)
        else:
            existing.effort_days = effort
        self.session.flush()
        AuditService(self.session).record(
            resource.project_id,
            "task_resource_allocation",
            existing.id,
            "UPDATE" if old else "CREATE",
            old=old,
            new=row_to_dict(existing),
        )
        return existing

    def remove_allocation(self, allocation_id: str) -> None:
        allocation = Repository(self.session, TaskResourceAllocationModel).require(allocation_id)
        project_id = allocation.resource.project_id
        old = row_to_dict(allocation)
        self.session.delete(allocation)
        AuditService(self.session).record(
            project_id, "task_resource_allocation", allocation_id, "DELETE", old=old
        )
        self.session.flush()

    def archive(self, resource_id: str) -> None:
        resource = Repository(self.session, ResourceModel).require(resource_id)
        if resource.task_allocations:
            raise ValueError("Retirez les allocations avant d'archiver cette ressource.")
        old = row_to_dict(resource)
        resource.archived = True
        AuditService(self.session).record(
            resource.project_id,
            "resource",
            resource.id,
            "ARCHIVE",
            old=old,
            new=row_to_dict(resource),
        )
        self.session.flush()

    def utilization(self, project_id: str) -> tuple[ResourceWeekLoad, ...]:
        resources = list(
            self.session.scalars(
                select(ResourceModel)
                .where(ResourceModel.project_id == project_id, ResourceModel.archived.is_(False))
                .order_by(ResourceModel.name)
            ).all()
        )
        if not resources:
            return ()
        resource_ids = [resource.id for resource in resources]
        overrides = {
            (item.resource_id, item.week_start): item.availability_percent
            for item in self.session.scalars(
                select(ResourceAvailabilityModel).where(
                    ResourceAvailabilityModel.resource_id.in_(resource_ids)
                )
            ).all()
        }
        allocations = list(
            self.session.scalars(
                select(TaskResourceAllocationModel)
                .join(TaskModel)
                .join(WbsNodeModel)
                .where(
                    WbsNodeModel.project_id == project_id,
                    TaskModel.archived.is_(False),
                    TaskResourceAllocationModel.resource_id.in_(resource_ids),
                )
            ).all()
        )
        loads: dict[tuple[str, date], Decimal] = {}
        relevant_weeks = {week for _resource_id, week in overrides}
        for allocation in allocations:
            task = allocation.task
            if not task.planned_start or not task.planned_end:
                continue
            working_days = [
                task.planned_start + timedelta(days=offset)
                for offset in range((task.planned_end - task.planned_start).days + 1)
                if (task.planned_start + timedelta(days=offset)).weekday() < 5
            ]
            if not working_days:
                working_days = [task.planned_start]
            daily_effort = allocation.effort_days / Decimal(len(working_days))
            for working_day in working_days:
                monday = working_day - timedelta(days=working_day.weekday())
                key = (allocation.resource_id, monday)
                loads[key] = loads.get(key, Decimal("0")) + daily_effort
                relevant_weeks.add(monday)
        if not relevant_weeks:
            today = date.today()
            relevant_weeks.add(today - timedelta(days=today.weekday()))

        result: list[ResourceWeekLoad] = []
        for resource in resources:
            for week_start in sorted(relevant_weeks):
                availability = overrides.get(
                    (resource.id, week_start), resource.default_availability_percent
                )
                capacity = Decimal("5") * availability / Decimal("100")
                allocated = loads.get((resource.id, week_start), Decimal("0"))
                utilization = (
                    allocated * Decimal("100") / capacity if capacity > 0 else None
                )
                result.append(
                    ResourceWeekLoad(
                        resource_id=resource.id,
                        resource_name=resource.name,
                        resource_type=resource.resource_type,
                        week_start=week_start,
                        availability_percent=availability,
                        capacity_days=capacity.quantize(Decimal("0.01")),
                        allocated_days=allocated.quantize(Decimal("0.01")),
                        utilization_percent=(
                            utilization.quantize(Decimal("0.1"))
                            if utilization is not None
                            else None
                        ),
                        overloaded=allocated > capacity,
                    )
                )
        return tuple(result)
