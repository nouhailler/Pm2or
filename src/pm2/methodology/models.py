from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)


class MethodologyIdentity(StrictModel):
    id: Literal["pm2"]
    name: str
    version: Literal["3.1"]
    language: Literal["fr"]
    source: str
    machine_readable_contract: bool = True
    implementation_policy: list[str] = Field(default_factory=list)


class PhaseDefinition(StrictModel):
    code: Literal["LAUNCH", "PLANNING", "EXECUTION", "CLOSING"]
    name: str
    order: int = Field(ge=1, le=4)
    purpose: str
    source_section: str


class TransversalDefinition(StrictModel):
    code: Literal["MONITORING_CONTROL"]
    name: str
    purpose: str
    source_section: str


class LifecycleDefinition(StrictModel):
    phases: list[PhaseDefinition]
    transversal: list[TransversalDefinition]

    @model_validator(mode="after")
    def validate_phase_order(self) -> LifecycleDefinition:
        if [phase.code for phase in sorted(self.phases, key=lambda item: item.order)] != [
            "LAUNCH",
            "PLANNING",
            "EXECUTION",
            "CLOSING",
        ]:
            raise ValueError("Les quatre phases PM² doivent être présentes dans l'ordre attendu.")
        return self


class RoleDefinition(StrictModel):
    code: str
    name: str
    optional: bool = False
    note: str | None = None


class RolesDefinition(StrictModel):
    standard: list[RoleDefinition]
    support: list[RoleDefinition] = Field(default_factory=list)
    operational_custom: dict[str, Any] = Field(default_factory=dict)


class ActivityDefinition(StrictModel):
    code: str
    phase: str
    name: str
    objective: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    related_artifacts: list[str] = Field(default_factory=list)
    source_section: str
    optional: bool = False


class ArtifactDefinition(StrictModel):
    name: str
    phase: str
    required: bool
    baseline: bool = False


class ChecklistDefinition(StrictModel):
    id: str
    description: str
    type: str
    required: bool
    artifact: str | None = None


class GateDefinition(StrictModel):
    code: Literal["RFP", "RFE", "RFC"]
    name: str
    label: str
    from_phase: str
    to_phase: str
    review_point: str
    approver_roles: list[str]
    responsible_role: str
    checklist: list[ChecklistDefinition]
    source_section: str


class MethodologyValidationRule(StrictModel):
    id: str
    severity: Literal["ERROR", "WARNING", "INFO"]
    applies_to: str
    condition: str
    message: str


class ValidationRulesDefinition(StrictModel):
    severity: list[Literal["ERROR", "WARNING", "INFO"]]
    rules: list[MethodologyValidationRule]


class PM2Configuration(StrictModel):
    methodology: MethodologyIdentity
    lifecycle: LifecycleDefinition
    status_model: dict[str, list[str]]
    roles: RolesDefinition
    responsibility_types: dict[str, dict[str, Any]]
    ram_matrix: dict[str, Any]
    activities: list[ActivityDefinition]
    artifacts: dict[str, ArtifactDefinition]
    registers: list[dict[str, Any]]
    monitoring_control: dict[str, Any]
    gates: list[GateDefinition]
    validation_rules: ValidationRulesDefinition
    traceability: dict[str, Any]
    optional_features: dict[str, Any]
    source_notes: dict[str, Any]

    def gate(self, code: str) -> GateDefinition:
        try:
            return next(gate for gate in self.gates if gate.code == code)
        except StopIteration as exc:
            raise KeyError(f"Gate PM² inconnu : {code}") from exc
