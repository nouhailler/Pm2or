from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pm2.application.audit import AuditService
from pm2.application.traceability import TraceabilityService as TraceabilityService
from pm2.infrastructure.orm import (
    PersonModel,
    ProjectRoleAssignmentModel,
    ResponsibilityAssignmentModel,
    StakeholderModel,
    row_to_dict,
)
from pm2.infrastructure.repositories import Repository


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


