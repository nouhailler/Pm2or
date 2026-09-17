from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.audit import AuditService
from pm2.application.dto import ProjectCreateDTO
from pm2.application.traceability import TraceabilityService as TraceabilityService
from pm2.domain.workflows import DEFAULT_WORKFLOW_ENGINE
from pm2.infrastructure.orm import (
    PersonModel,
    PhaseModel,
    ProjectModel,
    ProjectRoleAssignmentModel,
    RoleModel,
    row_to_dict,
    utcnow,
)
from pm2.infrastructure.repositories import Repository
from pm2.methodology import MethodologyLoader, bundle_methodology, methodology_sha256
from pm2.methodology.loader import MethodologyLoadError
from pm2.methodology.models import PM2Configuration


class ProjectMethodologyError(RuntimeError):
    pass


class ProjectService:
    def __init__(
        self,
        session: Session,
        methodology: PM2Configuration,
        *,
        methodology_snapshot: str | None = None,
        methodology_hash: str | None = None,
    ) -> None:
        self.session = session
        bundle = bundle_methodology(methodology)
        if methodology_snapshot is not None:
            snapshot_configuration = MethodologyLoader.load_text(
                methodology_snapshot, source="snapshot courant"
            )
            if snapshot_configuration != methodology:
                raise ProjectMethodologyError(
                    "Le snapshot fourni ne correspond pas à la méthodologie courante."
                )
            bundle = bundle_methodology(snapshot_configuration)
        if methodology_hash is not None and methodology_hash != bundle.sha256:
            raise ProjectMethodologyError(
                "L’empreinte fournie ne correspond pas au snapshot méthodologique courant."
            )
        self.methodology = bundle.configuration
        self.methodology_snapshot = bundle.snapshot
        self.methodology_hash = bundle.sha256

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
            methodology_hash=self.methodology_hash,
            methodology_snapshot=self.methodology_snapshot,
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

    def methodology_for(self, project: ProjectModel) -> PM2Configuration:
        """Load and validate the immutable methodology owned by a project."""
        if bool(project.methodology_snapshot) != bool(project.methodology_hash):
            raise ProjectMethodologyError(
                "Le snapshot et son empreinte sont incomplets : aucune substitution automatique n’est autorisée."
            )
        if not project.methodology_snapshot and not project.methodology_hash:
            if (
                project.methodology_id != self.methodology.methodology.id
                or project.methodology_version != self.methodology.methodology.version
            ):
                raise ProjectMethodologyError(
                    "Ce projet historique ne contient pas de snapshot méthodologique et sa "
                    "version ne correspond pas à la méthodologie installée."
                )
            project.methodology_snapshot = self.methodology_snapshot
            project.methodology_hash = self.methodology_hash
            AuditService(self.session).record(
                project.id,
                "project",
                project.id,
                "METHODOLOGY_SNAPSHOT_BACKFILL",
                new={
                    "methodology_id": project.methodology_id,
                    "methodology_version": project.methodology_version,
                    "methodology_hash": project.methodology_hash,
                },
            )
        actual_hash = methodology_sha256(project.methodology_snapshot)
        if actual_hash != project.methodology_hash:
            raise ProjectMethodologyError(
                "Le snapshot méthodologique du projet est corrompu : empreinte SHA-256 invalide."
            )
        try:
            configuration = MethodologyLoader.load_text(
                project.methodology_snapshot,
                source=f"projet {project.reference}",
            )
        except MethodologyLoadError as exc:
            raise ProjectMethodologyError(
                "Le snapshot méthodologique du projet est invalide."
            ) from exc
        identity = configuration.methodology
        if identity.id != project.methodology_id or identity.version != project.methodology_version:
            raise ProjectMethodologyError(
                "L’identité du snapshot méthodologique ne correspond pas aux métadonnées du projet."
            )
        return configuration

    def uses_current_methodology(self, project: ProjectModel) -> bool:
        self.methodology_for(project)
        return (
            project.methodology_id == self.methodology.methodology.id
            and project.methodology_version == self.methodology.methodology.version
            and project.methodology_hash == self.methodology_hash
        )

    def upgrade_methodology(
        self, project: ProjectModel, *, actor: str = "local"
    ) -> PM2Configuration:
        """Explicitly replace the frozen snapshot and audit the upgrade."""
        previous = {
            "methodology_id": project.methodology_id,
            "methodology_version": project.methodology_version,
            "methodology_hash": project.methodology_hash,
            "methodology_snapshot": project.methodology_snapshot,
        }
        self.methodology_for(project)
        project.methodology_id = self.methodology.methodology.id
        project.methodology_version = self.methodology.methodology.version
        project.methodology_hash = self.methodology_hash
        project.methodology_snapshot = self.methodology_snapshot
        self.seed_roles()
        existing_phases = set(
            self.session.scalars(
                select(PhaseModel.methodology_phase_code).where(PhaseModel.project_id == project.id)
            )
        )
        for definition in self.methodology.lifecycle.phases:
            if definition.code not in existing_phases:
                self.session.add(
                    PhaseModel(
                        project_id=project.id,
                        methodology_phase_code=definition.code,
                        status="NOT_STARTED",
                    )
                )
        AuditService(self.session).record(
            project.id,
            "project",
            project.id,
            "METHODOLOGY_UPGRADE",
            old=previous,
            new={
                "methodology_id": project.methodology_id,
                "methodology_version": project.methodology_version,
                "methodology_hash": project.methodology_hash,
            },
            actor=actor,
        )
        self.session.flush()
        return self.methodology

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


