# PM² Desktop 0.1.8

Cette version renforce la planification, les ressources et la traçabilité, tout en
rendant l'application plus simple à découvrir, installer et maintenir.

## Nouveautés

- **Moteur de planning CPM** : dépendances FS, SS, FF et SF, lag/lead, calcul des
  dates au plus tôt et au plus tard, marge totale et chemins critiques.
- **Gestion des ressources** : personnes, équipes, fournisseurs, équipements et
  budgets, disponibilités hebdomadaires, allocations et alertes de surcharge.
- **Graphe de traçabilité** : relations entre exigences, tâches, livrables,
  acceptations, risques, mitigations et changements, avec détection des orphelins.
- **Expérience guidée** : menu hamburger, catégories fonctionnelles, onboarding
  légal et contextuel, infobulles généralisées, nouveau logo et capture d'écran.
- **Mises à jour sécurisées** : paramètres système, vérification périodique des
  releases, téléchargement contrôlé par SHA-256 et installation automatique optionnelle.
- **Centre de connaissances** : plus de 60 notions, 12 fiches méthodologiques,
  chronologie historique, recherche et guide de choix disponibles hors ligne.
- **Installation simplifiée** : bouton de création d'un lanceur desktop Linux avec icône.
- Migration Alembic `0006` pour les ressources, avec intégration aux baselines.

## Installation

Le paquet cible Debian 13 amd64 avec glibc 2.41 ou ultérieure.

```bash
sudo apt install ./pm2-desktop_0.1.8_amd64.deb
pm2-desktop
```

Vérifiez le paquet téléchargé avec :

```bash
sha256sum -c SHA256SUMS-0.1.8
```

Une installation existante peut être mise à niveau avec la même commande `apt`.
Les bases sont sauvegardées automatiquement avant l'application des migrations.

## Validation

La publication est validée par 158 tests automatisés avec une couverture lignes et
branches de 82,70 %, Ruff, mypy, l'audit des dépendances, un SBOM CycloneDX, le
démarrage du bundle PyInstaller et l'inspection du paquet Debian.
