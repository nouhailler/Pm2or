# PM² Desktop 0.1.1

PM² Desktop est une application de gestion de projets locale, en français, fondée sur la méthodologie PM² v3.1 de la Commission européenne. Elle utilise PySide6/Qt6, SQLAlchemy 2 et SQLite et ne requiert aucun serveur ni accès Internet à l'exécution.

## Fonctions disponibles

- assistants complets Lancement, Planification, Exécution et Clôture avec complétude,
  validations, données sources, artefacts, gates, acceptations et fermeture administrative ;
- gates RfP, RfE et RfC avec checklists issues de la configuration méthodologique ;
- gouvernance, personnes, rôles PM², parties prenantes et matrice RCmSCI ;
- WBS arborescente avec déplacement, réordonnancement, indentation/désindentation,
  archivage, tâches, jalons, dates, effort, coût, avancement et dépendances ;
- exigences, livrables, critères/tests d'acceptation et liens de traçabilité ;
- registres des risques, problèmes, décisions et modifications avec workflows contrôlés ;
- qualité, transition, mise en œuvre organisationnelle et réunions ;
- validation PM² agrégée et filtrable ;
- catalogue détaillé des 47 entités avec CRUD, relations, validation et audit ;
- exécution des tests d'acceptation et acceptation finale contrôlée depuis l'interface ;
- 21 artefacts spécialisés, avec saisie structurée, aperçu, versions et exports Markdown,
  HTML, DOCX et PDF ;
- sauvegarde et réouverture d'archives `.pm2` avec contrôle d'intégrité.

## Installation développeur

Un paquet Debian 13 amd64 est disponible dans les [releases GitHub](https://github.com/nouhailler/Pm2or/releases). Installation : `sudo apt install ./pm2-desktop_0.1.1_amd64.deb`. Voir les [notes de version](docs/RELEASE_0.1.1.md).

Python 3.12 ou supérieur est requis.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
QT_QPA_PLATFORM=offscreen .venv/bin/pytest
.venv/bin/ruff check src tests
.venv/bin/mypy src/pm2/domain src/pm2/application src/pm2/methodology
```

Sous Windows, remplacez `.venv/bin/` par `.venv\Scripts\`.

## Lancement

```bash
.venv/bin/pm2-desktop
```

Une base particulière peut être ouverte avec :

```bash
.venv/bin/pm2-desktop --database /chemin/vers/projet.db
```

Le diagnostic sans interface vérifie la base et la méthodologie :

```bash
.venv/bin/pm2-desktop --headless-check
```

La recette de la V0.1 comprend des tests automatisés, dont les dix parcours Qt de
`10_TEST_PLAN.md` et un cycle de vie complet jusqu'au rapport final.

Les données applicatives sont conservées par défaut dans `~/.local/share/pm2-desktop`. La variable `PM2_DATA_DIR` permet de choisir un autre dossier.

## Construction du paquet desktop

```bash
./scripts/build.sh
```

Le script exécute les contrôles puis construit `dist/pm2-desktop` avec PyInstaller. Consultez [le guide utilisateur](docs/GUIDE_UTILISATEUR.md) et [le guide développeur](docs/GUIDE_DEVELOPPEUR.md) pour la suite.

## Source méthodologique

Le fichier `04_PM2_METHODOLOGY.yaml` est la source de vérité pour les phases, rôles, activités, artefacts, gates, responsabilités et règles PM² de la V0.1. Les widgets Qt ne définissent aucune règle méthodologique et toutes les transitions sont contrôlées par les services applicatifs.

Chaque nouveau projet fige l’identifiant, la version, un snapshot YAML canonique complet et son SHA-256. À la réouverture, les écrans utilisent exclusivement ce snapshot, et non le YAML installé. En cas d’écart, l’interface propose de conserver la méthodologie, examiner les différences ou effectuer une mise à niveau explicite et auditée.

Les archives `.pm2` (format 1.1) embarquent `methodology/PM2_METHODOLOGY.yaml` et vérifient sa cohérence avec le manifeste et SQLite. Les anciens projets sans snapshot ne peuvent être complétés automatiquement que si leur identifiant et leur version correspondent à ceux de la méthodologie installée ; le contenu historique exact ne peut pas être reconstitué a posteriori.
