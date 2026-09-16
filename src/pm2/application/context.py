from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import inspect

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
        path = Path(database_path) if str(database_path) != ":memory:" else None
        if not create and path is not None and not path.is_file():
            raise FileNotFoundError(f"Base de données introuvable : {path}")
        database = Database(database_path)
        try:
            if not create and "projects" not in inspect(database.engine).get_table_names():
                raise ValueError("Le fichier sélectionné n'est pas une base PM² Desktop.")
            database.upgrade_schema()
            methodology = load_default_methodology_bundle()
        except Exception:
            database.dispose()
            raise
        return cls(database=database, methodology_bundle=methodology)
