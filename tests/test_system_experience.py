from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pm2.application.system_settings import SystemSettingsStore
from pm2.application.updates import (
    ReleaseInfo,
    UpdateError,
    UpdateService,
    install_desktop_shortcut,
)
from pm2.ui.main_window import MainWindow
from pm2.ui.system_experience import LEGAL_VERSION, OnboardingDialog, SystemSettingsDialog


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def test_system_settings_are_persisted_and_timestamped(tmp_path: Path) -> None:
    path = tmp_path / "system-settings.json"
    store = SystemSettingsStore(path)
    store.value.automatic_update_install = True
    store.value.legal_accepted_version = LEGAL_VERSION
    store.record_update_check()

    restored = SystemSettingsStore(path)

    assert restored.value.automatic_update_install
    assert restored.value.legal_accepted_version == LEGAL_VERSION
    assert restored.value.last_update_check_label != "Jamais"
    assert datetime.fromisoformat(restored.value.last_update_check).tzinfo == UTC


def test_update_download_requires_and_verifies_sha256(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = b"verified deb package"
    release = ReleaseInfo(
        version="9.9.9",
        published_at="2026-10-31T10:00:00Z",
        page_url="https://github.com/nouhailler/Pm2or/releases/tag/v9.9.9",
        download_url=(
            "https://github.com/nouhailler/Pm2or/releases/download/"
            "v9.9.9/pm2-desktop_9.9.9_amd64.deb"
        ),
        filename="pm2-desktop_9.9.9_amd64.deb",
        sha256=hashlib.sha256(content).hexdigest(),
    )
    monkeypatch.setattr(
        "pm2.application.updates.urlopen",
        lambda *_args, **_kwargs: _Response(content),
    )

    downloaded = UpdateService().download(release, tmp_path)

    assert downloaded.read_bytes() == content
    assert release.is_newer
    with pytest.raises(UpdateError, match="empreinte"):
        UpdateService().download(
            ReleaseInfo(
                release.version,
                release.published_at,
                release.page_url,
                release.download_url,
                release.filename,
                None,
            ),
            tmp_path,
        )


def test_desktop_installer_creates_launcher_and_icon(tmp_path: Path) -> None:
    executable = tmp_path / "pm2-desktop"
    executable.write_text("binary", encoding="utf-8")
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"png")

    launcher = install_desktop_shortcut(executable, logo, tmp_path / "home")

    assert launcher.is_file()
    assert str(executable) in launcher.read_text(encoding="utf-8")
    assert launcher.stat().st_mode & 0o100


def test_onboarding_requires_legal_acceptance(qtbot: Any, tmp_path: Path) -> None:
    store = SystemSettingsStore(tmp_path / "settings.json")
    dialog = OnboardingDialog(store)
    qtbot.addWidget(dialog)

    dialog._next()
    assert dialog.pages.currentIndex() == 1
    dialog.accept_legal.setChecked(True)
    dialog._next()
    dialog._next()

    assert store.value.legal_accepted_version == LEGAL_VERSION


def test_hamburger_toggles_grouped_navigation(
    qtbot: Any, context: Any, project: Any, tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("PM2_DISABLE_UPDATE_CHECK", "1")
    paths = type(
        "Paths",
        (),
        {
            "data_dir": tmp_path,
            "database": context.database.path,
            "log_file": tmp_path / "app.log",
            "recent_file": tmp_path / "recent.json",
        },
    )()
    store = SystemSettingsStore(tmp_path / "system-settings.json")
    store.value.legal_accepted_version = LEGAL_VERSION
    store.save()
    window = MainWindow(context, paths)
    qtbot.addWidget(window)
    assert window.project is not None
    assert not window.navigation.isHidden()

    window.toggle_navigation()

    assert not window.navigation.isVisible()
    assert "Étapes du projet" in window.navigation.groups


def test_system_settings_dialog_exposes_release_information(
    qtbot: Any, tmp_path: Path
) -> None:
    store = SystemSettingsStore(tmp_path / "settings.json")

    class Updates:
        checking = type("Signal", (), {"connect": lambda *_args: None})()
        checked = type("Signal", (), {"connect": lambda *_args: None})()
        failed = type("Signal", (), {"connect": lambda *_args: None})()
        installation_started = type("Signal", (), {"connect": lambda *_args: None})()

        def check_now(self, *, manual: bool = True) -> None:
            pass

        def apply_preferences(self) -> None:
            pass

    dialog = SystemSettingsDialog(store, Updates())  # type: ignore[arg-type]
    qtbot.addWidget(dialog)

    labels = [label.text() for label in dialog.findChildren(type(dialog.last_check))]
    assert "01.11.2026" in labels
    assert any("Dernière vérification" in label for label in labels)
