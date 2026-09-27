from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from pm2.application.dashboard_metrics import DashboardService
from pm2.infrastructure.orm import (
    ChangeModel,
    DecisionModel,
    DeliverableModel,
    IssueModel,
    ProjectModel,
    RiskActionModel,
    RiskModel,
    TaskModel,
    WbsNodeModel,
)
from pm2.ui.pages import DashboardPage


def _seed_cockpit(session: Session, project: ProjectModel) -> None:
    project.approved_budget = 1_000
    node = WbsNodeModel(
        project_id=project.id,
        code="WBS-1",
        name="Lot principal",
        node_type="task",
    )
    session.add(node)
    session.flush()
    session.add(
        TaskModel(
            wbs_node_id=node.id,
            status="IN_PROGRESS",
            planned_end=date(2026, 1, 10),
            progress_percent=50,
            planned_cost=800,
            actual_cost=710,
        )
    )
    risk = RiskModel(
        project_id=project.id,
        code="R-007",
        title="Risque critique",
        status="ASSESSED",
        probability=5,
        impact=4,
        score=20,
        strategy="Réduire",
        owner="Alice",
    )
    session.add(risk)
    session.flush()
    session.add_all(
        [
            RiskActionModel(
                risk_id=risk.id,
                title="Mitigation fournisseur",
                due_date=date(2026, 1, 5),
                status="OPEN",
            ),
            IssueModel(
                project_id=project.id,
                code="I-003",
                title="Blocage",
                status="OPEN",
                due_date=date(2026, 1, 8),
            ),
            ChangeModel(
                project_id=project.id,
                code="CR-004",
                title="Évolution",
                status="APPROVAL",
            ),
            DecisionModel(
                project_id=project.id,
                code="D-013",
                title="Arbitrage",
                status="OPEN",
            ),
            DeliverableModel(
                project_id=project.id,
                code="DEL-009",
                name="Dossier final",
                owner="Bob",
                status="READY_FOR_ACCEPTANCE",
            ),
        ]
    )
    session.flush()


def test_dashboard_service_calculates_decision_metrics(
    session: Session, project: ProjectModel
) -> None:
    _seed_cockpit(session, project)
    cockpit = DashboardService(session).cockpit(project.id, today=date(2026, 1, 22))

    assert cockpit.kpis.progress_percent == 50
    assert cockpit.kpis.budget_percent == 71
    assert cockpit.kpis.schedule_variance_days == 12
    assert (
        cockpit.kpis.risks,
        cockpit.kpis.issues,
        cockpit.kpis.changes,
        cockpit.kpis.decisions,
    ) == (1, 1, 1, 1)
    health = {indicator.name: indicator.status for indicator in cockpit.health}
    assert health["Planning"] == "ORANGE"
    assert health["Risques"] == "ORANGE"
    assert health["Budget"] == "RED"
    assert health["Qualité"] == "GRAY"
    labels = {action.label for action in cockpit.actions}
    assert {"CR-004", "R-007", "D-013", "DEL-009", "I-003"} <= labels


def test_dashboard_cockpit_renders_and_opens_priority_action(
    qtbot: Any,
    session: Session,
    project: ProjectModel,
    context: Any,
    monkeypatch: Any,
) -> None:
    _seed_cockpit(session, project)
    monkeypatch.setattr("pm2.application.dashboard_metrics.date", _FixedDate)
    page = DashboardPage(session, project, context.methodology)
    qtbot.addWidget(page)

    assert page.cards["progress"].value.text() == "50 %"
    assert page.cards["budget"].value.text() == "71 %"
    assert page.cards["schedule"].value.text() == "+12 j"
    assert page.cards["decisions"].value.text() == "1"
    assert page.health_layout.count() == 10
    assert page.actions_table.rowCount() >= 5

    row = next(
        index
        for index in range(page.actions_table.rowCount())
        if page.actions_table.item(index, 0).text() == "CR-004"
    )
    button = page.actions_table.cellWidget(row, 2)
    assert button is not None
    destinations: list[str] = []
    corrections: list[tuple[str, str]] = []
    page.navigate_requested.connect(destinations.append)
    page.correction_requested.connect(
        lambda destination, section: corrections.append((destination, section))
    )
    button.click()
    assert destinations == ["Registres"]
    assert corrections == [("Registres", "change")]


class _FixedDate(date):
    @classmethod
    def today(cls) -> _FixedDate:
        return cls(2026, 1, 22)
