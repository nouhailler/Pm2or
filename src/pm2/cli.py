from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import inspect

from pm2 import __version__
from pm2.application.context import ApplicationContext
from pm2.application.diagnostics import export_diagnostics
from pm2.config import AppPaths
from pm2.logging_config import configure_logging


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="PM² Desktop — gestion de projets hors ligne")
    result.add_argument("--database", type=Path, help="Base SQLite locale à ouvrir")
    result.add_argument(
        "--headless-check", action="store_true", help="Vérifier l'environnement sans ouvrir Qt"
    )
    result.add_argument(
        "--diagnostics",
        type=Path,
        metavar="FICHIER",
        help="Exporter un diagnostic anonymisé au format JSON sans ouvrir Qt",
    )
    result.add_argument("--version", action="version", version=f"PM² Desktop {__version__}")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    paths = AppPaths.default()
    paths.ensure()
    configure_logging(paths.log_file)
    database = args.database or paths.database
    if args.headless_check or args.diagnostics:
        context = ApplicationContext.open(database)
        if args.diagnostics:
            destination = export_diagnostics(context, args.diagnostics)
            print(json.dumps({"status": "ok", "diagnostics": str(destination)}))
            context.database.dispose()
            return 0
        payload = {
            "status": "ok",
            "version": __version__,
            "database": str(database),
            "methodology": context.methodology.methodology.id,
            "methodology_version": context.methodology.methodology.version,
            "language": context.methodology.methodology.language,
            "tables": len(inspect(context.database.engine).get_table_names()),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        context.database.dispose()
        return 0
    from pm2.ui.app import run_gui

    return run_gui(database)
