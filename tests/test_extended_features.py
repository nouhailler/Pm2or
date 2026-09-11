from __future__ import annotations

import html as html_module
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.artifacts import ARTIFACT_SCHEMAS, ArtifactDataService
from pm2.application.context import ApplicationContext
from pm2.application.crud import EntityCrudService
from pm2.application.documents import DocumentService
from pm2.application.services import (
    AcceptanceService,
    DeliverableService,
    GateService,
    ProjectService,
    TraceabilityService,
    WorkflowService,
    WorkPlanService,
)
from pm2.infrastructure.orm import (
    ALL_MODELS_BY_TABLE,
    DocumentVersionModel,
    PhaseModel,
    StakeholderModel,
)


def test_all_21_artifacts_have_specialized_markdown_and_html(
    session: Session,
    project: object,
    context: ApplicationContext,
) -> None:
    assert set(ARTIFACT_SCHEMAS) == set(context.methodology.artifacts)
    service = DocumentService(session, context.methodology, Path("templates"))
    service.ensure_catalog(project.id)
    markdown_documents: set[str] = set()
    html_documents: set[str] = set()
    for code, schema in ARTIFACT_SCHEMAS.items():
        values = {
            field.code: f"Contenu spécialisé {code} — {field.label}"
            for section in schema.sections
            for field in section.fields
        }
        ArtifactDataService(session).save(project.id, code, values)
        artifact_context = service.context(project.id, code)
        markdown = service.render_markdown(artifact_context)
        html = service.render_html(artifact_context)
        first_field = schema.sections[0].fields[0]
        assert code in markdown
        assert first_field.label in markdown
        assert values[first_field.code] in markdown
        assert code in html
        unescaped_html = html_module.unescape(html)
        assert first_field.label in unescaped_html
        assert values[first_field.code] in unescaped_html
        markdown_documents.add(markdown)
        html_documents.add(html)
    assert len(markdown_documents) == 21
    assert len(html_documents) == 21


def test_generic_crud_is_audited_and_catalog_covers_every_entity(
    session: Session, project: object
) -> None:
    assert len(ALL_MODELS_BY_TABLE) == 47
    service = EntityCrudService(session, project.id)
    stakeholder = service.create(
        "stakeholders",
        {"name": "Utilisateur CRUD", "organisation": "PMO"},
        actor="testeur",
    )
    service.update("stakeholders", stakeholder.id, {"function": "Sponsor"}, actor="testeur")
    service.remove("stakeholders", stakeholder.id, actor="testeur")
    session.commit()

    stored = session.get(StakeholderModel, stakeholder.id)
    assert stored is not None and stored.archived
    assert [
        event.action for event in reversed(service.history("stakeholders", stakeholder.id))
    ] == [
        "CREATE",
        "UPDATE",
        "ARCHIVE",
    ]


def test_wbs_reorder_indent_outdent_and_dependency_removal(
    session: Session, project: object
) -> None:
    service = WorkPlanService(session)
    first = service.create_node(project.id, "1", "Premier lot")
    second = service.create_node(project.id, "2", "Second lot")
    assert (first.sequence, second.sequence) == (0, 1)
    service.indent(second.id)
    assert second.parent_id == first.id
    service.outdent(second.id)
    assert second.parent_id is None
    service.move_sibling(second.id, -1)
    assert second.sequence < first.sequence

    first_task_node = service.create_node(
        project.id, "1.1", "Tâche A", node_type="task", parent_id=first.id
    )
    second_task_node = service.create_node(
        project.id, "1.2", "Tâche B", node_type="task", parent_id=first.id
    )
    first_task = service.create_task(
        first_task_node.id,
        planned_start=date(2026, 1, 1),
        planned_end=date(2026, 1, 2),
        planned_cost=Decimal("100"),
    )
    second_task = service.create_task(
        second_task_node.id,
        planned_start=date(2026, 1, 3),
        planned_end=date(2026, 1, 4),
        planned_cost=Decimal("200"),
    )
    dependency = service.add_dependency(first_task.id, second_task.id, "FS", 1)
    service.remove_dependency(dependency.id)
    session.flush()
    assert session.get(type(dependency), dependency.id) is None


