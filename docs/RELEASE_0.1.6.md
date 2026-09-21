# PM² Desktop 0.1.6

Cette version consolide la robustesse, la maintenabilité et la chaîne de livraison.

## Nouveautés

- écran **Pièces jointes** avec ajout, ouverture, retrait, audit et contrôle SHA-256 ;
- migration Alembic `0003`, sauvegarde automatique avant migration et restauration
  de la base en cas d'échec ;
- diagnostic de support anonymisé avec `--diagnostics` ;
- contrôles supplémentaires des bases SQLite et archives ZIP hostiles ;
- services applicatifs et pages UI découpés en modules métier plus courts ;
- contrôle mypy étendu à toute l'interface PySide6 ;
- 111 tests, couverture lignes/branches de 80,84 % et seuil CI fixé à 80 % ;
- audit des dépendances, SBOM CycloneDX et tests automatisés du bundle et du `.deb`.

## Installation

Le paquet cible Debian 13 amd64 avec glibc 2.41 ou ultérieure.

```bash
sudo apt install ./pm2-desktop_0.1.6_amd64.deb
pm2-desktop
```

Vérifiez les artefacts téléchargés avec :

```bash
sha256sum -c SHA256SUMS-0.1.6
```

## Validation

La publication est validée par pytest avec couverture lignes/branches, Ruff, mypy,
`pip-audit`, génération du SBOM CycloneDX, démarrage du bundle PyInstaller et contrôle
du paquet Debian installé.
