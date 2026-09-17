from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pm2.application.audit import AuditService
from pm2.application.traceability import TraceabilityService as TraceabilityService
from pm2.infrastructure.orm import (
    AcceptanceCriterionModel,
    AcceptanceModel,
    AcceptancePlanModel,
    AcceptanceTestModel,
    DeliverableModel,
    row_to_dict,
    utcnow,
)
from pm2.infrastructure.repositories import Repository


class AcceptanceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def accept(
        self, deliverable_id: str, accepted_by: str, comments: str = "", *, final: bool = True
    ) -> AcceptanceModel:
        criteria = self.session.scalars(
            select(AcceptanceCriterionModel).where(
                AcceptanceCriterionModel.deliverable_id == deliverable_id,
                AcceptanceCriterionModel.applicable.is_(True),
            )
        ).all()
        if not criteria:
            raise ValueError("L'acceptation finale est impossible sans critère applicable.")
        criterion_ids = [criterion.id for criterion in criteria]
        tests_by_criterion = {
            criterion_id: list(
                self.session.scalars(
                    select(AcceptanceTestModel).where(
                        AcceptanceTestModel.criterion_id == criterion_id
                    )
                ).all()
            )
            for criterion_id in criterion_ids
        }
        if final and any(not tests for tests in tests_by_criterion.values()):
            raise ValueError(
                "Chaque critère applicable doit disposer d'au moins un test d'acceptation."
            )
        failed = self.session.scalar(
            select(func.count())
            .select_from(AcceptanceTestModel)
            .where(
                AcceptanceTestModel.criterion_id.in_(criterion_ids),
                or_(
                    AcceptanceTestModel.outcome.is_(None),
                    AcceptanceTestModel.outcome != "PASSED",
                ),
            )
        )
        if final and failed:
            raise ValueError("Tous les tests d'acceptation doivent être exécutés et réussis.")
        acceptance = AcceptanceModel(
            deliverable_id=deliverable_id,
            status="ACCEPTED",
            accepted_by=accepted_by,
            accepted_at=utcnow(),
            comments=comments,
            final=final,
        )
        self.session.add(acceptance)
        self.session.flush()
        deliverable = Repository(self.session, DeliverableModel).require(deliverable_id)
        deliverable.acceptance_status = "ACCEPTED"
        AuditService(self.session).record(
            deliverable.project_id,
            "acceptance",
            acceptance.id,
            "ACCEPT",
            new=row_to_dict(acceptance),
            actor=accepted_by,
        )
        self.session.flush()
        return acceptance

    def create_plan(self, project_id: str, code: str, title: str) -> AcceptancePlanModel:
        plan = AcceptancePlanModel(project_id=project_id, code=code, title=title)
        self.session.add(plan)
        self.session.flush()
        AuditService(self.session).record(
            project_id, "acceptance_plan", plan.id, "CREATE", new=row_to_dict(plan)
        )
        return plan

    def add_criterion(
        self,
        deliverable_id: str,
        code: str,
        description: str,
        *,
        plan_id: str | None = None,
        mandatory: bool = True,
    ) -> AcceptanceCriterionModel:
        criterion = AcceptanceCriterionModel(
            acceptance_plan_id=plan_id,
            deliverable_id=deliverable_id,
            code=code,
            description=description,
            mandatory=mandatory,
        )
        self.session.add(criterion)
        self.session.flush()
        deliverable = Repository(self.session, DeliverableModel).require(deliverable_id)
        AuditService(self.session).record(
            deliverable.project_id,
            "acceptance_criterion",
            criterion.id,
            "CREATE",
            new=row_to_dict(criterion),
        )
        return criterion

    def add_test(
        self, criterion_id: str, code: str, description: str, expected_result: str
    ) -> AcceptanceTestModel:
        if not expected_result.strip():
            raise ValueError("Le résultat attendu du test est obligatoire.")
        test = AcceptanceTestModel(
            criterion_id=criterion_id,
            code=code,
            description=description,
            expected_result=expected_result,
        )
        self.session.add(test)
        self.session.flush()
        criterion = Repository(self.session, AcceptanceCriterionModel).require(criterion_id)
        deliverable = Repository(self.session, DeliverableModel).require(criterion.deliverable_id)
        AuditService(self.session).record(
            deliverable.project_id,
            "acceptance_test",
            test.id,
            "CREATE",
            new=row_to_dict(test),
        )
        return test

    def record_test(self, test_id: str, outcome: str, actual_result: str) -> AcceptanceTestModel:
        if outcome not in {"PASSED", "FAILED", "BLOCKED"}:
            raise ValueError("Résultat de test invalide.")
        test = Repository(self.session, AcceptanceTestModel).require(test_id)
        old = row_to_dict(test)
        test.outcome = outcome
        test.actual_result = actual_result
        test.executed_at = utcnow()
        criterion = Repository(self.session, AcceptanceCriterionModel).require(test.criterion_id)
        deliverable = Repository(self.session, DeliverableModel).require(criterion.deliverable_id)
        AuditService(self.session).record(
            deliverable.project_id,
            "acceptance_test",
            test.id,
            "EXECUTE",
            old=old,
            new=row_to_dict(test),
        )
        self.session.flush()
        return test


