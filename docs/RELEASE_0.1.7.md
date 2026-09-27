# PM² Desktop 0.1.7

Cette version transforme PM² Desktop en assistant de pilotage quotidien, avec des
références immuables et un historique professionnel.

## Nouveautés

- **Cockpit projet** : avancement, budget consommé, dérive d'échéance, registres
  actifs, santé par domaine et prochaines actions cliquables.
- **Centre de conformité PM²** : score global et par phase, readiness détaillée des
  gates RfP, RfE et RfC, anomalies regroupées et corrections guidées.
- **Audit Trail professionnel** : timeline filtrable, utilisateur, date, origine,
  objet, raison et comparaison champ par champ des valeurs Avant/Après.
- **Baselines immuables** : snapshots SHA-256 approuvables couvrant le Work Plan,
  les exigences, livrables, risques, documents, budget et jalons.
- Migrations Alembic `0004` et `0005`, journal d'audit et baselines protégés contre
  la modification ou la suppression au niveau SQLite.

## Installation

Le paquet cible Debian 13 amd64 avec glibc 2.41 ou ultérieure.

```bash
sudo apt install ./pm2-desktop_0.1.7_amd64.deb
pm2-desktop
```

Vérifiez le paquet téléchargé avec :

```bash
sha256sum -c SHA256SUMS-0.1.7
```

## Validation

La publication est validée par 127 tests automatisés avec une couverture lignes et
branches de 81,93 %, Ruff, mypy, le démarrage du bundle PyInstaller et le contrôle
du paquet Debian.
