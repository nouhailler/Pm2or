from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from pm2.application.acceptance_services import AcceptanceService
from pm2.application.planning import DeliverableService, RequirementService, WorkPlanService
from pm2.application.traceability import TraceabilityService
from pm2.infrastructure.orm import (
    ChangeImpactModel,
    ChangeModel,
    ProjectModel,
    RiskActionModel,
    RiskModel,
)
from pm2.ui.traceability_page import TraceabilityPage


def _seed_traceability(session: Session, project: ProjectModel) -> dict[str, object]:
    planning = WorkPlanService(session)
    package = planning.create_node(project.id, "1", "Lot principal", node_type="work_package")
    task_node = planning.create_node(
        project.id, "T-034", "Réaliser", node_type="task", parent_id=package.id
    )
    task = planning.create_task(
        task_node.id, planned_start=date(2026, 1, 1), planned_end=date(2026, 1, 5)
    )
    root_task_node = planning.create_node(
        project.id, "T-ORPHAN", "Sans parent", node_type="task"
    )
    root_task = planning.create_task(root_task_node.id)

    requirements = RequirementService(session)
    requirement = requirements.create(project.id, "REQ-012", "Besoin tracé")
    orphan_requirement = requirements.create(project.id, "REQ-ORPHAN", "Besoin isolé")
    deliverables = DeliverableService(session)
    deliverable = deliverables.create(project.id, "D-007", "Livrable testé")
    orphan_deliverable = deliverables.create(project.id, "D-ORPHAN", "Sans test")
    requirements.link_task(requirement.id, task.id)
    requirements.link_deliverable(requirement.id, deliverable.id)
    acceptance = AcceptanceService(session)
    criterion = acceptance.add_criterion(deliverable.id, "AC-003", "Conforme")
    test = acceptance.add_test(criterion.id, "AT-003", "Recette", "OK")

    risk = RiskModel(project_id=project.id, code="R-007", title="Risque traité")
    orphan_risk = RiskModel(project_id=project.id, code="R-ORPHAN", title="Sans réponse")
    session.add_all([risk, orphan_risk])
    session.flush()
    action = RiskActionModel(risk_id=risk.id, title="Réduire l'exposition")
    change = ChangeModel(
        project_id=project.id,
        code="CR-004",
        title="Modification",
        impact_schedule="Deux jours",
        impact_cost=Decimal("1200"),
    )
    session.add_all([action, change])
    session.flush()
    impact = ChangeImpactModel(
        change_id=change.id, impact_type="SCHEDULE", description="Décalage de deux jours"
    )
    session.add(impact)
    session.flush()

    trace = TraceabilityService(session)
    trace.link(project.id, "task", task.id, "deliverable", deliverable.id, "produces")
    trace.link(project.id, "risk_action", action.id, "task", task.id, "implements")
    trace.link(project.id, "change_impact", impact.id, "deliverable", deliverable.id, "impacts")
    return {
        "requirement": requirement,
        "orphan_requirement": orphan_requirement,
        "task": task,
        "root_task": root_task,
        "deliverable": deliverable,
        "orphan_deliverable": orphan_deliverable,
        "test": test,
        "risk": risk,
        "orphan_risk": orphan_risk,
        "action": action,
        "change": change,
        "impact": impact,
    }


def test_traceability_graph_combines_native_and_explicit_links(
    session: Session, project: ProjectModel
) -> None:
    seeded = _seed_traceability(session, project)

    graph = TraceabilityService(session).graph(project.id)
    nodes = {(node.entity_type, node.label) for node in graph.nodes}
    relations = {(edge.source, edge.target, edge.relation) for edge in graph.edges}

    assert ("requirement", "REQ-012") in nodes
    assert ("acceptance_test", "AT-003") in nodes
    assert ("risk_action", "Mitigation") in nodes
    assert ("change_impact", "Schedule") in nodes
    assert ("change_impact", "Cost") in nodes
    assert (
        f"requirement:{seeded['requirement'].id}",
        f"task:{seeded['task'].id}",
        "implemented by",
    ) in relations
    assert (
        f"task:{seeded['task'].id}",
        f"deliverable:{seeded['deliverable'].id}",
        "produces",
    ) in relations
    assert any(edge.target.endswith(str(seeded["test"].id)) for edge in graph.edges)


def test_orphan_detection_finds_and_clears_missing_chains(
    session: Session, project: ProjectModel
) -> None:
    seeded = _seed_traceability(session, project)
    service = TraceabilityService(session)

    findings = {finding.code: finding for finding in service.orphan_findings(project.id)}

    assert findings["REQ_WITHOUT_DELIVERABLE"].entity_labels == ("REQ-ORPHAN",)
    assert findings["RISK_WITHOUT_RESPONSE"].entity_labels == ("R-ORPHAN",)
    assert findings["DELIVERABLE_WITHOUT_TEST"].entity_labels == ("D-ORPHAN",)
    assert findings["TASK_WITHOUT_WBS_PARENT"].entity_labels == ("T-ORPHAN",)

    service.link(
        project.id,
        "requirement",
        seeded["orphan_requirement"].id,
        "deliverable",
        seeded["deliverable"].id,
        "produces",
    )
    service.link(
        project.id,
        "risk",
        seeded["orphan_risk"].id,
        "task",
        seeded["task"].id,
        "mitigates",
    )
    service.link(
        project.id,
        "deliverable",
        seeded["orphan_deliverable"].id,
        "acceptance_test",
        seeded["test"].id,
        "verifies",
    )
    seeded["root_task"].wbs_node.parent_id = seeded["task"].wbs_node.parent_id

    assert all(finding.count == 0 for finding in service.orphan_findings(project.id))


def test_traceability_page_renders_graph_and_actionable_orphans(
    qtbot: Any, session: Session, project: ProjectModel
) -> None:
    _seed_traceability(session, project)
    page = TraceabilityPage(session, project)
    qtbot.addWidget(page)
    destinations: list[str] = []
    page.navigate_requested.connect(destinations.append)

    assert "objets" in page.graph_summary.text()
    assert page.scene.items()
    assert page.orphans.rowCount() == 4
    assert "⚠ 4" in page.orphan_summary.text()

    page.orphans.setCurrentCell(0, 0)
    page._navigate_orphan()
    assert destinations == ["Données métier"]

    page.chain_filter.setCurrentIndex(1)
    assert "relations" in page.graph_summary.text()
