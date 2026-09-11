# PM² Desktop — Architecture V0.1

## 1. Objectif
Application desktop offline-first de gestion de projets basée sur PM² v3.1. La V0.1 doit gérer le cycle de vie complet : Lancement, Planification, Exécution, Clôture, avec Suivi & Contrôle transversal.

## 2. Stack imposée
- Python 3.12+
- PySide6 / Qt6
- SQLAlchemy 2.x
- SQLite
- Alembic
- Pydantic v2
- Jinja2
- python-docx
- ReportLab
- pytest
- Ruff
- mypy
- PyInstaller

## 3. Principes
- Offline-first, aucune dépendance serveur.
- Architecture en couches : domain / application / infrastructure / ui.
- PM² ne doit pas être codé en dur dans les écrans.
- Les règles méthodologiques sont décrites par des données de configuration.
- Les documents sont générés à partir des données métier.
- Toutes les entités importantes possèdent un identifiant stable.
- Toute modification importante est historisable.
- Les objets doivent être interconnectables pour assurer la traçabilité.

## 4. Architecture
src/pm2/
  domain/
  application/
  infrastructure/
  methodology/
  ui/

### domain
Entités et invariants métier indépendants de Qt et SQLite.

### application
Services/use cases : création de projet, transitions de phase, registres, validations, gates, génération documentaire, traçabilité.

### infrastructure
SQLAlchemy, SQLite, repositories, exporteurs, stockage des pièces jointes.

### methodology
Chargement et validation de PM²_METHODOLOGY.yaml : phases, rôles, artefacts, activités, gates, responsabilités, règles.

### ui
PySide6. MainWindow + navigation + vues métier + dialogues + modèles Qt.

## 5. Format projet
Extension : .pm2

Le fichier est un ZIP contenant :
project.db
manifest.json
documents/
attachments/
exports/

manifest.json contient version du format, identifiant projet, méthodologie, version de méthodologie et date de dernière sauvegarde.

## 6. Navigation principale
Dashboard
Projet
Gouvernance
Lancement
Planification
Exécution
Suivi & Contrôle
Clôture
Registres
Documents
Paramètres

## 7. Services
ProjectService
PhaseService
GateService
ResponsibilityService
StakeholderService
WorkPlanService
RequirementService
DeliverableService
RiskService
IssueService
DecisionService
ChangeService
QualityService
AcceptanceService
TransitionService
MeetingService
DocumentService
ValidationService
TraceabilityService
ExportService
AuditService

## 8. Non-objectifs V0.1
Pas de cloud, serveur, collaboration temps réel, authentification réseau, PM² Agile, PM² Programme/Portfolio, EVM avancée, Critical Chain, IA, plugins.
