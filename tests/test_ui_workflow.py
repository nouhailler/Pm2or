from pathlib import Path

from PySide6.QtCore import Qt

from pm2.application.services import GateService, ProjectService
from pm2.config import AppPaths
from pm2.ui.main_window import MainWindow
from pm2.ui.navigation import NAVIGATION_GROUPS
from pm2.ui.pages import DashboardPage
from pm2.ui.wizards import PhaseAssistantPage


def make_window(qtbot, context, tmp_path: Path) -> MainWindow:
    paths = AppPaths(
        tmp_path, context.database.path, tmp_path / "app.log", tmp_path / "recent.json"
    )
    window = MainWindow(context, paths)
    qtbot.addWidget(window)
    return window


def test_workflow_opens_assistants_without_changing_phase(qtbot, context, project, tmp_path):
    window = make_window(qtbot, context, tmp_path)
    dashboard = window.stack.currentWidget()
    assert isinstance(dashboard, DashboardPage)
    workflow = dashboard.workflow
    assert "Vous êtes ici" in workflow.phase_buttons["LAUNCH"].text()
    assert not workflow.phase_buttons["PLANNING"].property("current")
    assert workflow.methodology == window.project_methodology
    window.show()
    window.resize(1050, 740)
    qtbot.waitUntil(lambda: workflow.width() < 700)
    assert dashboard.dashboard_scroll.horizontalScrollBar().maximum() == 0
    workflow.phase_buttons["PLANNING"].click()
    assert isinstance(window.stack.currentWidget(), PhaseAssistantPage)
    assert window.stack.currentWidget().phase == "PLANNING"
    window.session.refresh(window.project)
    assert window.project.current_phase == "LAUNCH"
    workflow.continue_button.click()
    assert window.stack.currentWidget().phase == "LAUNCH"
    workflow.gate_buttons["RFP"].click()
    assert window.navigation.currentItem() is window.navigation.page_items["Gates"]


def test_workflow_follows_gate_decisions_and_final_closure(qtbot, context, project, tmp_path):
    window = make_window(qtbot, context, tmp_path)
    dashboard = window.stack.currentWidget()
    workflow = dashboard.workflow
    gates = GateService(window.session, window.project_methodology)
    for code, phase in (("RFP", "PLANNING"), ("RFE", "EXECUTION"), ("RFC", "CLOSING")):
        review = gates.get_or_create(window.project.id, code)
        for item in gates.checklist(review.id):
            gates.set_item(item.id, True, "Preuve de test")
        gates.decide(review.id, "APPROVED", "Comité de pilotage fictif")
        window.session.commit()
        window.refresh_all()
        assert workflow.phase_buttons[phase].property("current")
        assert (
            sum(bool(button.property("current")) for button in workflow.phase_buttons.values()) == 1
        )
        assert "Approuvé" in workflow.gate_buttons[code].text()
    ProjectService(window.session, window.project_methodology).close(window.project.id)
    window.session.commit()
    window.refresh_all()
    assert "Projet clos" in workflow.position.text()
    assert "Vous êtes ici" not in workflow.phase_buttons["CLOSING"].text()
    assert "Terminée" in workflow.phase_buttons["CLOSING"].text()
    assert workflow.next_gate.text() == ""


def test_execution_has_rfc_review_and_closure_has_no_outgoing_gate(
    qtbot, context, project, tmp_path
):
    window = make_window(qtbot, context, tmp_path)
    assistants = {page.phase: page for page in window.pages if isinstance(page, PhaseAssistantPage)}
    assert assistants["EXECUTION"].gate.gate_code == "RFC"
    assert assistants["CLOSING"].gate is None


def test_navigation_drawers_keep_active_page_and_reveal_shortcut(qtbot, context, project, tmp_path):
    window = make_window(qtbot, context, tmp_path)
    window.show()
    navigation = window.navigation
    assert navigation.topLevelItemCount() == 5
    assert len(navigation.page_items) == len(window.pages)
    group = navigation.groups["Vue d’ensemble"]
    active = navigation.currentItem()
    rect = navigation.visualItemRect(group)
    qtbot.mouseClick(navigation.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    assert not group.isExpanded()
    assert navigation.currentItem() is active
    assert window.stack.currentWidget() is window.pages[0]
    window.navigate_to("Documents")
    assert navigation.groups["Données et documents"].isExpanded()
    assert navigation.currentItem() is navigation.page_items["Documents"]
    assert window.stack.currentWidget() is window.pages[window.page_indexes["Documents"]]


def test_all_grouped_navigation_destinations_open_their_page(qtbot, context, project, tmp_path):
    window = make_window(qtbot, context, tmp_path)
    for _title, names in NAVIGATION_GROUPS:
        for name in names:
            window.navigate_to(name)
            assert window.stack.currentWidget() is window.pages[window.page_indexes[name]]
            assert window.navigation.currentItem() is window.navigation.page_items[name]
            assert window.navigation.currentItem().parent().isExpanded()
