from __future__ import annotations

import hashlib
import json
import shlex
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pm2 import __version__

REPOSITORY = "nouhailler/Pm2or"
RELEASE_DATE = date(2026, 11, 1)


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    version: str
    published_at: str
    page_url: str
    download_url: str
    filename: str
    sha256: str | None

    @property
    def is_newer(self) -> bool:
        return _version_tuple(self.version) > _version_tuple(__version__)


def _version_tuple(value: str) -> tuple[int, ...]:
    cleaned = value.strip().lstrip("v").split("-", 1)[0]
    try:
        return tuple(int(part) for part in cleaned.split("."))
    except ValueError:
        return (0,)


def _safe_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not (
        parsed.hostname == "github.com"
        or (parsed.hostname or "").endswith(".github.com")
        or (parsed.hostname or "").endswith(".githubusercontent.com")
    ):
        raise UpdateError("L'adresse de téléchargement de la mise à jour n'est pas fiable.")
    return value


class UpdateService:
    API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"

    def latest_release(self, timeout: float = 12.0) -> ReleaseInfo:
        payload = self._json(self.API_URL, timeout)
        version = str(payload.get("tag_name", "")).lstrip("v")
        assets = payload.get("assets", [])
        if not version or not isinstance(assets, list):
            raise UpdateError("La réponse du serveur de mises à jour est incomplète.")
        deb = next(
            (
                asset
                for asset in assets
                if isinstance(asset, dict)
                and str(asset.get("name", "")).endswith("_amd64.deb")
            ),
            None,
        )
        if deb is None:
            raise UpdateError("La dernière version ne contient pas de paquet Debian amd64.")
        digest = str(deb.get("digest") or "")
        sha256 = digest.removeprefix("sha256:") if digest.startswith("sha256:") else None
        return ReleaseInfo(
            version=version,
            published_at=str(payload.get("published_at", "")),
            page_url=_safe_url(str(payload.get("html_url", ""))),
            download_url=_safe_url(str(deb.get("browser_download_url", ""))),
            filename=str(deb.get("name")),
            sha256=sha256,
        )

    def download(self, release: ReleaseInfo, directory: Path, timeout: float = 60.0) -> Path:
        if not release.sha256:
            raise UpdateError(
                "Installation automatique refusée : aucune empreinte SHA-256 publiée."
            )
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / release.filename
        temporary = destination.with_suffix(destination.suffix + ".part")
        request = Request(
            _safe_url(release.download_url),
            headers={"User-Agent": f"PM2-Desktop/{__version__}"},
        )
        digest = hashlib.sha256()
        try:
            with urlopen(request, timeout=timeout) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise UpdateError(f"Téléchargement impossible : {exc}") from exc
        if digest.hexdigest().casefold() != release.sha256.casefold():
            temporary.unlink(missing_ok=True)
            raise UpdateError("L'empreinte SHA-256 de la mise à jour est invalide.")
        temporary.replace(destination)
        return destination

    def _json(self, url: str, timeout: float) -> dict[str, Any]:
        request = Request(
            _safe_url(url),
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"PM2-Desktop/{__version__}",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload: Any = json.load(response)
        except (OSError, ValueError) as exc:
            raise UpdateError(f"Vérification impossible : {exc}") from exc
        if not isinstance(payload, dict):
            raise UpdateError("Réponse de mise à jour invalide.")
        return payload


def install_desktop_shortcut(executable: Path, logo: Path, home: Path) -> Path:
    applications = home / ".local" / "share" / "applications"
    icons = home / ".local" / "share" / "icons" / "hicolor" / "512x512" / "apps"
    applications.mkdir(parents=True, exist_ok=True)
    icons.mkdir(parents=True, exist_ok=True)
    icon_target = icons / "pm2-desktop.png"
    shutil.copy2(logo, icon_target)
    launcher = applications / "pm2-desktop.desktop"
    launcher.write_text(
        "[Desktop Entry]\nType=Application\nName=PM² Desktop\n"
        "Comment=Gestion de projets PM² hors ligne\n"
        f"Exec={shlex.quote(str(executable))}\nIcon={icon_target}\nTerminal=false\n"
        "Categories=Office;ProjectManagement;\n",
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    return launcher
