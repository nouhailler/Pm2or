from pathlib import Path

import pytest

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
