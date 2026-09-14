# Méthodologie figée par projet

## Contrat

`projects` conserve `methodology_id`, `methodology_version`, `methodology_hash` et `methodology_snapshot`. Le snapshot est le YAML canonique de la configuration validée : les commentaires et la mise en forme du fichier source ne participent pas à l’empreinte. Tous les champs méthodologiques, y compris les extensions, sont conservés.

L’application charge la configuration installée pour créer de nouveaux projets et comparer les versions. Elle charge le snapshot SQLite pour les écrans d’un projet existant. Une différence de hash déclenche l’avertissement, même si le numéro de version est identique.

## Choix utilisateur

- **Conserver** : aucun changement de snapshot ni de version.
- **Examiner les différences** : comparaison YAML, puis retour au choix.
- **Mettre à niveau** : remplacement explicite du snapshot, ajout des rôles et phases manquants, reconstruction des écrans et conservation de l’ancien snapshot dans l’audit. Les données métier et versions documentaires existantes ne sont pas supprimées.

Ce parcours ne constitue pas un moteur universel de migration entre contrats incompatibles : une évolution structurelle majeure devra fournir sa migration métier dédiée.

## Archives

Le format 1.1 contient :

```text
manifest.json
methodology/PM2_METHODOLOGY.yaml
project.db
documents/
attachments/
exports/
```

Le manifeste contient le hash méthodologique et le chemin du snapshot. L’import vérifie les empreintes de SQLite et du YAML, l’identité de la méthodologie et l’égalité du snapshot avec celui de la base avant de remplacer la destination.

## Compatibilité historique

La migration Alembic `0002` et l’ouverture locale ajoutent les colonnes manquantes sans supprimer les données. Un ancien projet sans snapshot ne peut être complété que si son identifiant et sa version correspondent à la configuration installée. Cette inférence est auditée ; elle ne prouve pas que le YAML historique était identique. Une version différente ou un snapshot partiel/corrompu est refusé, sans substitution silencieuse.
