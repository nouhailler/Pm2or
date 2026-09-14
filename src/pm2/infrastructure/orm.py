from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def uuid_str() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ArchiveMixin:
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "projects"
    reference: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    sponsor: Mapped[str | None] = mapped_column(String(255))
    business_owner: Mapped[str | None] = mapped_column(String(255))
    project_manager: Mapped[str | None] = mapped_column(String(255))
    methodology_id: Mapped[str] = mapped_column(String(40), default="pm2", nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(20), default="3.1", nullable=False)
    methodology_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    methodology_snapshot: Mapped[str] = mapped_column(Text, default="", nullable=False)
    current_phase: Mapped[str] = mapped_column(String(40), default="LAUNCH", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="LAUNCH", nullable=False, index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    target_end_date: Mapped[date | None] = mapped_column(Date)
    actual_end_date: Mapped[date | None] = mapped_column(Date)
    approved_budget: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    outsourcing_required: Mapped[bool] = mapped_column(Boolean, default=False)
    transition_required: Mapped[bool] = mapped_column(Boolean, default=False)
    organisation_implementation_required: Mapped[bool] = mapped_column(Boolean, default=False)

    phases: Mapped[list[PhaseModel]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    role_assignments: Mapped[list[ProjectRoleAssignmentModel]] = relationship(
        back_populates="project"
    )
    wbs_nodes: Mapped[list[WbsNodeModel]] = relationship(back_populates="project")
    deliverables: Mapped[list[DeliverableModel]] = relationship(back_populates="project")
    requirements: Mapped[list[RequirementModel]] = relationship(back_populates="project")

    __table_args__ = (
        CheckConstraint("approved_budget >= 0", name="ck_project_budget_nonnegative"),
        CheckConstraint(
            "target_end_date IS NULL OR start_date IS NULL OR target_end_date >= start_date",
            name="ck_project_dates",
        ),
    )


class PhaseModel(Base, UUIDMixin):
    __tablename__ = "phases"
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    methodology_phase_code: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="NOT_STARTED", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    project: Mapped[ProjectModel] = relationship(back_populates="phases")
    __table_args__ = (UniqueConstraint("project_id", "methodology_phase_code"),)


class PersonModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "persons"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    organisation: Mapped[str | None] = mapped_column(String(255))
    function: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str] = mapped_column(Text, default="")


class RoleModel(Base):
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(60), default="standard")


