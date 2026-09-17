from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pm2.application.traceability import TraceabilityService as TraceabilityService
from pm2.infrastructure.orm import (
    ChangeModel,
    DeliverableModel,
    DocumentModel,
    IssueModel,
    RequirementModel,
    RiskModel,
    TaskModel,
    WbsNodeModel,
)


def project_counts(session: Session, project_id: str) -> dict[str, int | float]:
    def count(model: Any, *conditions: Any) -> int:
        return int(session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)

    tasks = session.scalars(
        select(TaskModel).join(WbsNodeModel).where(WbsNodeModel.project_id == project_id)
    ).all()
    progress = sum(task.progress_percent for task in tasks) / len(tasks) if tasks else 0.0
    return {
        "risks": count(RiskModel, RiskModel.project_id == project_id, RiskModel.status != "CLOSED"),
        "issues": count(
            IssueModel, IssueModel.project_id == project_id, IssueModel.status != "CLOSED"
        ),
        "changes": count(
            ChangeModel,
            ChangeModel.project_id == project_id,
            ~ChangeModel.status.in_(["CLOSED", "REJECTED"]),
        ),
        "deliverables": count(DeliverableModel, DeliverableModel.project_id == project_id),
        "requirements": count(RequirementModel, RequirementModel.project_id == project_id),
        "documents": count(DocumentModel, DocumentModel.project_id == project_id),
        "progress": round(progress, 1),
    }
