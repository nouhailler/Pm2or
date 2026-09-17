from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from pm2.application.traceability import TraceabilityService as TraceabilityService
from pm2.infrastructure.orm import (
    ImplementationActivityModel,
    MeetingActionModel,
    MeetingModel,
    MeetingParticipantModel,
    QualityActionModel,
    QualityControlModel,
    QualityFindingModel,
    TransitionActivityModel,
)


class QualityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_control(
        self,
        project_id: str,
        code: str,
        title: str,
        *,
        owner: str | None = None,
        control_date: date | None = None,
    ) -> QualityControlModel:
        control = QualityControlModel(
            project_id=project_id,
            code=code,
            title=title,
            owner=owner,
            control_date=control_date,
            status="PLANNED",
        )
        self.session.add(control)
        self.session.flush()
        return control

    def add_finding(
        self, control_id: str, title: str, *, description: str = "", severity: str = "MINOR"
    ) -> QualityFindingModel:
        finding = QualityFindingModel(
            quality_control_id=control_id,
            title=title,
            description=description,
            severity=severity,
        )
        self.session.add(finding)
        self.session.flush()
        return finding

    def add_action(
        self,
        finding_id: str,
        title: str,
        *,
        owner: str | None = None,
        evidence_required: bool = False,
    ) -> QualityActionModel:
        action = QualityActionModel(
            finding_id=finding_id,
            title=title,
            owner=owner,
            evidence_required=evidence_required,
        )
        self.session.add(action)
        self.session.flush()
        return action


class TransitionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        project_id: str,
        code: str,
        title: str,
        *,
        task_id: str | None = None,
        owner: str | None = None,
        implementation: bool = False,
    ) -> TransitionActivityModel | ImplementationActivityModel:
        model = ImplementationActivityModel if implementation else TransitionActivityModel
        activity = model(
            project_id=project_id,
            code=code,
            title=title,
            task_id=task_id,
            owner=owner,
            status="PLANNED",
        )
        self.session.add(activity)
        self.session.flush()
        return activity


class MeetingService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, project_id: str, code: str, title: str) -> MeetingModel:
        meeting = MeetingModel(project_id=project_id, code=code, title=title, status="PLANNED")
        self.session.add(meeting)
        self.session.flush()
        return meeting

    def add_participant(
        self,
        meeting_id: str,
        name: str,
        *,
        person_id: str | None = None,
        role: str | None = None,
    ) -> MeetingParticipantModel:
        participant = MeetingParticipantModel(
            meeting_id=meeting_id, person_id=person_id, name=name, role=role
        )
        self.session.add(participant)
        self.session.flush()
        return participant

    def add_action(
        self, meeting_id: str, title: str, *, owner: str | None = None
    ) -> MeetingActionModel:
        action = MeetingActionModel(meeting_id=meeting_id, title=title, owner=owner)
        self.session.add(action)
        self.session.flush()
        return action


