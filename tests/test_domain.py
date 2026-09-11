from datetime import date
from decimal import Decimal

import pytest

from pm2.domain.entities import Project, Task


def test_project_invariants() -> None:
    with pytest.raises(ValueError, match="obligatoires"):
        Project(reference="", name="")
    with pytest.raises(ValueError, match="budget"):
        Project(reference="P", name="P", approved_budget=Decimal("-1"))


def test_task_invariants() -> None:
    with pytest.raises(ValueError, match="0 et 100"):
        Task(wbs_node_id="n", progress_percent=101)
    with pytest.raises(ValueError, match="fin planifiée"):
        Task(wbs_node_id="n", planned_start=date(2026, 2, 2), planned_end=date(2026, 2, 1))
