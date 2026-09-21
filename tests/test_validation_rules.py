from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.validation import ValidationService
from pm2.infrastructure.orm import (
    AcceptanceCriterionModel,
    AcceptanceTestModel,
    ChangeModel,
    DecisionModel,
    DeliverableModel,
    GateChecklistItemModel,
    GateReviewModel,
    IssueModel,
    ProjectModel,
    ProjectRoleAssignmentModel,
    QualityActionModel,
    QualityControlModel,
    QualityFindingModel,
    RequirementModel,
    RiskModel,
)


def test_validation_reports_all_major_inconsistent_states(
    session: Session, project: ProjectModel
) -> None:
    project.name = " "
    project.reference = " "
    project.methodology_id = "other"
    for assignment in project.role_assignments:
        assignment.active = False

    accepted = DeliverableModel(
        project_id=project.id,
        code="DEL-BROKEN",
        name="Livrable incohérent",
        owner=None,
        planned_date=None,
        status="ACCEPTED",
    )
    without_criteria = DeliverableModel(
        project_id=project.id,
        code="DEL-NO-CRITERIA",
        name="Sans critères",
        owner="Alice",
        planned_date=date.today(),
    )
    session.add_all([accepted, without_criteria])
    session.flush()
    criterion = AcceptanceCriterionModel(
        deliverable_id=accepted.id,
        code="AC-BROKEN",
        description="Critère",
    )
    session.add(criterion)
    session.flush()
    session.add_all(
        [
            AcceptanceTestModel(
                criterion_id=criterion.id,
                code="AT-FAILED",
                description="Test échoué",
                expected_result="OK",
                outcome="FAILED",
            ),
            AcceptanceTestModel(
                criterion_id=criterion.id,
                code="AT-EMPTY",
                description="Test incomplet",
                expected_result="",
                outcome=None,
            ),
            RequirementModel(
                project_id=project.id,
                code="REQ-BROKEN",
                title="Exigence incohérente",
                status="VERIFIED",
                source=None,
                priority=None,
                verification_method=None,
            ),
            RiskModel(
                project_id=project.id,
                code="R-NO-RATING",
                title="Non évalué",
                status="ASSESSED",
            ),
            RiskModel(
                project_id=project.id,
                code="R-BROKEN",
                title="Score incohérent",
                status="ASSESSED",
                probability=5,
                impact=4,
                score=19,
                strategy="Réduire",
                tolerance_status="BEYOND",
            ),
            IssueModel(
                project_id=project.id,
                code="I-CLOSED",
                title="Clos sans résolution",
                status="CLOSED",
                resolution="",
            ),
            IssueModel(
                project_id=project.id,
                code="I-LATE",
                title="En retard",
                status="OPEN",
                due_date=date(2020, 1, 1),
            ),
            ChangeModel(
                project_id=project.id,
                code="C-BROKEN",
                title="Sans analyse",
                status="IMPLEMENTING",
            ),
            DecisionModel(
                project_id=project.id,
                code="D-ORPHAN",
                title="Sans trace",
            ),
        ]
    )
    control = QualityControlModel(project_id=project.id, code="QC-1", title="Contrôle")
    session.add(control)
    session.flush()
    finding = QualityFindingModel(quality_control_id=control.id, title="Constat")
    session.add(finding)
    session.flush()
    session.add(
        QualityActionModel(
            finding_id=finding.id,
            title="Action sans preuve",
            status="CLOSED",
            evidence_required=True,
            evidence="",
        )
    )
    gate = GateReviewModel(
        project_id=project.id,
        gate_code="BROKEN",
        from_phase="LAUNCH",
        to_phase="PLANNING",
        status="APPROVED_WITH_RESERVES",
    )
    session.add(gate)
    session.flush()
    session.add(
        GateChecklistItemModel(
            gate_review_id=gate.id,
            item_code="MANDATORY",
            description="Obligatoire",
            required=True,
            satisfied=False,
        )
    )
    session.flush()

    problems = ValidationService(session).validate_project(project.id)
    codes = {problem.code for problem in problems}
    assert {
        "PM2-PROJECT-001",
        "PM2-PROJECT-002",
        "PM2-GOV-001",
        "PM2-GOV-003",
        "PM2-GOV-004",
        "PM2-DEL-001",
        "PM2-DEL-002",
        "PM2-DEL-003",
        "PM2-DEL-004",
        "PM2-ACC-001",
        "PM2-ACC-002",
        "PM2-REQ-001",
        "PM2-REQ-002",
        "PM2-REQ-003",
        "PM2-RISK-001",
        "PM2-RISK-002",
        "PM2-RISK-003",
        "PM2-RISK-004",
        "PM2-ISSUE-001",
        "PM2-ISSUE-002",
        "PM2-CHANGE-001",
        "PM2-CHANGE-002",
        "PM2-QUAL-001",
        "PM2-GATE-001",
        "PM2-GATE-002",
        "PM2-TRACE-001",
    } <= codes
    assert [problem.severity for problem in problems] == sorted(
        (problem.severity for problem in problems),
        key={"ERROR": 0, "WARNING": 1, "INFO": 2}.get,
    )
    assert ValidationService.filtered(problems, "INFO") == [
        problem for problem in problems if problem.severity == "INFO"
    ]
    assert ValidationService.filtered(problems, None) == problems


def test_validation_rejects_unknown_project_and_duplicate_project_managers(
    session: Session, project: ProjectModel
) -> None:
    assignments = session.scalars(
        select(ProjectRoleAssignmentModel).where(
            ProjectRoleAssignmentModel.project_id == project.id
        )
    ).all()
    assert len(assignments) == 2
    assignments[1].role_code = "PM"
    session.flush()

    codes = {problem.code for problem in ValidationService(session).validate_project(project.id)}
    assert "PM2-GOV-002" in codes
    with pytest.raises(LookupError, match="introuvable"):
        ValidationService(session).validate_project("missing")
