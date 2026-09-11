from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pm2.infrastructure.database import Database
from pm2.methodology import PM2Configuration, load_default_methodology


@dataclass(slots=True)
class ApplicationContext:
    database: Database
    methodology: PM2Configuration

    @classmethod
    def open(cls, database_path: Path | str, *, create: bool = True) -> ApplicationContext:
        database = Database(database_path)
        if create:
            database.create_schema()
        return cls(database=database, methodology=load_default_methodology())
