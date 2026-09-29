from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from pm2.application.planning import WorkPlanService
from pm2.infrastructure.orm import ProjectModel, TaskModel
from pm2.ui.work_plan_page import WorkPlanPage


def _task(
    service: WorkPlanService,
    project_id: str,
    code: str,
    duration_days: int,
) -> TaskModel:
    node = service.create_node(project_id, code, f"Tâche {code}", node_type="task")
    start = date(2026, 1, 1)
    return service.create_task(
        node.id,
        planned_start=start,
        planned_end=start + timedelta(days=duration_days - 1),
    )


@pytest.mark.parametrize(
    ("dependency_type", "lag_days", "expected_successor_offset"),
    [
        ("FS", 3, 7),
        ("SS", 3, 3),
        ("FF", 3, 5),
        ("SF", 3, 1),
        ("FS", -2, 2),
    ],
)
def test_cpm_supports_dependency_types_lag_and_lead(
    session: Session,
    project: ProjectModel,
    dependency_type: str,
    lag_days: int,
    expected_successor_offset: int,
) -> None:
    service = WorkPlanService(session)
    predecessor = _task(service, project.id, "P", 4)
    successor = _task(service, project.id, "S", 2)
    service.add_dependency(
        predecessor.id,
        successor.id,
        dependency_type,
        lag_days,
    )

    result = service.calculate_schedule(project.id, project_start=date(2026, 1, 1))

    successor_schedule = next(item for item in result.tasks if item.code == "S")
    assert successor_schedule.early_start == date(2026, 1, 1) + timedelta(
        days=expected_successor_offset
    )
    assert all(item.late_finish <= result.project_finish for item in result.tasks)


def test_cpm_calculates_float_and_critical_path(
    session: Session, project: ProjectModel
) -> None:
    service = WorkPlanService(session)
    task_a = _task(service, project.id, "T1", 3)
    task_b = _task(service, project.id, "T4", 2)
    task_c = _task(service, project.id, "T7", 1)
    task_d = _task(service, project.id, "D03", 1)
    service.add_dependency(task_a.id, task_b.id, "FS")
    service.add_dependency(task_b.id, task_d.id, "FS")
    service.add_dependency(task_a.id, task_c.id, "SS")
    service.add_dependency(task_c.id, task_d.id, "FS")

    result = service.calculate_schedule(project.id, project_start=date(2026, 1, 1))
    schedules = {item.code: item for item in result.tasks}

    assert result.project_finish == date(2026, 1, 6)
    assert result.duration_days == 6
    assert result.critical_paths == (("T1", "T4", "D03"),)
    assert schedules["T1"].early_start == date(2026, 1, 1)
    assert schedules["T4"].early_start == date(2026, 1, 4)
    assert schedules["D03"].early_start == date(2026, 1, 6)
    assert schedules["T7"].total_float_days == 4
    assert not schedules["T7"].critical


def test_empty_schedule_uses_project_start(session: Session, project: ProjectModel) -> None:
    project.start_date = date(2026, 2, 2)

    result = WorkPlanService(session).calculate_schedule(project.id)

    assert result.project_start == date(2026, 2, 2)
    assert result.project_finish == date(2026, 2, 2)
    assert result.tasks == ()


def test_work_plan_page_displays_critical_path(
    qtbot: Any, session: Session, project: ProjectModel
) -> None:
    service = WorkPlanService(session)
    first = _task(service, project.id, "T1", 2)
    second = _task(service, project.id, "T2", 1)
    service.add_dependency(first.id, second.id, "FS", 1)
    page = WorkPlanPage(session, project)
    qtbot.addWidget(page)

    assert "T1 → T2" in page.critical_path.text()
    assert page.schedule.rowCount() == 2
    assert page.schedule.item(0, 7).text() == "OUI"
    assert WorkPlanPage._lag_label(3) == "+3 j (lag)"
    assert WorkPlanPage._lag_label(-2) == "-2 j (lead)"
