from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pm2.infrastructure.database import Database
from pm2.methodology import MethodologyBundle, PM2Configuration, load_default_methodology_bundle


@dataclass(slots=True)
class ApplicationContext:
    database: Database
    methodology_bundle: MethodologyBundle

    @property
    def methodology(self) -> PM2Configuration:
        return self.methodology_bundle.configuration

    @property
    def methodology_snapshot(self) -> str:
        return self.methodology_bundle.snapshot

    @property
    def methodology_hash(self) -> str:
        return self.methodology_bundle.sha256

    @classmethod
    def open(cls, database_path: Path | str, *, create: bool = True) -> ApplicationContext:
        database = Database(database_path)
        if create:
            database.create_schema()
        else:
            database.ensure_schema_compatibility()
        return cls(database=database, methodology_bundle=load_default_methodology_bundle())
