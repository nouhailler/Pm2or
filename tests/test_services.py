from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pm2.application.context import ApplicationContext
from pm2.application.services import (
    AcceptanceService,
    GateService,
    ProjectMethodologyError,
    ProjectService,
    RegisterService,
    ResponsibilityService,
    TraceabilityService,
    WorkflowService,
    WorkPlanService,
)
from pm2.application.validation import ValidationService
from pm2.domain.enums import WorkflowError
from pm2.infrastructure.orm import (
    AcceptanceCriterionModel,
    AcceptancePlanModel,
    AcceptanceTestModel,
    AuditEventModel,
    DeliverableModel,
    IssueModel,
    ProjectModel,
    RequirementModel,
    RiskModel,
    RoleModel,
)


def test_project_creation_has_lifecycle_governance_and_audit(
    session: Session, project: object
) -> None:
    assert project.current_phase == "LAUNCH"
    assert len(project.phases) == 4
    assert {item.role_code for item in project.role_assignments} == {"PM", "PO"}
    assert session.scalar(select(func.count()).select_from(RoleModel)) >= 14
    assert session.scalar(select(func.count()).select_from(AuditEventModel)) == 1


def test_project_keeps_frozen_methodology_until_explicit_upgrade(
    session: Session,
    project: ProjectModel,
    context: ApplicationContext,
) -> None:
    original_hash = project.methodology_hash
    original_snapshot = project.methodology_snapshot
    assert len(original_hash) == 64
    assert "methodology:" in project.methodology_snapshot

    future_identity = context.methodology.methodology.model_copy(update={"version": "3.2"})
    future = context.methodology.model_copy(update={"methodology": future_identity})
    service = ProjectService(session, future)

    frozen = service.methodology_for(project)
    assert frozen.methodology.version == "3.1"
    assert project.methodology_hash == original_hash
    assert not service.uses_current_methodology(project)

    upgraded = service.upgrade_methodology(project, actor="testeur")
    assert upgraded.methodology.version == "3.2"
    assert project.methodology_version == "3.2"
    assert project.methodology_hash != original_hash
    upgrade_event = session.scalar(
        select(AuditEventModel).where(AuditEventModel.action == "METHODOLOGY_UPGRADE")
    )
    import json

    assert json.loads(upgrade_event.old_value_json)["methodology_snapshot"] == original_snapshot
    assert (
        session.scalar(
            select(func.count())
            .select_from(AuditEventModel)
            .where(AuditEventModel.action == "METHODOLOGY_UPGRADE")
        )
        == 1
    )


def test_legacy_matching_project_gets_audited_snapshot_backfill(
    session: Session,
    project: ProjectModel,
    context: ApplicationContext,
) -> None:
    project.methodology_hash = ""
    project.methodology_snapshot = ""
    service = ProjectService(session, context.methodology)

    restored = service.methodology_for(project)

    assert restored.methodology.version == "3.1"
    assert len(project.methodology_hash) == 64
    assert (
        session.scalar(
            select(func.count())
            .select_from(AuditEventModel)
            .where(AuditEventModel.action == "METHODOLOGY_SNAPSHOT_BACKFILL")
        )
        == 1
    )


@pytest.mark.parametrize(
    "damage", ["missing_hash", "missing_snapshot", "altered_snapshot", "legacy_version"]
)
def test_project_rejects_incomplete_or_unrecoverable_methodology(
    session: Session, project: ProjectModel, context: ApplicationContext, damage: str
) -> None:
    if damage == "missing_hash":
        project.methodology_hash = ""
    elif damage == "missing_snapshot":
        project.methodology_snapshot = ""
    elif damage == "altered_snapshot":
        project.methodology_snapshot += "\n# altered\n"
    else:
        project.methodology_snapshot = ""
        project.methodology_hash = ""
        project.methodology_version = "3.0"
    with pytest.raises(ProjectMethodologyError):
        ProjectService(session, context.methodology).methodology_for(project)


def test_methodology_change_is_detected_even_without_version_bump(
    session: Session, project: ProjectModel, context: ApplicationContext
) -> None:
    changed = context.methodology.model_copy(
        update={
            "source_notes": {**context.methodology.source_notes, "revision_note": "Nouvelle règle"}
        }
    )
    service = ProjectService(session, changed)
    assert service.methodology.methodology.version == project.methodology_version
    assert not service.uses_current_methodology(project)


def test_rcmsci_uniqueness(session: Session, project: object) -> None:
    service = ResponsibilityService(session)
    service.assign(project.id, "activity", "LA-001", "PM", "R")
    with pytest.raises(ValueError, match="déjà un R"):
        service.assign(project.id, "activity", "LA-001", "BM", "R")
    service.assign(project.id, "activity", "LA-001", "BM", "Cm")
    service.assign(project.id, "activity", "LA-001", "PCT", "S")


def test_work_plan_tree_dates_and_dependency_cycle(session: Session, project: object) -> None:
    service = WorkPlanService(session)
    package = service.create_node(project.id, "1", "Lot", node_type="work_package")
    node_a = service.create_node(project.id, "1.1", "A", node_type="task", parent_id=package.id)
    node_b = service.create_node(project.id, "1.2", "B", node_type="task", parent_id=package.id)
    task_a = service.create_task(
        node_a.id, planned_start=date(2026, 1, 1), planned_end=date(2026, 1, 2)
    )
    task_b = service.create_task(
        node_b.id, planned_start=date(2026, 1, 3), planned_end=date(2026, 1, 4)
    )
    service.add_dependency(task_a.id, task_b.id)
    with pytest.raises(ValueError, match="cycle"):
        service.add_dependency(task_b.id, task_a.id)
    with pytest.raises(ValueError, match="descendant"):
        service.move(package.id, node_a.id)