class ProjectRoleAssignmentModel(Base, UUIDMixin, ArchiveMixin):
    __tablename__ = "project_role_assignments"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), index=True)
    role_code: Mapped[str] = mapped_column(ForeignKey("roles.code"), index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    project: Mapped[ProjectModel] = relationship(back_populates="role_assignments")
    person: Mapped[PersonModel] = relationship()
    role: Mapped[RoleModel] = relationship()
    __table_args__ = (UniqueConstraint("project_id", "person_id", "role_code", "start_date"),)


class StakeholderModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "stakeholders"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organisation: Mapped[str | None] = mapped_column(String(255))
    function: Mapped[str | None] = mapped_column(String(255))
    interest: Mapped[str | None] = mapped_column(String(40))
    influence: Mapped[str | None] = mapped_column(String(40))
    engagement_level: Mapped[str | None] = mapped_column(String(40))
    strategy: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", index=True)


class ResponsibilityAssignmentModel(Base, UUIDMixin):
    __tablename__ = "responsibility_assignments"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    subject_type: Mapped[str] = mapped_column(String(60), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(80), nullable=False)
    role_code: Mapped[str] = mapped_column(ForeignKey("roles.code"), index=True)
    responsibility_type: Mapped[str] = mapped_column(String(4), nullable=False)
    __table_args__ = (
        UniqueConstraint("project_id", "subject_type", "subject_id", "role_code"),
        CheckConstraint("responsibility_type IN ('R','Cm','S','C','I')", name="ck_ram_type"),
        Index(
            "uq_ram_one_r",
            "project_id",
            "subject_type",
            "subject_id",
            unique=True,
            sqlite_where=text("responsibility_type = 'R'"),
        ),
        Index(
            "uq_ram_one_cm",
            "project_id",
            "subject_type",
            "subject_id",
            unique=True,
            sqlite_where=text("responsibility_type = 'Cm'"),
        ),
    )


class WbsNodeModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "wbs_nodes"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("wbs_nodes.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    node_type: Mapped[str] = mapped_column(String(40), default="task")
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    project: Mapped[ProjectModel] = relationship(back_populates="wbs_nodes")
    parent: Mapped[WbsNodeModel | None] = relationship(
        remote_side="WbsNodeModel.id", back_populates="children"
    )
    children: Mapped[list[WbsNodeModel]] = relationship(back_populates="parent")
    task: Mapped[TaskModel | None] = relationship(back_populates="wbs_node", uselist=False)
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class TaskModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "tasks"
    wbs_node_id: Mapped[str] = mapped_column(
        ForeignKey("wbs_nodes.id", ondelete="CASCADE"), unique=True
    )
    owner_person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="NOT_STARTED", index=True)
    planned_start: Mapped[date | None] = mapped_column(Date, index=True)
    planned_end: Mapped[date | None] = mapped_column(Date, index=True)
    actual_start: Mapped[date | None] = mapped_column(Date)
    actual_end: Mapped[date | None] = mapped_column(Date)
    planned_effort: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    actual_effort: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    planned_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    wbs_node: Mapped[WbsNodeModel] = relationship(back_populates="task")
    __table_args__ = (
        CheckConstraint("progress_percent BETWEEN 0 AND 100", name="ck_task_progress"),
        CheckConstraint(
            "planned_end IS NULL OR planned_start IS NULL OR planned_end >= planned_start",
            name="ck_task_planned_dates",
        ),
        CheckConstraint(
            "actual_end IS NULL OR actual_start IS NULL OR actual_end >= actual_start",
            name="ck_task_actual_dates",
        ),
    )


class TaskDependencyModel(Base, UUIDMixin):
    __tablename__ = "task_dependencies"
    predecessor_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    successor_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    dependency_type: Mapped[str] = mapped_column(String(8), default="FS")
    lag_days: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint("predecessor_task_id", "successor_task_id"),
        CheckConstraint("predecessor_task_id != successor_task_id", name="ck_task_dependency_self"),
    )


class DeliverableModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "deliverables"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str | None] = mapped_column(String(255), index=True)
    planned_date: Mapped[date | None] = mapped_column(Date)
    actual_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="PLANNED", index=True)
    acceptance_status: Mapped[str] = mapped_column(String(40), default="NOT_STARTED")
    project: Mapped[ProjectModel] = relationship(back_populates="deliverables")
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class RequirementModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "requirements"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str | None] = mapped_column(String(255))
    priority: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    approval_status: Mapped[str] = mapped_column(String(40), default="PENDING")
    verification_method: Mapped[str | None] = mapped_column(String(255))
    project: Mapped[ProjectModel] = relationship(back_populates="requirements")
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class RequirementTaskModel(Base, UUIDMixin):
    __tablename__ = "requirement_tasks"
    requirement_id: Mapped[str] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    __table_args__ = (UniqueConstraint("requirement_id", "task_id"),)


class RequirementDeliverableModel(Base, UUIDMixin):
    __tablename__ = "requirement_deliverables"
    requirement_id: Mapped[str] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    deliverable_id: Mapped[str] = mapped_column(
        ForeignKey("deliverables.id", ondelete="CASCADE"), index=True
    )
    __table_args__ = (UniqueConstraint("requirement_id", "deliverable_id"),)


class RegisterMixin(UUIDMixin, TimestampMixin, ArchiveMixin):
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str | None] = mapped_column(String(255), index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)


class RiskModel(Base, RegisterMixin):
    __tablename__ = "risks"
    cause: Mapped[str] = mapped_column(Text, default="")
    consequence: Mapped[str] = mapped_column(Text, default="")
    probability: Mapped[int | None] = mapped_column(Integer)
    impact: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[int | None] = mapped_column(Integer, index=True)
    tolerance_status: Mapped[str | None] = mapped_column(String(40))
    strategy: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)
    __table_args__ = (
        UniqueConstraint("project_id", "code"),
        CheckConstraint(
            "probability IS NULL OR probability BETWEEN 1 AND 5", name="ck_risk_probability"
        ),
        CheckConstraint("impact IS NULL OR impact BETWEEN 1 AND 5", name="ck_risk_impact"),
    )


class RiskActionModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "risk_actions"
    risk_id: Mapped[str] = mapped_column(ForeignKey("risks.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    owner: Mapped[str | None] = mapped_column(String(255), index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)


class IssueModel(Base, RegisterMixin):
    __tablename__ = "issues"
    impact: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str | None] = mapped_column(String(40))
    resolution: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class IssueActionModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "issue_actions"
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    owner: Mapped[str | None] = mapped_column(String(255), index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)


class DecisionModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "decisions"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    decision_date: Mapped[date | None] = mapped_column(Date)
    decision_owner: Mapped[str | None] = mapped_column(String(255), index=True)
    outcome: Mapped[str] = mapped_column(Text, default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class ChangeModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "changes"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    requester: Mapped[str | None] = mapped_column(String(255))
    request_date: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    impact_scope: Mapped[str] = mapped_column(Text, default="")
    impact_schedule: Mapped[str] = mapped_column(Text, default="")
    impact_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    impact_quality: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    approver: Mapped[str | None] = mapped_column(String(255))
    approval_date: Mapped[date | None] = mapped_column(Date)
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class ChangeImpactModel(Base, UUIDMixin):
    __tablename__ = "change_impacts"
    change_id: Mapped[str] = mapped_column(ForeignKey("changes.id", ondelete="CASCADE"), index=True)
    impact_type: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))


class ChangeApprovalModel(Base, UUIDMixin):
    __tablename__ = "change_approvals"
    change_id: Mapped[str] = mapped_column(ForeignKey("changes.id", ondelete="CASCADE"), index=True)
    decision: Mapped[str] = mapped_column(String(40))
    approver: Mapped[str] = mapped_column(String(255))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    comments: Mapped[str] = mapped_column(Text, default="")


class QualityControlModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "quality_controls"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(255))
    control_date: Mapped[date | None] = mapped_column(Date)
    owner: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(40), default="PLANNED", index=True)
    result: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class QualityFindingModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "quality_findings"
    quality_control_id: Mapped[str] = mapped_column(
        ForeignKey("quality_controls.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(40), default="MINOR")
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)


class QualityActionModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "quality_actions"
    finding_id: Mapped[str] = mapped_column(
        ForeignKey("quality_findings.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    owner: Mapped[str | None] = mapped_column(String(255), index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)
    evidence: Mapped[str] = mapped_column(Text, default="")
    evidence_required: Mapped[bool] = mapped_column(Boolean, default=False)


class AcceptancePlanModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "acceptance_plans"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class AcceptanceCriterionModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "acceptance_criteria"
    acceptance_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("acceptance_plans.id"), index=True
    )
    deliverable_id: Mapped[str] = mapped_column(ForeignKey("deliverables.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text)
    applicable: Mapped[bool] = mapped_column(Boolean, default=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", index=True)


class AcceptanceTestModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "acceptance_tests"
    criterion_id: Mapped[str] = mapped_column(
        ForeignKey("acceptance_criteria.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text)
    expected_result: Mapped[str] = mapped_column(Text, default="")
    actual_result: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str | None] = mapped_column(String(40))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AcceptanceModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "acceptances"
    deliverable_id: Mapped[str] = mapped_column(ForeignKey("deliverables.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", index=True)
    accepted_by: Mapped[str | None] = mapped_column(String(255))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comments: Mapped[str] = mapped_column(Text, default="")
    final: Mapped[bool] = mapped_column(Boolean, default=False)


class PlannedActivityMixin(UUIDMixin, TimestampMixin, ArchiveMixin):
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str | None] = mapped_column(String(255), index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="PLANNED", index=True)


class TransitionActivityModel(Base, PlannedActivityMixin):
    __tablename__ = "transition_activities"
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class ImplementationActivityModel(Base, PlannedActivityMixin):
    __tablename__ = "implementation_activities"
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class MeetingModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "meetings"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(255))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(255))
    agenda: Mapped[str] = mapped_column(Text, default="")
    minutes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="PLANNED", index=True)
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class MeetingParticipantModel(Base, UUIDMixin):
    __tablename__ = "meeting_participants"
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(80))
    attended: Mapped[bool] = mapped_column(Boolean, default=False)


class MeetingActionModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "meeting_actions"
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    owner: Mapped[str | None] = mapped_column(String(255), index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)


class CommunicationModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "communications"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    audience: Mapped[str] = mapped_column(Text, default="")
    channel: Mapped[str | None] = mapped_column(String(80))
    frequency: Mapped[str | None] = mapped_column(String(80))
    owner: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(40), default="PLANNED", index=True)


class ReportModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "reports"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(255))
    report_type: Mapped[str] = mapped_column(String(80))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)


class DocumentModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "documents"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(80), index=True)
    artifact_code: Mapped[str | None] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    author: Mapped[str | None] = mapped_column(String(255))
    reviewer: Mapped[str | None] = mapped_column(String(255))
    approver: Mapped[str | None] = mapped_column(String(255))
    approval_date: Mapped[date | None] = mapped_column(Date)
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class DocumentVersionModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_versions"
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    file_path: Mapped[str | None] = mapped_column(Text)
    baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("document_id", "version"),)


class DocumentLinkModel(Base, UUIDMixin):
    __tablename__ = "document_links"
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    relation_type: Mapped[str] = mapped_column(String(40), default="referenced_by")


class GateReviewModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "gate_reviews"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    gate_code: Mapped[str] = mapped_column(String(20), index=True)
    from_phase: Mapped[str] = mapped_column(String(40))
    to_phase: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="NOT_READY", index=True)
    comments: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("project_id", "gate_code"),)


class GateChecklistItemModel(Base, UUIDMixin):
    __tablename__ = "gate_checklist_items"
    gate_review_id: Mapped[str] = mapped_column(
        ForeignKey("gate_reviews.id", ondelete="CASCADE"), index=True
    )
    item_code: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    satisfied: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("gate_review_id", "item_code"),)


class GateDecisionModel(Base, UUIDMixin):
    __tablename__ = "gate_decisions"
    gate_review_id: Mapped[str] = mapped_column(
        ForeignKey("gate_reviews.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(40))
    decided_by: Mapped[str] = mapped_column(String(255))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    comments: Mapped[str] = mapped_column(Text, default="")


class TraceLinkModel(Base, UUIDMixin):
    __tablename__ = "trace_links"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    critical: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "target_type", "target_id", "relation_type"),
        Index("ix_trace_source", "source_type", "source_id"),
        Index("ix_trace_target", "target_type", "target_id"),
        CheckConstraint(
            "NOT (source_type = target_type AND source_id = target_id)", name="ck_trace_self"
        ),
    )


class LessonLearnedModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "lessons_learned"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(80))
    impact: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)


class RecommendationModel(Base, UUIDMixin, TimestampMixin, ArchiveMixin):
    __tablename__ = "recommendations"
    lesson_learned_id: Mapped[str] = mapped_column(ForeignKey("lessons_learned.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)


class AuditEventModel(Base, UUIDMixin):
    __tablename__ = "audit_events"
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(255), default="local")
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(80))
    old_value_json: Mapped[str | None] = mapped_column(Text)
    new_value_json: Mapped[str | None] = mapped_column(Text)


class SettingModel(Base, UUIDMixin):
    __tablename__ = "settings"
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), index=True)
    key: Mapped[str] = mapped_column(String(120), index=True)
    value_json: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("project_id", "key"),)


MODEL_BY_KIND: dict[str, type[Base]] = {
    "project": ProjectModel,
    "person": PersonModel,
    "stakeholder": StakeholderModel,
    "wbs_node": WbsNodeModel,
    "task": TaskModel,
    "deliverable": DeliverableModel,
    "requirement": RequirementModel,
    "risk": RiskModel,
    "issue": IssueModel,
    "decision": DecisionModel,
    "change": ChangeModel,
    "quality_control": QualityControlModel,
    "acceptance": AcceptanceModel,
    "meeting": MeetingModel,
    "document": DocumentModel,
    "gate_review": GateReviewModel,
    "trace_link": TraceLinkModel,
}

ALL_MODELS_BY_TABLE: dict[str, type[Base]] = {
    mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers
}


def row_to_dict(row: Base) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}
