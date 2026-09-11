from __future__ import annotations

from dataclasses import dataclass

from pm2.domain.enums import WorkflowError

WORKFLOWS: dict[str, dict[str, set[str]]] = {
    "project": {
        "DRAFT": {"LAUNCH"},
        "LAUNCH": {"PLANNING"},
        "PLANNING": {"EXECUTION"},
        "EXECUTION": {"CLOSING"},
        "CLOSING": {"CLOSED"},
        "CLOSED": set(),
    },
    "risk": {
        "OPEN": {"ASSESSED"},
        "ASSESSED": {"RESPONSE_PLANNED"},
        "RESPONSE_PLANNED": {"MONITORED"},
        "MONITORED": {"CLOSED"},
        "CLOSED": set(),
    },
    "issue": {
        "OPEN": {"ANALYSIS"},
        "ANALYSIS": {"ACTION_PLANNED"},
        "ACTION_PLANNED": {"IN_PROGRESS"},
        "IN_PROGRESS": {"RESOLVED"},
        "RESOLVED": {"CLOSED"},
        "CLOSED": set(),
    },
    "decision": {
        "OPEN": {"ANALYSIS"},
        "ANALYSIS": {"DECIDED"},
        "DECIDED": {"COMMUNICATED"},
        "COMMUNICATED": {"CLOSED"},
        "CLOSED": set(),
    },
    "change": {
        "DRAFT": {"SUBMITTED"},
        "SUBMITTED": {"IMPACT_ANALYSIS"},
        "IMPACT_ANALYSIS": {"APPROVAL"},
        "APPROVAL": {"APPROVED", "REJECTED"},
        "APPROVED": {"IMPLEMENTING"},
        "REJECTED": set(),
        "IMPLEMENTING": {"VERIFIED"},
        "VERIFIED": {"CLOSED"},
        "CLOSED": set(),
    },
    "requirement": {
        "DRAFT": {"REVIEW"},
        "REVIEW": {"APPROVED"},
        "APPROVED": {"IMPLEMENTED"},
        "IMPLEMENTED": {"VERIFIED"},
        "VERIFIED": {"ACCEPTED"},
        "ACCEPTED": set(),
    },
    "deliverable": {
        "PLANNED": {"IN_PROGRESS"},
        "IN_PROGRESS": {"READY_FOR_ACCEPTANCE"},
        "READY_FOR_ACCEPTANCE": {"ACCEPTED", "REJECTED"},
        "ACCEPTED": {"CLOSED"},
        "REJECTED": {"IN_PROGRESS"},
        "CLOSED": set(),
    },
    "document": {
        "DRAFT": {"IN_REVIEW"},
        "IN_REVIEW": {"APPROVED"},
        "APPROVED": {"BASELINED"},
        "BASELINED": {"SUPERSEDED"},
        "SUPERSEDED": set(),
    },
    "meeting": {
        "PLANNED": {"HELD"},
        "HELD": {"MINUTES_DRAFT"},
        "MINUTES_DRAFT": {"MINUTES_APPROVED"},
        "MINUTES_APPROVED": {"CLOSED"},
        "CLOSED": set(),
    },
}


@dataclass(frozen=True, slots=True)
class WorkflowEngine:
    workflows: dict[str, dict[str, set[str]]]

    def allowed_targets(self, kind: str, status: str) -> set[str]:
        return set(self.workflows.get(kind, {}).get(status, set()))

    def validate(self, kind: str, current: str, target: str) -> None:
        if kind not in self.workflows:
            raise WorkflowError(f"Workflow inconnu : {kind}.")
        if current not in self.workflows[kind]:
            raise WorkflowError(f"État {current} inconnu pour le workflow {kind}.")
        if target not in self.workflows[kind][current]:
            raise WorkflowError(
                f"Transition interdite pour {kind} : {current} → {target}. "
                f"États permis : {', '.join(sorted(self.workflows[kind][current])) or 'aucun'}."
            )


DEFAULT_WORKFLOW_ENGINE = WorkflowEngine(WORKFLOWS)