def test_final_acceptance_requires_each_test_to_be_executed(
    session: Session, project: object
) -> None:
    deliverable = DeliverableService(session).create(
        project.id, "DEL-STRICT", "Livrable strict", owner="Alice"
    )
    deliverable.status = "READY_FOR_ACCEPTANCE"
    criterion = AcceptanceService(session).add_criterion(deliverable.id, "AC-STRICT", "Conformité")
    test = AcceptanceService(session).add_test(criterion.id, "AT-STRICT", "Contrôle", "OK")
    with pytest.raises(ValueError, match="exécutés et réussis"):
        AcceptanceService(session).accept(deliverable.id, "PO")
    AcceptanceService(session).record_test(test.id, "PASSED", "OK")
    AcceptanceService(session).accept(deliverable.id, "PO")


def _approve_gate(service: GateService, project_id: str, code: str) -> None:
    review = service.get_or_create(project_id, code)
    for item in service.checklist(review.id):
        service.set_item(item.id, True, "Preuve d'intégration")
    service.decide(review.id, "APPROVED", "PSC")


def test_complete_lifecycle_to_final_report(
    session: Session,
    project: object,
    context: ApplicationContext,
    tmp_path: Path,
) -> None:
    gates = GateService(session, context.methodology)
    _approve_gate(gates, project.id, "RFP")
    assert project.current_phase == "PLANNING"
    _approve_gate(gates, project.id, "RFE")
    assert project.current_phase == "EXECUTION"

    deliverable = DeliverableService(session).create(
        project.id,
        "DEL-FINAL",
        "Produit final",
        owner="Alice",
        planned_date=date(2026, 6, 1),
    )
    for target in ("IN_PROGRESS", "READY_FOR_ACCEPTANCE"):
        WorkflowService(session).transition("deliverable", deliverable.id, target)
    criterion = AcceptanceService(session).add_criterion(
        deliverable.id, "AC-FINAL", "Le produit répond au besoin"
    )
    test = AcceptanceService(session).add_test(criterion.id, "AT-FINAL", "Recette", "Succès")
    AcceptanceService(session).record_test(test.id, "PASSED", "Succès")
    AcceptanceService(session).accept(deliverable.id, "PO")
    WorkflowService(session).transition("deliverable", deliverable.id, "ACCEPTED")
    _approve_gate(gates, project.id, "RFC")
    assert project.current_phase == "CLOSING"

    final_schema = ARTIFACT_SCHEMAS["PROJECT_END_REPORT"]
    ArtifactDataService(session).save(
        project.id,
        final_schema.code,
        {
            field.code: f"Clôture — {field.label}"
            for section in final_schema.sections
            for field in section.fields
        },
    )
    documents = DocumentService(session, context.methodology, Path("templates"))
    documents.ensure_catalog(project.id)
    report = documents.generate(
        project.id,
        "PROJECT_END_REPORT",
        tmp_path / "project-end-report.pdf",
        "pdf",
    )
    ProjectService(session, context.methodology).close(project.id, actor="PM")
    session.commit()

    assert report.path.exists() and report.path.stat().st_size > 500
    assert project.status == "CLOSED"
    phases = session.scalars(select(PhaseModel).where(PhaseModel.project_id == project.id)).all()
    assert all(phase.status == "COMPLETED" for phase in phases)
    assert session.scalar(select(DocumentVersionModel)) is not None


def test_requirement_deliverable_test_trace_reaches_accepted(
    session: Session, project: object
) -> None:
    from pm2.application.services import RequirementService

    requirement = RequirementService(session).create(
        project.id,
        "REQ-END",
        "Besoin vérifiable",
        source="PO",
        priority="HIGH",
        verification_method="Recette",
    )
    deliverable = DeliverableService(session).create(
        project.id, "DEL-END", "Résultat", owner="Alice"
    )
    criterion = AcceptanceService(session).add_criterion(
        deliverable.id, "AC-END", "Le besoin est satisfait"
    )
    test = AcceptanceService(session).add_test(
        criterion.id, "AT-END", "Vérification du besoin", "OK"
    )
    TraceabilityService(session).link(
        project.id,
        "requirement",
        requirement.id,
        "deliverable",
        deliverable.id,
        "produces",
    )
    TraceabilityService(session).link(
        project.id,
        "requirement",
        requirement.id,
        "acceptance_test",
        test.id,
        "verifies",
    )
    for target in ("REVIEW", "APPROVED", "IMPLEMENTED", "VERIFIED", "ACCEPTED"):
        WorkflowService(session).transition("requirement", requirement.id, target)
    assert requirement.status == "ACCEPTED"
