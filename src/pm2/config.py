from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    data_dir: Path
    database: Path
    log_file: Path
    recent_file: Path

    @classmethod
    def default(cls) -> AppPaths:
        root = Path(
            os.environ.get("PM2_DATA_DIR", Path.home() / ".local" / "share" / "pm2-desktop")
        )
        return cls(root, root / "project.db", root / "pm2.log", root / "recent.json")

    def ensure(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
