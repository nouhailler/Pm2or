"""Assemble le bundle PyInstaller en paquet Debian 13 amd64."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pm2 import __version__


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    bundle = root / "dist/pm2-desktop"
    if not (bundle / "pm2-desktop").is_file():
        raise SystemExit("Construire le bundle avec PyInstaller avant le paquet Debian.")
    destination = root / "dist" / f"pm2-desktop_{__version__}_amd64.deb"
    with tempfile.TemporaryDirectory(prefix="pm2-deb-") as name:
        staging = Path(name)
        shutil.copytree(bundle, staging / "opt/pm2-desktop")
        files = {
            "DEBIAN/control": (
                "Package: pm2-desktop\n"
                f"Version: {__version__}\n"
                "Section: office\nPriority: optional\nArchitecture: amd64\n"
                "Maintainer: nouhailler <patrick.nouhailler@gmail.com>\n"
                "Depends: libc6 (>= 2.41), libstdc++6 (>= 14), libgcc-s1, libgl1, libegl1, libx11-6, libxcb1, libxcb-cursor0, libxkbcommon0, libxkbcommon-x11-0, libfontconfig1, libfreetype6, libdbus-1-3\n"
                "Homepage: https://github.com/nouhailler/Pm2or\n"
                "Description: Gestion de projets PM² locale et hors ligne\n"
                " Assistants PM², WBS, registres, documents et méthodologie figée.\n"
            ),
            "usr/bin/pm2-desktop": '#!/bin/sh\nexec /opt/pm2-desktop/pm2-desktop "$@"\n',
            "usr/share/applications/pm2-desktop.desktop": (
                "[Desktop Entry]\nType=Application\nName=PM² Desktop\n"
                "Comment=Gestion de projets PM² hors ligne\nExec=pm2-desktop\n"
                "Icon=pm2-desktop\nTerminal=false\nCategories=Office;ProjectManagement;\n"
            ),
            "usr/share/icons/hicolor/scalable/apps/pm2-desktop.svg": (
                '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
                '<rect width="128" height="128" rx="24" fill="#18324a"/>'
                '<text x="64" y="82" text-anchor="middle" font-family="sans-serif" font-size="49" fill="white">PM²</text></svg>\n'
            ),
        }
        for relative, content in files.items():
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        (staging / "usr/bin/pm2-desktop").chmod(0o755)
        subprocess.run(
            ["dpkg-deb", "--root-owner-group", "--build", str(staging), str(destination)],
            check=True,
        )
    print(destination)


if __name__ == "__main__":
    main()
