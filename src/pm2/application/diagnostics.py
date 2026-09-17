from __future__ import annotations

import json
import os
import platform
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alembic.runtime.migration import MigrationContext
from sqlalchemy import func, inspect, select

from pm2 import __version__
from pm2.application.context import ApplicationContext
from pm2.infrastructure.orm import ProjectModel


def collect_diagnostics(context: ApplicationContext) -> dict[str, Any]:
    """Collect support data without project names, identifiers, content, or local paths."""
    with context.database.engine.connect() as connection:
        revision = MigrationContext.configure(connection).get_current_revision()
    with context.database.session_factory() as session:
        projects = session.scalar(select(func.count()).select_from(ProjectModel)) or 0
    database_size = context.database.path.stat().st_size if context.database.path else None
    methodology = context.methodology.methodology
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "application": {"name": "PM² Desktop", "version": __version__},
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.system(),
            "platform_release": platform.release(),
        },
        "database": {
            "schema_revision": revision,
            "size_bytes": database_size,
            "table_count": len(inspect(context.database.engine).get_table_names()),
            "project_count": projects,
        },
        "methodology": {
            "id": methodology.id,
            "version": methodology.version,
            "language": methodology.language,
            "sha256": context.methodology_hash,
        },
    }


def export_diagnostics(context: ApplicationContext, destination: Path) -> Path:
    """Atomically write an anonymized diagnostic report."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(collect_diagnostics(context), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination
