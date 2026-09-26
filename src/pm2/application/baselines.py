from __future__ import annotations

import hashlib
import json
from collections.abc import MutableSequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.audit import AuditService
from pm2.infrastructure.orm import (
    BaselineModel,
    DeliverableModel,
    DocumentModel,
    DocumentVersionModel,
    ProjectModel,
    RequirementModel,
    RiskModel,
    SettingModel,
    TaskModel,
    WbsNodeModel,
)


class BaselineIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BaselineDifference:
    path: str
    change: str
    baseline: Any
    current: Any


@dataclass(frozen=True, slots=True)
class BaselineComparison:
    baseline: BaselineModel
    differences: tuple[BaselineDifference, ...]

    @property
    def added(self) -> int:
        return sum(item.change == "ADDED" for item in self.differences)

    @property
    def removed(self) -> int:
        return sum(item.change == "REMOVED" for item in self.differences)

    @property
    def changed(self) -> int:
        return sum(item.change == "CHANGED" for item in self.differences)


def baseline_sha256(snapshot: str) -> str:
    return hashlib.sha256(snapshot.encode("utf-8")).hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _row(value: Any, *, exclude: set[str] | None = None) -> dict[str, Any]:
    ignored = {"created_at", "updated_at"} | (exclude or set())
    return {
        column.name: _json_value(getattr(value, column.name))
        for column in value.__table__.columns
        if column.name not in ignored
    }


