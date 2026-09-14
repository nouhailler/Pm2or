from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import yaml
from pydantic import ValidationError

from pm2.methodology.models import PM2Configuration


class MethodologyLoadError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MethodologyBundle:
    configuration: PM2Configuration
    snapshot: str
    sha256: str
    source: str


def methodology_sha256(snapshot: str) -> str:
    return hashlib.sha256(snapshot.encode("utf-8")).hexdigest()


def dump_methodology(configuration: PM2Configuration) -> str:
    """Return the canonical YAML persisted with projects and archives."""
    return yaml.safe_dump(
        configuration.model_dump(mode="json"),
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )


def bundle_methodology(
    configuration: PM2Configuration, *, source: str = "configuration"
) -> MethodologyBundle:
    snapshot = dump_methodology(configuration)
    return MethodologyBundle(
        configuration=configuration,
        snapshot=snapshot,
        sha256=methodology_sha256(snapshot),
        source=source,
    )


class MethodologyLoader:
    @staticmethod
    def load(path: Path | str) -> PM2Configuration:
        source = Path(path)
        try:
            return MethodologyLoader.load_text(
                source.read_text(encoding="utf-8"), source=str(source)
            )
        except OSError as exc:
            raise MethodologyLoadError(f"Configuration PM² invalide ({source}) : {exc}") from exc

    @staticmethod
    def load_text(snapshot: str, *, source: str = "snapshot") -> PM2Configuration:
        try:
            raw = yaml.safe_load(snapshot)
            if not isinstance(raw, dict):
                raise MethodologyLoadError(
                    "La configuration méthodologique doit être un objet YAML."
                )
            return PM2Configuration.model_validate(raw)
        except (yaml.YAMLError, ValidationError) as exc:
            raise MethodologyLoadError(f"Configuration PM² invalide ({source}) : {exc}") from exc

    @staticmethod
    def bundle(path: Path | str) -> MethodologyBundle:
        source = Path(path)
        configuration = MethodologyLoader.load(source)
        return bundle_methodology(configuration, source=str(source))


def load_default_methodology_bundle() -> MethodologyBundle:
    candidates = [
        Path.cwd() / "04_PM2_METHODOLOGY.yaml",
        Path(__file__).resolve().parents[3] / "04_PM2_METHODOLOGY.yaml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return MethodologyLoader.bundle(candidate)
    try:
        packaged = resources.files("pm2").joinpath("resources/PM2_METHODOLOGY.yaml")
        configuration = MethodologyLoader.load_text(
            packaged.read_text(encoding="utf-8"), source=str(packaged)
        )
        return bundle_methodology(configuration, source=str(packaged))
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise MethodologyLoadError("04_PM2_METHODOLOGY.yaml est introuvable.") from exc


def load_default_methodology() -> PM2Configuration:
    return load_default_methodology_bundle().configuration
