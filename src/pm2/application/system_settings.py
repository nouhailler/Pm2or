from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SystemSettings:
    legal_accepted_version: str = ""
    last_update_check: str = ""
    automatic_update_checks: bool = True
    automatic_update_install: bool = False
    update_interval_hours: int = 6
    seen_contextual_help: list[str] = field(default_factory=list)

    @property
    def last_update_check_label(self) -> str:
        if not self.last_update_check:
            return "Jamais"
        try:
            checked = datetime.fromisoformat(self.last_update_check)
        except ValueError:
            return "Inconnue"
        return checked.astimezone().strftime("%d.%m.%Y à %H:%M")


class SystemSettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.value = self._load()

    def _load(self) -> SystemSettings:
        if not self.path.is_file():
            return SystemSettings()
        try:
            payload: Any = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return SystemSettings()
            allowed = SystemSettings.__dataclass_fields__
            return SystemSettings(**{key: value for key, value in payload.items() if key in allowed})
        except (OSError, ValueError, TypeError):
            return SystemSettings()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".saving")
        temporary.write_text(
            json.dumps(asdict(self.value), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(self.path)

    def record_update_check(self) -> None:
        self.value.last_update_check = datetime.now(UTC).replace(microsecond=0).isoformat()
        self.save()

    def mark_help_seen(self, page_name: str) -> None:
        if page_name not in self.value.seen_contextual_help:
            self.value.seen_contextual_help.append(page_name)
            self.save()
