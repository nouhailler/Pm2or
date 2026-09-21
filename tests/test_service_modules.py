from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from pm2.application.context import ApplicationContext
from pm2.application.governance import GovernanceService, ResponsibilityService
from pm2.application.operations import MeetingService, QualityService, TransitionService
from pm2.application.planning import DeliverableService, RequirementService, WorkPlanService
from pm2.application.project_service import ProjectService
from pm2.infrastructure.orm import ProjectModel


def test_operational_services_create_quality_transition_and_meeting_data(
    session: Session, project: ProjectModel
) -> None:
    quality = QualityService(session)
    control = quality.create_control(
        project.id, "QC-COVER", "Contrôle", owner="Alice", control_date=date(2026, 9, 21)
    )
    finding = quality.add_finding(
        control.id, "Écart", description="Description", severity="MAJOR"
    )
    action = quality.add_action(
        finding.id, "Corriger", owner="Bob", evidence_required=True
    )
    assert action.finding_id == finding.id

    transition = TransitionService(session)
    activity = transition.create(project.id, "TR-COVER", "Transfert", owner="Alice")
    implementation = transition.create(
        project.id, "IM-COVER", "Déploiement", owner="Bob", implementation=True
    )
    assert activity.__tablename__ == "transition_activities"
    assert implementation.__tablename__ == "implementation_activities"

    meetings = MeetingService(session)
    meeting = meetings.create(project.id, "MEET-COVER", "Comité")
    participant = meetings.add_participant(meeting.id, "Charlie", role="Expert")
    meeting_action = meetings.add_action(meeting.id, "Préparer", owner="Charlie")
    assert participant.meeting_id == meeting.id
    assert meeting_action.meeting_id == meeting.id


def test_governance_and_responsibility_edge_cases(
    session: Session, project: ProjectModel
) -> None:
    governance = GovernanceService(session)
    person = governance.add_person(name="Nouvelle personne", organisation="PMO")
    assignment = governance.assign_role(project.id, person.id, "PCT")
    stakeholder = governance.add_stakeholder(
        project.id, "Partie prenante", organisation="Association"
    )
    assert assignment.role_code == "PCT"
    assert stakeholder.project_id == project.id
    with pytest.raises(ValueError, match="Un seul Chef de Projet"):
        governance.assign_role(project.id, person.id, "PM")

    responsibilities = ResponsibilityService(session)
    with pytest.raises(ValueError, match="invalide"):
        responsibilities.assign(project.id, "activity", "A-1", "PCT", "X")
    responsibilities.assign(project.id, "activity", "A-1", "PCT", "S")
    with pytest.raises(ValueError, match="conflit"):
        responsibilities.assign(project.id, "activity", "A-1", "PCT", "S")
    session.rollback()


def test_planning_services_validate_edges_and_create_links(
    session: Session, project: ProjectModel, context: ApplicationContext
) -> None:
    planning = WorkPlanService(session)
    with pytest.raises(ValueError, match="Type de nœud"):
        planning.create_node(project.id, "X", "Invalide", node_type="unknown")
    with pytest.raises(ValueError, match="obligatoires"):
        planning.create_node(project.id, " ", " ")

    root = planning.create_node(project.id, "1", "Racine")
    task_node = planning.create_node(project.id, "1.1", "Tâche", node_type="task")
    with pytest.raises(ValueError, match="contenir"):
        planning.create_node(project.id, "1.1.1", "Enfant", parent_id=task_node.id)
    with pytest.raises(ValueError, match="task ou milestone"):
        planning.create_task(root.id)
    with pytest.raises(ValueError, match="0 et 100"):
        planning.create_task(task_node.id, progress_percent=101)
    with pytest.raises(ValueError, match="date de fin"):
        planning.create_task(
            task_node.id,
            planned_start=date(2026, 2, 2),
            planned_end=date(2026, 2, 1),
        )
    task = planning.create_task(
        task_node.id,
        planned_start=date(2026, 2, 1),
        planned_end=date(2026, 2, 2),
    )
    with pytest.raises(ValueError, match="obligatoires"):
        planning.update_node(task_node.id, code="", name="")
    with pytest.raises(ValueError, match="date de fin"):
        planning.update_node(
            task_node.id,
            code="1.1",
            name="Tâche",
            planned_start=date(2026, 2, 2),
            planned_end=date(2026, 2, 1),
        )
    with pytest.raises(ValueError, match="0 et 100"):
        planning.update_node(task_node.id, code="1.1", name="Tâche", progress_percent=-1)
    planning.update_node(task_node.id, code="1.1", name="Tâche mise à jour", progress_percent=50)
    assert task.progress_percent == 50

    with pytest.raises(ValueError, match=r"-1 ou \+1"):
        planning.move_sibling(root.id, 2)
    planning.move_sibling(root.id, -1)
    with pytest.raises(ValueError, match="précédent"):
        planning.indent(root.id)
    with pytest.raises(ValueError, match="niveau racine"):
        planning.outdent(root.id)
    with pytest.raises(ValueError, match="elle-même"):
        planning.add_dependency(task.id, task.id)
    with pytest.raises(ValueError, match="Type de dépendance"):
        planning.add_dependency(task.id, "missing", "XX")

    other = ProjectService(session, context.methodology).create(reference="OTHER", name="Autre")
    other_root = planning.create_node(other.id, "1", "Autre racine")
    with pytest.raises(ValueError, match="autre projet"):
        planning.create_node(project.id, "2", "Mauvais parent", parent_id=other_root.id)
    other_task_node = planning.create_node(other.id, "1.1", "Autre tâche", node_type="task")
    other_task = planning.create_task(other_task_node.id)
    with pytest.raises(ValueError, match="même projet"):
        planning.add_dependency(task.id, other_task.id)

    requirements = RequirementService(session)
    with pytest.raises(ValueError, match="obligatoires"):
        requirements.create(project.id, "", "")
    requirement = requirements.create(project.id, "REQ-COVER", "Exigence")
    deliverables = DeliverableService(session)
    with pytest.raises(ValueError, match="obligatoires"):
        deliverables.create(project.id, "", "")
    deliverable = deliverables.create(project.id, "DEL-COVER", "Livrable")
    assert requirements.link_task(requirement.id, task.id).task_id == task.id
    assert (
        requirements.link_deliverable(requirement.id, deliverable.id).deliverable_id
        == deliverable.id
    )
