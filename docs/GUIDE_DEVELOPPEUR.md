# Guide développeur — PM² Desktop V0.1

## Architecture

Le paquet `pm2` respecte quatre couches principales :

- `domain` : types, invariants et moteur de workflow sans Qt ni SQLAlchemy ;
- `application` : services/cas d'utilisation, validation, documents et exports ;
- `infrastructure` : modèles SQLAlchemy, repositories, SQLite et archives ;
- `methodology` : modèles Pydantic et chargement YAML ;
- `ui` : fenêtres, pages et dialogues PySide6 qui appellent les services.

Le flux d'écriture normal est `widget → service → repository/session → SQLite`. Aucun widget ne décide de la validité d'une transition métier.

## Base de données

`pm2.infrastructure.orm.Base.metadata` décrit les 47 tables contractuelles. `Database` active `PRAGMA foreign_keys=ON` sur chaque connexion. Les objets référencés ont `archived`/`deleted_at`; la cascade est réservée aux enfants stricts.

La migration initiale se lance ainsi :

```bash
PYTHONPATH=src .venv/bin/alembic upgrade head
```

Pour une nouvelle migration, modifiez d'abord les modèles, ajoutez une révision sous `migrations/versions`, puis testez un upgrade sur une base vide et une copie de données.

## Méthodologie

`04_PM2_METHODOLOGY.yaml` est validé par `PM2Configuration` au démarrage. Une configuration invalide produit `MethodologyLoadError` avant l'ouverture de l'interface. Ajoutez les règles PM² dans le YAML et/ou `ValidationService`, jamais dans un widget.

## Services importants

- `ProjectService`, `GovernanceService`, `ResponsibilityService` ;
- `GateService`, `WorkflowService`, `ValidationService` ;
- `WorkPlanService`, `RequirementService`, `DeliverableService`, `AcceptanceService` ;
- `RiskService`, `IssueService`, `DecisionService`, `ChangeService` ;
- `QualityService`, `TransitionService`, `MeetingService` ;
- `TraceabilityService`, `DocumentService`, `ArtifactDataService`, `EntityCrudService`,
  `ExportService`, `AuditService`.

Les services lèvent des erreurs contenant un message directement compréhensible par l'utilisateur. Une transaction UI est validée uniquement après succès complet, sinon elle est annulée.

## Documents

Le contexte de `DocumentService` agrège le projet, les registres, exigences, livrables, parties prenantes, WBS, acceptations et validations. `ARTIFACT_SCHEMAS` définit des champs et sections propres à chacun des 21 artefacts. Chaque artefact possède ses templates Jinja2 Markdown et HTML ; `python-docx` et ReportLab Platypus réutilisent ces sections spécialisées pour les formats binaires. Toute version générée enregistre son empreinte et son chemin.

## Tests et qualité

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/pytest
.venv/bin/ruff check src tests
PYTHONPATH=src .venv/bin/mypy src/pm2/domain src/pm2/application src/pm2/methodology
```

Les 40 tests couvrent les invariants, les 47 tables, Alembic, les gates, RCmSCI,
workflows, commandes WBS/dépendances, CRUD/audit, acceptation stricte, traçabilité,
les 21 modèles spécialisés, quatre formats documentaires, archive/intégrité, les dix
parcours UI contractuels et le cycle de vie complet jusqu'au rapport final.

## Extension

Pour ajouter une entité : créez le modèle SQLAlchemy et la migration, exposez-la par un service, ajoutez les validations et l'audit nécessaires, puis seulement la vue Qt. Pour ajouter un artefact, déclarez-le dans le YAML, ajoutez son `ArtifactSchema` et ses deux templates spécialisés, puis étendez le contexte avec les seules données métier utiles.