def test_register_workflows_and_change_approval(session: Session, project: object) -> None:
    registers = RegisterService(session)
    risk = registers.create(
        "risk",
        project.id,
        code="R-1",
        title="Risque",
        probability=4,
        impact=5,
        strategy="Escalade au PSC",
        owner="Alice",
    )
    assert risk.score == 20
    workflow = WorkflowService(session)
    workflow.transition("risk", risk.id, "ASSESSED")
    with pytest.raises(WorkflowError, match="Transition interdite"):
        workflow.transition("risk", risk.id, "CLOSED")

    change = registers.create(
        "change", project.id, code="C-1", title="Changement", impact_scope="Périmètre"
    )
    for target in ("SUBMITTED", "IMPACT_ANALYSIS", "APPROVAL"):
        workflow.transition("change", change.id, target)
    workflow.approve_change(change.id, "Direction")
    workflow.transition("change", change.id, "IMPLEMENTING")
    assert change.status == "IMPLEMENTING"
    assert session.scalar(select(func.count()).select_from(AuditEventModel)) >= 7


def test_issue_close_requires_resolution(session: Session, project: object) -> None:
    issue = RegisterService(session).create(
        "issue", project.id, code="I-1", title="Incident", impact="Fort"
    )
    workflow = WorkflowService(session)
    for target in ("ANALYSIS", "ACTION_PLANNED", "IN_PROGRESS", "RESOLVED"):
        workflow.transition("issue", issue.id, target)
    with pytest.raises(WorkflowError, match="résolution"):
        workflow.transition("issue", issue.id, "CLOSED")
    issue.resolution = "Corrigé"
    workflow.transition("issue", issue.id, "CLOSED")


def test_gate_blocks_then_advances_phase(
    session: Session, project: object, context: ApplicationContext
) -> None:
    service = GateService(session, context.methodology)
    review = service.get_or_create(project.id, "RFP")
    with pytest.raises(WorkflowError, match="obligatoires"):
        service.decide(review.id, "APPROVED", "PSC")
    for item in service.checklist(review.id):
        service.set_item(item.id, True, "Vérifié")
    service.decide(review.id, "APPROVED", "PSC")
    assert project.current_phase == "PLANNING"
    assert project.status == "PLANNING"


def test_acceptance_and_requirement_trace(session: Session, project: object) -> None:
    deliverable = DeliverableModel(
        project_id=project.id,
        code="D-1",
        name="Livrable",
        owner="Alice",
        status="READY_FOR_ACCEPTANCE",
    )
    session.add(deliverable)
    session.flush()
    with pytest.raises(ValueError, match="critère"):
        AcceptanceService(session).accept(deliverable.id, "PO")
    plan = AcceptancePlanModel(project_id=project.id, code="AP-1", title="Plan")
    session.add(plan)
    session.flush()
    criterion = AcceptanceCriterionModel(
        acceptance_plan_id=plan.id,
        deliverable_id=deliverable.id,
        code="AC-1",
        description="Conforme",
    )
    session.add(criterion)
    session.flush()
    test = AcceptanceTestModel(
        criterion_id=criterion.id,
        code="AT-1",
        description="Vérification",
        expected_result="OK",
        outcome="PASSED",
    )
    session.add(test)
    session.flush()
    AcceptanceService(session).accept(deliverable.id, "PO")
    WorkflowService(session).transition("deliverable", deliverable.id, "ACCEPTED")
    assert deliverable.status == "ACCEPTED"

    requirement = RequirementModel(
        project_id=project.id,
        code="REQ-1",
        title="Besoin",
        source="PO",
        priority="HIGH",
        verification_method="Test",
        status="IMPLEMENTED",
    )
    session.add(requirement)
    session.flush()
    with pytest.raises(WorkflowError, match="test d'acceptation"):
        WorkflowService(session).transition("requirement", requirement.id, "VERIFIED")
    TraceabilityService(session).link(
        project.id, "requirement", requirement.id, "acceptance_test", test.id, "verifies"
    )
    WorkflowService(session).transition("requirement", requirement.id, "VERIFIED")


def test_trace_link_and_critical_deletion(session: Session, project: object) -> None:
    service = TraceabilityService(session)
    link = service.link(project.id, "requirement", "a", "task", "b", "implements")
    assert service.links_for("requirement", "a") == [link]
    service.unlink(link.id)
    critical = service.link(project.id, "risk", "r", "task", "t", "mitigates", critical=True)
    with pytest.raises(ValueError, match="critique"):
        service.unlink(critical.id)


def test_validation_detects_high_risk_and_overdue_issue(session: Session, project: object) -> None:
    session.add(
        RiskModel(
            project_id=project.id,
            code="R-H",
            title="Critique",
            probability=5,
            impact=4,
            score=20,
            strategy="",
            status="ASSESSED",
        )
    )
    session.add(
        IssueModel(
            project_id=project.id,
            code="I-L",
            title="Retard",
            impact="",
            status="OPEN",
            due_date=date(2020, 1, 1),
        )
    )
    session.flush()
    codes = {item.code for item in ValidationService(session).validate_project(project.id)}
    assert {"PM2-RISK-003", "PM2-ISSUE-002"} <= codes
