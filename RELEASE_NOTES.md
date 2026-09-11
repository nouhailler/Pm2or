# PM² Desktop 0.1.0

Publication du 9 septembre 2026.

## Points forts

- assistants complets de Lancement, Planification, Exécution et Clôture ;
- catalogue CRUD des 47 entités métier avec archivage, restauration, historique et audit ;
- édition de la WBS avec déplacement, indentation, désindentation et dépendances ;
- préparation, exécution et décision d’acceptation des livrables depuis l’interface ;
- 21 modèles documentaires PM² spécialisés avec versionnage et empreinte SHA-256 ;
- stockage SQLite local, migrations Alembic et export de projet `.pm2` ;
- fonctionnement entièrement hors ligne.

## Validation de la version

- recette visuelle manuelle courte : 9 écrans représentatifs contrôlés, résultat **PASS** ;
- tests automatisés : **40 réussis** ;
- Ruff : aucune erreur ;
- mypy strict : aucune erreur sur les 16 fichiers contrôlés ;
- démarrage du paquet Linux validé par le contrôle headless.

## Paquets

- `pm2-desktop-0.1.0-linux-x86_64.tar.gz` : application autonome pour Linux x86_64 ;
- `pm2_desktop-0.1.0-py3-none-any.whl` : paquet Python 3.12 ou ultérieur.

Les empreintes d’intégrité sont publiées dans `SHA256SUMS`.

## Installation Linux

Décompresser l’archive, puis lancer :

```bash
./pm2-desktop/pm2-desktop
```

Les données utilisateur restent locales dans le répertoire de données de l’application.
