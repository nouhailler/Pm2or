# PM² Desktop 0.1.1

Cette version fige la méthodologie de chaque projet : snapshot YAML complet, version et empreinte SHA-256. À l’ouverture, le projet conserve sa configuration ; l’interface permet de comparer et de demander explicitement une mise à niveau auditée.

Les archives `.pm2` au format 1.1 embarquent la méthodologie et vérifient sa cohérence avec le manifeste et SQLite. Migration des anciennes bases incluse.

## Installation

Paquet pour **Debian 13 amd64** (glibc 2.41 ou ultérieure). La compatibilité avec Debian 12 et Ubuntu 24.04 n’est pas assurée.

```bash
sudo apt install ./pm2-desktop_0.1.1_amd64.deb
pm2-desktop
```

Un lanceur est installé dans le menu des applications. Python est embarqué dans le paquet.

## Vérification

53 tests automatisés ; Ruff et mypy. Construction PyInstaller et contrôle de démarrage du paquet extrait. Le fichier SHA256SUMS permet de vérifier le téléchargement.

## Construction

```bash
.venv/bin/pyinstaller --noconfirm pm2-desktop.spec
.venv/bin/python scripts/package_deb.py
```
