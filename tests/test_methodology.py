import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from pm2.methodology import loader
from pm2.methodology.loader import (
    MethodologyLoader,
    MethodologyLoadError,
    load_default_methodology,
    load_default_methodology_bundle,
    methodology_sha256,
)


def test_default_methodology_contract() -> None:
    config = load_default_methodology()
    assert (config.methodology.id, config.methodology.version, config.methodology.language) == (
        "pm2",
        "3.1",
        "fr",
    )
    assert [phase.code for phase in config.lifecycle.phases] == [
        "LAUNCH",
        "PLANNING",
        "EXECUTION",
        "CLOSING",
    ]
    assert [gate.code for gate in config.gates] == ["RFP", "RFE", "RFC"]
    assert {role.code for role in config.roles.standard} >= {"PM", "PO", "PSC", "AGB"}
    assert len(config.artifacts) == 21


def test_invalid_methodology_has_explicit_error(tmp_path: Path) -> None:
    source = tmp_path / "invalid.yaml"
    source.write_text("methodology: invalid", encoding="utf-8")
    with pytest.raises(MethodologyLoadError, match="Configuration PM² invalide"):
        MethodologyLoader.load(source)


def test_default_methodology_has_canonical_verifiable_snapshot() -> None:
    bundle = load_default_methodology_bundle()
    assert MethodologyLoader.load_text(bundle.snapshot) == bundle.configuration
    assert methodology_sha256(bundle.snapshot) == bundle.sha256
    assert len(bundle.sha256) == 64


def test_pyinstaller_methodology_loads_outside_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).resolve().parents[1]

    def analysis(*args, **kwargs):
        return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])

    def build_step(*args, **kwargs):
        return None

    spec = runpy.run_path(
        str(root / "pm2-desktop.spec"),
        init_globals={
            "SPECPATH": str(root),
            "Analysis": analysis,
            "PYZ": build_step,
            "EXE": build_step,
            "COLLECT": build_step,
        },
    )
    package = tmp_path / "_internal" / "pm2"
    for destination, source, kind in spec["a"].datas:
        assert kind == "DATA"
        target = tmp_path / "_internal" / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(source).read_bytes())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(loader, "__file__", str(package / "methodology" / "loader.py"))
    monkeypatch.setattr(loader.resources, "files", lambda name: package)
    bundle = load_default_methodology_bundle()
    assert bundle.configuration.methodology.id == "pm2"
    assert bundle.configuration.methodology.version == "3.1"
    assert bundle.source == str(package / "resources" / "PM2_METHODOLOGY.yaml")
