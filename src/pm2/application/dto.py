from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectCreateDTO(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    reference: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    project_manager: str = ""
    project_owner: str = ""
    approved_budget: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    start_date: date | None = None
    target_end_date: date | None = None

    @model_validator(mode="after")
    def coherent_dates(self) -> ProjectCreateDTO:
        if self.start_date and self.target_end_date and self.target_end_date < self.start_date:
            raise ValueError("La date de fin cible doit suivre la date de début.")
        return self


class ValidationProblemDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    severity: str
    message: str
    entity: str
    entity_id: str | None = None
