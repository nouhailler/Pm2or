from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from pm2.application.gates import GateService
from pm2.application.validation import ValidationService
from pm2.infrastructure.orm import DeliverableModel, ProjectModel
from pm2.ui.validation_page import ValidationPage


def test_compliance_report_scores_phases_and_gate_readiness(
    session: Session, project: ProjectModel, context: Any
) -> None:
    service = ValidationService(session)
    report = service.compliance_report(project.id, context.methodology)

    assert 0 <= report.score <= 100
    assert [phase.code for phase in report.phases] == [
        "LAUNCH",
        "PLANNING",
        "EXECUTION",
        "MONITORING_CONTROL",
        "CLOSING",
    ]
    assert report.phases[0].score is not None
    assert report.phases[1].score is None
    assert report.phases[-1].status == "Non commencée"
    rfe = next(gate for gate in report.gates if gate.code == "RFE")
    assert rfe.status == "BLOQUÉ"
    assert rfe.score == 0
    assert len(rfe.checks) == 8

    gates = GateService(session, context.methodology)
    review = gates.get_or_create(project.id, "RFE")
    for item in gates.checklist(review.id):
        gates.set_item(item.id, True, "Vérifié")
    refreshed = service.compliance_report(project.id, context.methodology)
    ready = next(gate for gate in refreshed.gates if gate.code == "RFE")
    assert ready.status == "PRÊT"
    assert ready.score == 100


def test_compliance_center_aggregates_and_navigates_to_correction(
    qtbot: Any,
    session: Session,
    project: ProjectModel,
    context: Any,
) -> None:
    session.add_all(
        [
            DeliverableModel(
                project_id=project.id,
                code=f"DEL-{index}",
                name=f"Livrable {index}",
                owner="Alice",
                planned_date=date.today(),
            )
            for index in range(3)
        ]
    )
    session.flush()
    page = ValidationPage(session, project, context.methodology)
    qtbot.addWidget(page)

    assert page.score_progress.value() == page.report.score
    assert page.phase_table.rowCount() == 5
    assert page.gate_tabs.count() == 3
    matching_row = next(
        row
        for row in range(page.findings.rowCount())
        if page.findings.item(row, 1).text() == "PM2-DEL-003"
    )
    assert page.findings.item(matching_row, 3).text() == "3"
    action = page.findings.cellWidget(matching_row, 4)
    assert action is not None
    destinations: list[str] = []
    corrections: list[tuple[str, str]] = []
    page.navigate_requested.connect(destinations.append)
    page.correction_requested.connect(
        lambda destination, section: corrections.append((destination, section))
    )
    action.click()
    assert destinations == ["Données métier"]
    assert corrections == [("Données métier", "criteria")]

    page.filter.setCurrentIndex(page.filter.findData("ERROR"))
    assert all(
        page.findings.item(row, 0).text() == "ERROR"
        for row in range(page.findings.rowCount())
    )