class BaselineService:
    """Create immutable project snapshots and compare them with live state."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def capture(self, project_id: str) -> str:
        project = self.session.get(ProjectModel, project_id)
        if project is None:
            raise LookupError(f"Projet introuvable : {project_id}")

        wbs_nodes = self.session.scalars(
            select(WbsNodeModel)
            .where(WbsNodeModel.project_id == project_id)
            .order_by(WbsNodeModel.code)
        ).all()
        tasks = self.session.scalars(
            select(TaskModel)
            .join(WbsNodeModel)
            .where(WbsNodeModel.project_id == project_id)
            .order_by(WbsNodeModel.code)
        ).all()
        task_by_node = {task.wbs_node_id: _row(task) for task in tasks}

        def keyed(model: Any, key: str = "code") -> dict[str, dict[str, Any]]:
            values = self.session.scalars(
                select(model).where(model.project_id == project_id).order_by(getattr(model, key))
            ).all()
            return {str(getattr(value, key)): _row(value) for value in values}

        documents = self.session.scalars(
            select(DocumentModel)
            .where(DocumentModel.project_id == project_id)
            .order_by(DocumentModel.code)
        ).all()
        document_state: dict[str, dict[str, Any]] = {}
        for document in documents:
            versions = self.session.scalars(
                select(DocumentVersionModel)
                .where(DocumentVersionModel.document_id == document.id)
                .order_by(DocumentVersionModel.version)
            ).all()
            item = _row(document)
            item["versions"] = {
                version.version: _row(version, exclude={"file_path"}) for version in versions
            }
            document_state[document.artifact_code or document.code] = item

        artifact_data: dict[str, Any] = {}
        settings = self.session.scalars(
            select(SettingModel)
            .where(
                SettingModel.project_id == project_id,
                SettingModel.key.startswith("artifact_data:"),
            )
            .order_by(SettingModel.key)
        ).all()
        for setting in settings:
            code = setting.key.removeprefix("artifact_data:")
            try:
                artifact_data[code] = json.loads(setting.value_json)
            except json.JSONDecodeError:
                artifact_data[code] = setting.value_json

        work_plan = {
            node.code: {
                **_row(node),
                "task": task_by_node.get(node.id),
            }
            for node in wbs_nodes
        }
        payload = {
            "format": "pm2-desktop-baseline",
            "format_version": "1.0",
            "project": _row(project, exclude={"methodology_snapshot"}),
            "budget": {
                "approved": _json_value(project.approved_budget),
                "currency": project.currency,
                "planned_cost": str(sum((task.planned_cost for task in tasks), Decimal("0"))),
                "actual_cost": str(sum((task.actual_cost for task in tasks), Decimal("0"))),
            },
            "work_plan": work_plan,
            "milestones": {
                node.code: work_plan[node.code]
                for node in wbs_nodes
                if node.node_type == "milestone"
            },
            "requirements": keyed(RequirementModel),
            "deliverables": keyed(DeliverableModel),
            "risks": keyed(RiskModel),
            "documents": document_state,
            "artifact_data": artifact_data,
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def create(
        self,
        project_id: str,
        *,
        name: str,
        baseline_type: str = "PROJECT",
        created_by: str,
    ) -> BaselineModel:
        name = name.strip()
        baseline_type = baseline_type.strip().upper()
        created_by = created_by.strip()
        if not name or not baseline_type or not created_by:
            raise ValueError("Le nom, le type et le créateur de la baseline sont obligatoires.")
        existing_codes = self.session.scalars(
            select(BaselineModel.code).where(BaselineModel.project_id == project_id)
        ).all()
        numbers = [
            int(code[2:])
            for code in existing_codes
            if code.startswith("B-") and code[2:].isdigit()
        ]
        code = f"B-{max(numbers, default=0) + 1:03d}"
        snapshot = self.capture(project_id)
        baseline = BaselineModel(
            project_id=project_id,
            code=code,
            name=name,
            type=baseline_type,
            created_by=created_by,
            hash=baseline_sha256(snapshot),
            snapshot=snapshot,
        )
        self.session.add(baseline)
        self.session.flush()
        AuditService(self.session).record(
            project_id,
            "baseline",
            baseline.id,
            "CREATE",
            new={
                "code": baseline.code,
                "name": baseline.name,
                "type": baseline.type,
                "hash": baseline.hash,
            },
            actor=created_by,
        )
        return baseline

    def approve(self, baseline_id: str, *, approved_by: str) -> BaselineModel:
        baseline = self.require(baseline_id)
        approved_by = approved_by.strip()
        if not approved_by:
            raise ValueError("L’approbateur est obligatoire.")
        if baseline.approved_at is not None:
            raise ValueError("Cette baseline est déjà approuvée et ne peut plus être modifiée.")
        baseline.approved_at = datetime.now(UTC)
        baseline.approved_by = approved_by
        self.session.flush()
        AuditService(self.session).record(
            baseline.project_id,
            "baseline",
            baseline.id,
            "APPROVE",
            new={"approved_at": baseline.approved_at, "approved_by": approved_by},
            actor=approved_by,
        )
        return baseline

    def list(self, project_id: str) -> list[BaselineModel]:
        baselines = list(
            self.session.scalars(
                select(BaselineModel)
                .where(BaselineModel.project_id == project_id)
                .order_by(BaselineModel.created_at.desc())
            ).all()
        )
        for baseline in baselines:
            self._verify(baseline)
        return baselines

    def require(self, baseline_id: str) -> BaselineModel:
        baseline = self.session.get(BaselineModel, baseline_id)
        if baseline is None:
            raise LookupError(f"Baseline introuvable : {baseline_id}")
        self._verify(baseline)
        return baseline

    def compare(self, baseline_id: str) -> BaselineComparison:
        baseline = self.require(baseline_id)
        reference = json.loads(baseline.snapshot)
        current = json.loads(self.capture(baseline.project_id))
        differences: list[BaselineDifference] = []
        self._compare_values(reference, current, "", differences)
        return BaselineComparison(baseline, tuple(differences))

    @staticmethod
    def _verify(baseline: BaselineModel) -> None:
        if baseline_sha256(baseline.snapshot) != baseline.hash:
            raise BaselineIntegrityError(
                f"La baseline {baseline.code} est corrompue : empreinte SHA-256 invalide."
            )
        try:
            payload = json.loads(baseline.snapshot)
        except json.JSONDecodeError as exc:
            raise BaselineIntegrityError(
                f"La baseline {baseline.code} contient un snapshot illisible."
            ) from exc
        if not isinstance(payload, dict) or payload.get("format") != "pm2-desktop-baseline":
            raise BaselineIntegrityError(f"La baseline {baseline.code} a un format invalide.")

    @classmethod
    def _compare_values(
        cls,
        reference: Any,
        current: Any,
        path: str,
        output: MutableSequence[BaselineDifference],
    ) -> None:
        if isinstance(reference, dict) and isinstance(current, dict):
            for key in sorted(reference.keys() | current.keys()):
                child = f"{path}/{key}" if path else str(key)
                if key not in reference:
                    output.append(BaselineDifference(child, "ADDED", None, current[key]))
                elif key not in current:
                    output.append(BaselineDifference(child, "REMOVED", reference[key], None))
                else:
                    cls._compare_values(reference[key], current[key], child, output)
            return
        if reference != current:
            output.append(BaselineDifference(path, "CHANGED", reference, current))
