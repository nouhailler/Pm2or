from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from pm2.domain.enums import PhaseCode, ProjectStatus


def new_id() -> str:
    return str(uuid4())


def now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class Project:
    reference: str
    name: str
    description: str = ""
    id: str = field(default_factory=new_id)
    sponsor: str | None = None
    business_owner: str | None = None
    project_manager: str | None = None
    methodology_id: str = "pm2"
    methodology_version: str = "3.1"
    current_phase: PhaseCode = PhaseCode.LAUNCH
    status: ProjectStatus = ProjectStatus.LAUNCH
    start_date: date | None = None
    target_end_date: date | None = None
    actual_end_date: date | None = None
    approved_budget: Decimal = Decimal("0")
    currency: str = "EUR"

    def __post_init__(self) -> None:
        if not self.reference.strip() or not self.name.strip():
            raise ValueError("Le nom et la référence du projet sont obligatoires.")
        if self.approved_budget < 0:
            raise ValueError("Le budget approuvé ne peut pas être négatif.")
        if self.start_date and self.target_end_date and self.target_end_date < self.start_date:
            raise ValueError("La date de fin cible doit suivre la date de début.")


@dataclass(slots=True)
class WorkItem:
    project_id: str
    code: str
    title: str
    id: str = field(default_factory=new_id)
    description: str = ""
    status: str = "OPEN"


@dataclass(slots=True)
class Task:
    wbs_node_id: str
    id: str = field(default_factory=new_id)
    planned_start: date | None = None
    planned_end: date | None = None
    progress_percent: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.progress_percent <= 100:
            raise ValueError("L'avancement doit être compris entre 0 et 100.")
        if self.planned_start and self.planned_end and self.planned_end < self.planned_start:
            raise ValueError("La fin planifiée doit suivre le début planifié.")


@dataclass(slots=True)
class ResponsibilityAssignment:
    project_id: str
    subject_type: str
    subject_id: str
    role_code: str
    responsibility_type: str
    id: str = field(default_factory=new_id)


@dataclass(frozen=True, slots=True)
class ValidationProblem:
    code: str
    severity: str
    message: str
    entity: str
    entity_id: str | None = None


@dataclass(slots=True)
class WorkflowTransition:
    entity_type: str
    entity_id: str
    from_status: str
    to_status: str
    actor: str = "local"
    at: datetime = field(default_factory=now_utc)


# Explicit lightweight domain types keep the complete vocabulary available without
# coupling it to persistence. Rich behavior lives in application services.
_ENTITY_NAMES = (
    "Phase Person Role ProjectRoleAssignment Stakeholder WbsNode TaskDependency "
    "Deliverable Requirement Risk Issue Decision ChangeRequest QualityControl "
    "QualityFinding QualityAction AcceptancePlan AcceptanceCriterion AcceptanceTest "
    "Acceptance TransitionActivity ImplementationActivity Meeting MeetingParticipant "
    "MeetingAction Communication Report Document DocumentVersion GateReview "
    "GateChecklistItem GateDecision TraceLink LessonLearned Recommendation AuditEvent"
)


@dataclass(slots=True)
class EntityRef:
    id: str = field(default_factory=new_id)


for _name in _ENTITY_NAMES.split():
    if _name not in globals():
        globals()[_name] = type(_name, (EntityRef,), {"__module__": __name__})
