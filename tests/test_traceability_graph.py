from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsPathItem, QGraphicsTextItem
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


def test_traceability_graph_labels_stay_inside_their_nodes(
    qtbot: Any, session: Session, project: ProjectModel
) -> None:
    _seed_traceability(session, project)
    page = TraceabilityPage(session, project)
    qtbot.addWidget(page)
    page.resize(1400, 900)
    page.show()
    destinations: list[str] = []
    page.navigate_requested.connect(destinations.append)

    nodes = [item for item in page.scene.items() if item.data(1)]
    assert len(nodes) > 1
    assert len({(node.pos().x(), node.pos().y()) for node in nodes}) == len(nodes)
    for node in nodes:
        labels = node.childItems()
        assert len(labels) == 1
        assert labels[0].scenePos() == node.pos() + labels[0].pos()
        assert node.sceneBoundingRect().contains(labels[0].sceneBoundingRect().topLeft())

    relation_labels = [
        item
        for item in page.scene.items()
        if isinstance(item, QGraphicsTextItem)
        and item.parentItem() is None
        and item.toPlainText() in {"a pour critère", "vérifié par"}
    ]
    assert relation_labels
    for label in relation_labels:
        assert not any(
            node.sceneBoundingRect().intersects(label.sceneBoundingRect()) for node in nodes
        )

    target = next(node for node in nodes if node.data(0) == "requirement")
    page.graph_view.centerOn(target)
    click = page.graph_view.mapFromScene(target.sceneBoundingRect().center())
    qtbot.mouseClick(page.graph_view.viewport(), Qt.MouseButton.LeftButton, pos=click)

    assert page.scene.selectedItems() == [target]
    page._navigate_graph()
    assert destinations == [target.data(2)]


def test_traceability_graph_links_do_not_cross_other_nodes(
    qtbot: Any, session: Session, project: ProjectModel
) -> None:
    _seed_traceability(session, project)
    page = TraceabilityPage(session, project)
    qtbot.addWidget(page)

    items = page.scene.items()
    nodes = [item.sceneBoundingRect().adjusted(3, 3, -3, -3) for item in items if item.data(1)]
    points = []
    for item in items:
        if isinstance(item, QGraphicsPathItem):
            path = item.path()
            points += [path.pointAtPercent(step / 400) for step in range(401)]
        elif isinstance(item, QGraphicsLineItem):
            line = item.line()
            points += [line.pointAt(step / 400) for step in range(401)]

    assert any(isinstance(item, QGraphicsPathItem) for item in items)
    assert not [point for point in points if any(node.contains(point) for node in nodes)]


def test_traceability_graph_shortens_titles_and_translates_labels(
    qtbot: Any, session: Session, project: ProjectModel
) -> None:
    _seed_traceability(session, project)
    full_title = "Réserver une activité avec confirmation par courriel"
    RequirementService(session).create(project.id, "REQ-LONG", full_title)
    page = TraceabilityPage(session, project)
    qtbot.addWidget(page)

    node = next(
        item
        for item in page.scene.items()
        if item.data(1) and "REQ-LONG" in item.childItems()[0].toPlainText()
    )
    label = node.childItems()[0].toPlainText()
    assert label.endswith("avec…")
    assert full_title in node.toolTip()

    texts = "\n".join(
        item.toPlainText() for item in page.scene.items() if isinstance(item, QGraphicsTextItem)
    )
    assert "mise en œuvre par" in texts
    assert "Planning — " in texts
    for english in ("implemented by", "has criterion", "Schedule"):
        assert english not in texts

    page.filter.setCurrentIndex(page.filter.findData("produces"))
    assert page.table.rowCount() == 1
    assert page.table.item(0, 1).text() == "produit"


def test_traceability_chain_filter_hides_objects_outside_the_chain(
    qtbot: Any, session: Session, project: ProjectModel
) -> None:
    seeded = _seed_traceability(session, project)
    page = TraceabilityPage(session, project)
    qtbot.addWidget(page)

    page.chain_filter.setCurrentIndex(page.chain_filter.findData("risks"))
    shown = {item.data(1) for item in page.scene.items() if item.data(1)}
    assert {seeded["risk"].id, seeded["orphan_risk"].id, seeded["task"].id} <= shown
    assert seeded["deliverable"].id in shown
    assert seeded["root_task"].id not in shown
    assert seeded["orphan_deliverable"].id not in shown


def test_traceability_chain_filter_explains_an_empty_chain(
    qtbot: Any, session: Session, project: ProjectModel
) -> None:
    session.add(RiskModel(project_id=project.id, code="R-001", title="Sans réponse"))
    RequirementService(session).create(project.id, "REQ-001", "Hors chaîne")
    session.flush()
    page = TraceabilityPage(session, project)
    qtbot.addWidget(page)

    page.chain_filter.setCurrentIndex(page.chain_filter.findData("risks"))

    assert page.graph_summary.text().startswith("1 objets · 0 relations — aucune relation")
