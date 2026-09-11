from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pm2.application.dto import ProjectCreateDTO
from pm2.domain.enums import GateDecisionType, WorkflowError
from pm2.domain.workflows import DEFAULT_WORKFLOW_ENGINE
from pm2.infrastructure.orm import (
    MODEL_BY_KIND,
    AcceptanceCriterionModel,
    AcceptanceModel,
    AcceptancePlanModel,
    AcceptanceTestModel,
    AuditEventModel,
    ChangeApprovalModel,
    ChangeModel,
    DeliverableModel,
    DocumentModel,
    GateChecklistItemModel,
    GateDecisionModel,
    GateReviewModel,
    ImplementationActivityModel,
    IssueModel,
    MeetingActionModel,
    MeetingModel,
    MeetingParticipantModel,
    PersonModel,
    PhaseModel,
    ProjectModel,
    ProjectRoleAssignmentModel,
    QualityActionModel,
    QualityControlModel,
    QualityFindingModel,
    RequirementDeliverableModel,
    RequirementModel,
    RequirementTaskModel,
    ResponsibilityAssignmentModel,
    RiskModel,
    RoleModel,
    StakeholderModel,
    TaskDependencyModel,
    TaskModel,
    TraceLinkModel,
    TransitionActivityModel,
    WbsNodeModel,
    row_to_dict,
    utcnow,
)
from pm2.infrastructure.repositories import Repository
from pm2.methodology.models import PM2Configuration


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        project_id: str | None,
        entity_type: str,
        entity_id: str,
        action: str,
        *,
        old: Any = None,
        new: Any = None,
        actor: str = "local",
    ) -> AuditEventModel:
        event = AuditEventModel(
            project_id=project_id,
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_value_json=_json(old) if old is not None else None,
            new_value_json=_json(new) if new is not None else None,
        )
        self.session.add(event)
        self.session.flush()
        return event


class ProjectService:
    def __init__(self, session: Session, methodology: PM2Configuration) -> None:
        self.session = session
        self.methodology = methodology

    def seed_roles(self) -> None:
        roles = [*self.methodology.roles.standard, *self.methodology.roles.support]
        for definition in roles:
            if self.session.get(RoleModel, definition.code) is None:
                self.session.add(
                    RoleModel(
                        code=definition.code,
                        name=definition.name,
                        description=definition.note or "",
                        category="support" if definition.optional else "standard",
                    )
                )

    def create(
        self,
        *,
        reference: str,
        name: str,
        description: str = "",
        project_manager: str = "",
        project_owner: str = "",
        approved_budget: Decimal = Decimal("0"),
        currency: str = "EUR",
        start_date: date | None = None,
        target_end_date: date | None = None,
    ) -> ProjectModel:
        dto = ProjectCreateDTO(
            reference=reference,
            name=name,
            description=description,
            project_manager=project_manager,
            project_owner=project_owner,
            approved_budget=approved_budget,
            currency=currency,
            start_date=start_date,
            target_end_date=target_end_date,
        )
        self.seed_roles()
        project = ProjectModel(
            reference=dto.reference,
            name=dto.name,
            description=dto.description,
            project_manager=dto.project_manager or None,
            business_owner=dto.project_owner or None,
            approved_budget=dto.approved_budget,
            currency=dto.currency.upper(),
            start_date=dto.start_date,
            target_end_date=dto.target_end_date,
            methodology_id=self.methodology.methodology.id,
            methodology_version=self.methodology.methodology.version,
            current_phase="LAUNCH",
            status="LAUNCH",
        )
        self.session.add(project)
        self.session.flush()
        for definition in self.methodology.lifecycle.phases:
            self.session.add(
                PhaseModel(
                    project_id=project.id,
                    methodology_phase_code=definition.code,
                    status="IN_PROGRESS" if definition.code == "LAUNCH" else "NOT_STARTED",
                    started_at=utcnow() if definition.code == "LAUNCH" else None,
                )
            )
        for person_name, role_code in ((dto.project_manager, "PM"), (dto.project_owner, "PO")):
            if person_name:
                person = PersonModel(name=person_name)
                self.session.add(person)
                self.session.flush()
                self.session.add(
                    ProjectRoleAssignmentModel(
                        project_id=project.id,
                        person_id=person.id,
                        role_code=role_code,
                        active=True,
                        start_date=dto.start_date,
                    )
                )
        AuditService(self.session).record(
            project.id, "project", project.id, "CREATE", new=row_to_dict(project)
        )
        self.session.flush()
        return project

    def list(self) -> Sequence[ProjectModel]:
        return self.session.scalars(
            select(ProjectModel)
            .where(ProjectModel.deleted_at.is_(None))
            .order_by(ProjectModel.updated_at.desc())
        ).all()

    def get(self, project_id: str) -> ProjectModel:
        return Repository(self.session, ProjectModel).require(project_id)

    def close(self, project_id: str, *, actor: str = "local") -> ProjectModel:
        project = self.get(project_id)
        DEFAULT_WORKFLOW_ENGINE.validate("project", project.status, "CLOSED")
        old = row_to_dict(project)
        project.status = "CLOSED"
        project.actual_end_date = date.today()
        phase = self.session.scalar(
            select(PhaseModel).where(
                PhaseModel.project_id == project_id,
                PhaseModel.methodology_phase_code == "CLOSING",
            )
        )
        if phase:
            phase.status = "COMPLETED"
            phase.completed_at = utcnow()
        AuditService(self.session).record(
            project_id,
            "project",
            project.id,
            "TRANSITION:CLOSING→CLOSED",
            old=old,
            new=row_to_dict(project),
            actor=actor,
        )
        return project


class GovernanceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_person(self, **values: Any) -> PersonModel:
        return Repository(self.session, PersonModel).add(PersonModel(**values))

    def assign_role(
        self, project_id: str, person_id: str, role_code: str
    ) -> ProjectRoleAssignmentModel:
        if role_code == "PM":
            current = self.session.scalar(
                select(func.count())
                .select_from(ProjectRoleAssignmentModel)
                .where(
                    ProjectRoleAssignmentModel.project_id == project_id,
                    ProjectRoleAssignmentModel.role_code == "PM",
                    ProjectRoleAssignmentModel.active.is_(True),
                )
            )
            if current:
                raise ValueError("Un seul Chef de Projet (PM) actif peut être désigné.")
        assignment = ProjectRoleAssignmentModel(
            project_id=project_id, person_id=person_id, role_code=role_code, active=True
        )
        self.session.add(assignment)
        self.session.flush()
        AuditService(self.session).record(
            project_id,
            "project_role_assignment",
            assignment.id,
            "CREATE",
            new=row_to_dict(assignment),
        )
        return assignment

    def add_stakeholder(self, project_id: str, name: str, **values: Any) -> StakeholderModel:
        stakeholder = StakeholderModel(project_id=project_id, name=name, **values)
        self.session.add(stakeholder)
        self.session.flush()
        AuditService(self.session).record(
            project_id,
            "stakeholder",
            stakeholder.id,
            "CREATE",
            new=row_to_dict(stakeholder),
        )
        return stakeholder


class StakeholderService(GovernanceService):
    """Service nommé pour le cas d'utilisation de gestion des parties prenantes."""


class ResponsibilityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def assign(
        self,
        project_id: str,
        subject_type: str,
        subject_id: str,
        role_code: str,
        responsibility_type: str,
    ) -> ResponsibilityAssignmentModel:
        if responsibility_type not in {"R", "Cm", "S", "C", "I"}:
            raise ValueError("Type RCmSCI invalide.")
        if responsibility_type in {"R", "Cm"}:
            existing = self.session.scalar(
                select(ResponsibilityAssignmentModel).where(
                    ResponsibilityAssignmentModel.project_id == project_id,
                    ResponsibilityAssignmentModel.subject_type == subject_type,
                    ResponsibilityAssignmentModel.subject_id == subject_id,
                    ResponsibilityAssignmentModel.responsibility_type == responsibility_type,
                )
            )
            if existing:
                raise ValueError(
                    f"Le sujet possède déjà un {responsibility_type}; un seul est autorisé."
                )
        assignment = ResponsibilityAssignmentModel(
            project_id=project_id,
            subject_type=subject_type,
            subject_id=subject_id,
            role_code=role_code,
            responsibility_type=responsibility_type,
        )
        self.session.add(assignment)
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise ValueError(
                "Affectation RCmSCI en conflit avec une affectation existante."
            ) from exc
        return assignment


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


class AcceptanceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def accept(
        self, deliverable_id: str, accepted_by: str, comments: str = "", *, final: bool = True
    ) -> AcceptanceModel:
        criteria = self.session.scalars(
            select(AcceptanceCriterionModel).where(
                AcceptanceCriterionModel.deliverable_id == deliverable_id,
                AcceptanceCriterionModel.applicable.is_(True),
            )
        ).all()
        if not criteria:
            raise ValueError("L'acceptation finale est impossible sans critère applicable.")
        criterion_ids = [criterion.id for criterion in criteria]
        tests_by_criterion = {
            criterion_id: list(
                self.session.scalars(
                    select(AcceptanceTestModel).where(
                        AcceptanceTestModel.criterion_id == criterion_id
                    )
                ).all()
            )
            for criterion_id in criterion_ids
        }
        if final and any(not tests for tests in tests_by_criterion.values()):
            raise ValueError(
                "Chaque critère applicable doit disposer d'au moins un test d'acceptation."
            )
        failed = self.session.scalar(
            select(func.count())
            .select_from(AcceptanceTestModel)
            .where(
                AcceptanceTestModel.criterion_id.in_(criterion_ids),
                or_(
                    AcceptanceTestModel.outcome.is_(None),
                    AcceptanceTestModel.outcome != "PASSED",
                ),
            )
        )
        if final and failed:
            raise ValueError("Tous les tests d'acceptation doivent être exécutés et réussis.")
        acceptance = AcceptanceModel(
            deliverable_id=deliverable_id,
            status="ACCEPTED",
            accepted_by=accepted_by,
            accepted_at=utcnow(),
            comments=comments,
            final=final,
        )
        self.session.add(acceptance)
        self.session.flush()
        deliverable = Repository(self.session, DeliverableModel).require(deliverable_id)
        deliverable.acceptance_status = "ACCEPTED"
        AuditService(self.session).record(
            deliverable.project_id,
            "acceptance",
            acceptance.id,
            "ACCEPT",
            new=row_to_dict(acceptance),
            actor=accepted_by,
        )
        self.session.flush()
        return acceptance

    def create_plan(self, project_id: str, code: str, title: str) -> AcceptancePlanModel:
        plan = AcceptancePlanModel(project_id=project_id, code=code, title=title)
        self.session.add(plan)
        self.session.flush()
        AuditService(self.session).record(
            project_id, "acceptance_plan", plan.id, "CREATE", new=row_to_dict(plan)
        )
        return plan

    def add_criterion(
        self,
        deliverable_id: str,
        code: str,
        description: str,
        *,
        plan_id: str | None = None,
        mandatory: bool = True,
    ) -> AcceptanceCriterionModel:
        criterion = AcceptanceCriterionModel(
            acceptance_plan_id=plan_id,
            deliverable_id=deliverable_id,
            code=code,
            description=description,
            mandatory=mandatory,
        )
        self.session.add(criterion)
        self.session.flush()
        deliverable = Repository(self.session, DeliverableModel).require(deliverable_id)
        AuditService(self.session).record(
            deliverable.project_id,
            "acceptance_criterion",
            criterion.id,
            "CREATE",
            new=row_to_dict(criterion),
        )
        return criterion

    def add_test(
        self, criterion_id: str, code: str, description: str, expected_result: str
    ) -> AcceptanceTestModel:
        if not expected_result.strip():
            raise ValueError("Le résultat attendu du test est obligatoire.")
        test = AcceptanceTestModel(
            criterion_id=criterion_id,
            code=code,
            description=description,
            expected_result=expected_result,
        )
        self.session.add(test)
        self.session.flush()
        criterion = Repository(self.session, AcceptanceCriterionModel).require(criterion_id)
        deliverable = Repository(self.session, DeliverableModel).require(criterion.deliverable_id)
        AuditService(self.session).record(
            deliverable.project_id,
            "acceptance_test",
            test.id,
            "CREATE",
            new=row_to_dict(test),
        )
        return test

    def record_test(self, test_id: str, outcome: str, actual_result: str) -> AcceptanceTestModel:
        if outcome not in {"PASSED", "FAILED", "BLOCKED"}:
            raise ValueError("Résultat de test invalide.")
        test = Repository(self.session, AcceptanceTestModel).require(test_id)
        old = row_to_dict(test)
        test.outcome = outcome
        test.actual_result = actual_result
        test.executed_at = utcnow()
        criterion = Repository(self.session, AcceptanceCriterionModel).require(test.criterion_id)
        deliverable = Repository(self.session, DeliverableModel).require(criterion.deliverable_id)
        AuditService(self.session).record(
            deliverable.project_id,
            "acceptance_test",
            test.id,
            "EXECUTE",
            old=old,
            new=row_to_dict(test),
        )
        self.session.flush()
        return test


class QualityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_control(
        self,
        project_id: str,
        code: str,
        title: str,
        *,
        owner: str | None = None,
        control_date: date | None = None,
    ) -> QualityControlModel:
        control = QualityControlModel(
            project_id=project_id,
            code=code,
            title=title,
            owner=owner,
            control_date=control_date,
            status="PLANNED",
        )
        self.session.add(control)
        self.session.flush()
        return control

    def add_finding(
        self, control_id: str, title: str, *, description: str = "", severity: str = "MINOR"
    ) -> QualityFindingModel:
        finding = QualityFindingModel(
            quality_control_id=control_id,
            title=title,
            description=description,
            severity=severity,
        )
        self.session.add(finding)
        self.session.flush()
        return finding

    def add_action(
        self,
        finding_id: str,
        title: str,
        *,
        owner: str | None = None,
        evidence_required: bool = False,
    ) -> QualityActionModel:
        action = QualityActionModel(
            finding_id=finding_id,
            title=title,
            owner=owner,
            evidence_required=evidence_required,
        )
        self.session.add(action)
        self.session.flush()
        return action


class TransitionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        project_id: str,
        code: str,
        title: str,
        *,
        task_id: str | None = None,
        owner: str | None = None,
        implementation: bool = False,
    ) -> TransitionActivityModel | ImplementationActivityModel:
        model = ImplementationActivityModel if implementation else TransitionActivityModel
        activity = model(
            project_id=project_id,
            code=code,
            title=title,
            task_id=task_id,
            owner=owner,
            status="PLANNED",
        )
        self.session.add(activity)
        self.session.flush()
        return activity


class MeetingService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, project_id: str, code: str, title: str) -> MeetingModel:
        meeting = MeetingModel(project_id=project_id, code=code, title=title, status="PLANNED")
        self.session.add(meeting)
        self.session.flush()
        return meeting

    def add_participant(
        self,
        meeting_id: str,
        name: str,
        *,
        person_id: str | None = None,
        role: str | None = None,
    ) -> MeetingParticipantModel:
        participant = MeetingParticipantModel(
            meeting_id=meeting_id, person_id=person_id, name=name, role=role
        )
        self.session.add(participant)
        self.session.flush()
        return participant

    def add_action(
        self, meeting_id: str, title: str, *, owner: str | None = None
    ) -> MeetingActionModel:
        action = MeetingActionModel(meeting_id=meeting_id, title=title, owner=owner)
        self.session.add(action)
        self.session.flush()
        return action


class TraceabilityService:
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
