from __future__ import annotations

from importlib import resources
from pathlib import Path

import yaml
from pydantic import ValidationError

from pm2.methodology.models import PM2Configuration


class MethodologyLoadError(RuntimeError):
    pass


class MethodologyLoader:
    @staticmethod
    def load(path: Path | str) -> PM2Configuration:
        source = Path(path)
        try:
            raw = yaml.safe_load(source.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise MethodologyLoadError(
                    "La configuration méthodologique doit être un objet YAML."
                )
            return PM2Configuration.model_validate(raw)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise MethodologyLoadError(f"Configuration PM² invalide ({source}) : {exc}") from exc


def load_default_methodology() -> PM2Configuration:
    candidates = [
        Path.cwd() / "04_PM2_METHODOLOGY.yaml",
        Path(__file__).resolve().parents[3] / "04_PM2_METHODOLOGY.yaml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return MethodologyLoader.load(candidate)
    try:
        packaged = resources.files("pm2").joinpath("resources/PM2_METHODOLOGY.yaml")
        with resources.as_file(packaged) as path:
            return MethodologyLoader.load(path)
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise MethodologyLoadError("04_PM2_METHODOLOGY.yaml est introuvable.") from exc
