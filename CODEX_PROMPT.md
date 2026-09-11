# CODEX MASTER PROMPT — PM² DESKTOP V0.1

Tu es l'ingénieur logiciel principal chargé de construire une application desktop professionnelle nommée PM² Desktop.

## MISSION

Construis une application desktop offline-first de gestion de projets basée sur la méthodologie PM² v3.1 de la Commission européenne.

Tu dois implémenter la V0.1 décrite par les fichiers suivants, qui constituent la spécification contractuelle du projet :

- 01_ARCHITECTURE.md
- 02_DOMAIN_MODEL.md
- 03_DATABASE_SCHEMA.md
- 04_PM2_METHODOLOGY.yaml
- 05_WORKFLOWS.md
- 06_VALIDATION_RULES.md
- 07_UI_SPECIFICATION.md
- 08_DOCUMENT_TEMPLATES.md
- 09_EXPORT_SYSTEM.md
- 10_TEST_PLAN.md
- 11_ACCEPTANCE_CRITERIA.md

NE DEDUIS PAS de nouvelles règles PM² lorsque ces fichiers définissent déjà le comportement attendu. En cas d'ambiguïté technique, choisis l'implémentation la plus simple, testable, offline-first et cohérente avec l'architecture.

## CONTRAINTES ABSOLUES

1. Python 3.12+.
2. PySide6/Qt6 pour l'interface.
3. SQLAlchemy 2.x + SQLite.
4. Alembic pour les migrations.
5. Pydantic v2 pour les DTO/configurations.
6. Jinja2 pour les templates.
7. python-docx pour DOCX.
8. ReportLab Platypus pour PDF.
9. pytest et pytest-qt.
10. Ruff et mypy.
11. Aucune dépendance serveur.
12. L'application doit fonctionner hors ligne.
13. Ne pas utiliser de framework web pour l'UI.
14. Ne pas coder PM² directement dans les widgets.
15. Les règles méthodologiques doivent être chargées depuis 04_PM2_METHODOLOGY.yaml et des modules de règles clairement identifiés.
16. Toutes les transitions métier doivent être contrôlées côté service, jamais seulement côté UI.

## ARCHITECTURE

Crée :

src/pm2/
  domain/
  application/
  infrastructure/
  methodology/
  ui/

Ajoute tests/, templates/, migrations/, docs/.

Utilise des repositories pour isoler SQLAlchemy du domaine.

Les services applicatifs doivent orchestrer les cas d'utilisation.

Les widgets Qt doivent appeler les services et ne doivent pas contenir de logique métier PM².

## MODÈLE MÉTIER

Implémente toutes les entités décrites dans 02_DOMAIN_MODEL.md.

Au minimum :
Project, Phase, Person, Role, ProjectRoleAssignment, Stakeholder, ResponsibilityAssignment, WbsNode, Task, TaskDependency, Deliverable, Requirement, Risk, Issue, Decision, ChangeRequest, QualityControl, QualityFinding, QualityAction, AcceptancePlan, AcceptanceCriterion, AcceptanceTest, Acceptance, TransitionActivity, ImplementationActivity, Meeting, MeetingParticipant, MeetingAction, Communication, Report, Document, DocumentVersion, GateReview, GateChecklistItem, GateDecision, TraceLink, LessonLearned, Recommendation, AuditEvent.

Les relations doivent être navigables depuis l'interface.

## BASE DE DONNÉES

Implémente exactement les tables de 03_DATABASE_SCHEMA.md.

Active SQLite foreign_keys.

Crée une première migration Alembic complète.

Ajoute les index utiles.

Utilise UUID stables.

Prévois archived/deleted_at plutôt que la suppression physique des objets référencés.

## MÉTHODOLOGIE

Charge 04_PM2_METHODOLOGY.yaml au démarrage.

Valide le YAML avec Pydantic.

PM² doit être identifié comme :
id = pm2
version = 3.1
langue = fr

Implémente les phases :
LAUNCH
PLANNING
EXECUTION
CLOSING

Implémente le suivi transversal :
MONITORING_CONTROL

Implémente :
RFP = Ready for Planning
RFE = Ready for Execution
RFC = Ready for Closure

Implémente tous les rôles listés dans le YAML.

Implémente R/Cm/S/C/I.

## WORKFLOWS

Implémente les workflows de 05_WORKFLOWS.md exactement.

Un workflow doit avoir :
- états
- transitions
- garde/validation
- historique
- message d'erreur explicite

Exemple :
ChangeRequest ne peut pas passer à IMPLEMENTING si APPROVED n'est pas acquis.

## VALIDATION

Implémente ValidationService.

Chaque règle doit avoir :
code
severity
message
entity
condition

Les sévérités sont :
ERROR
WARNING
INFO

L'interface doit permettre de filtrer les problèmes.

Les gates utilisent les mêmes validations mais peuvent avoir des règles obligatoires spécifiques.

## GATES

Créer une interface de gate :

Titre
Phase actuelle
Phase cible
Checklist
Statut
Décision
Décideur
Date
Commentaires

Les éléments obligatoires non satisfaits bloquent l'approbation.

Les décisions possibles :
APPROVED
REJECTED
APPROVED_WITH_RESERVES

## RCmSCI

Créer une interface de matrice de responsabilités.

Lignes = activités/artefacts.
Colonnes = rôles.
Cellules = R/Cm/S/C/I.

Bloquer :
- plus d'un R sur un même sujet
- plus d'un Cm sur un même sujet

Permettre les rôles multiples S/C/I.

## WORK PLAN

Créer un éditeur WBS arborescent.

Fonctions :
- créer
- renommer
- déplacer
- indenter/désindenter
- supprimer/archiver
- créer tâche
- créer jalon
- dépendances
- dates
- effort
- coûts
- progression

Ajouter une vue Gantt simple.

Le Work Plan est une source de données centrale.

## REGISTRES

Créer quatre vues de registre professionnelles :

Risques
Problèmes
Décisions
Modifications

Chaque ligne doit avoir :
code
titre
statut
responsable
date
priorité/niveau lorsque pertinent

Chaque fiche doit afficher :
- données
- workflow
- historique
- relations
- validation
- audit

## TRAÇABILITÉ

Implémente TraceabilityService.

Permets :
- créer un lien
- supprimer un lien non critique
- afficher les liens
- filtrer par type
- naviguer vers la cible

Types minimum :
supports
derives_from
impacts
mitigates
resolves
decides
implements
verifies
accepted_by
produces
depends_on
assigned_to
discussed_in
referenced_by

Ajouter une vue "Traçabilité" sur les fiches.

## DOCUMENTS

Les artefacts PM² doivent être générés depuis les données métier.

Ne crée pas des documents avec des données saisies une seconde fois.

Implémente au minimum :
Project Initiation Request
Business Case
Project Charter
Project Handbook
Stakeholder Matrix
Work Plan
Outsourcing Plan
Deliverables Acceptance Plan
Transition Plan
Organisational Implementation Plan
Requirements Management Plan
Change Management Plan
Risk Management Plan
Issue Management Plan
Quality Management Plan
Communications Management Plan
Meeting Minutes
Project Report
Quality Report
Project End Report
Lessons Learned

Chaque document doit avoir :
code
version
status
author
reviewer
approver
dates
historique

## EXPORT

Implémente :
Markdown
HTML
DOCX
PDF
.pm2

Le bundle .pm2 doit contenir :
project.db
manifest.json
documents/
attachments/
exports/

L'import/reouverture doit fonctionner.

## INTERFACE

Construis une MainWindow avec :
- menu
- navigation latérale
- zone centrale
- panneau contextuel
- barre de statut

Pages :
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

L'UI doit être en français.

Le Dashboard doit afficher :
- phase
- readiness gate
- avancement
- budget
- échéancier
- risques
- problèmes
- changements
- livrables
- exigences
- qualité
- actions requises

## DÉMARRAGE

Au premier lancement :
- proposer Nouveau projet
- Ouvrir projet
- Projets récents

Nouveau projet demande :
nom
référence
description
PM
PO
budget
dates
méthodologie PM² v3.1

## PLAN D'IMPLÉMENTATION OBLIGATOIRE

Travaille par étapes et garde le dépôt toujours exécutable.

### Étape 1 — Bootstrap
- pyproject.toml
- structure
- configuration
- logging
- CLI minimale
- application qui démarre
- test de smoke

### Étape 2 — Domain
- toutes les entités
- enums
- invariants
- tests unitaires

### Étape 3 — Database
- SQLAlchemy
- modèles
- repositories
- migration initiale
- tests CRUD

### Étape 4 — Methodology Engine
- loader YAML
- Pydantic models
- PM² config
- tests de chargement

### Étape 5 — Project + Governance
- création projet
- personnes
- rôles
- assignments
- stakeholders
- RCmSCI

### Étape 6 — Lifecycle + Gates
- phases
- RfP
- RfE
- RfC
- workflow engine
- validations

### Étape 7 — Work Plan
- WBS
- tâches
- jalons
- dépendances
- Gantt simple
- budget/effort

### Étape 8 — Requirements + Deliverables + Acceptance
- exigences
- livrables
- critères
- tests
- acceptations
- traçabilité

### Étape 9 — Registers
- risks
- issues
- decisions
- changes
- workflows
- validations

### Étape 10 — Quality + Transition + Implementation
- qualité
- transition
- mise en œuvre organisationnelle
- intégration au Work Plan

### Étape 11 — Documents
- templates
- génération Markdown/HTML
- DOCX
- PDF
- versioning

### Étape 12 — UI complète
- toutes les pages
- dashboard
- filtres
- relations
- validations

### Étape 13 — Project archive
- save .pm2
- open .pm2
- manifest
- integrity checks

### Étape 14 — Tests + packaging
- tests d'intégration
- tests UI critiques
- Ruff
- mypy
- PyInstaller
- README d'installation

## RÈGLES DE DÉVELOPPEMENT

- Ne pas laisser de TODO critique.
- Ne pas utiliser de faux objets ou données mockées dans les workflows finaux.
- Ne pas hardcoder des données PM² dans les widgets.
- Ne pas contourner les services pour écrire directement en base depuis l'UI.
- Ne pas créer une architecture prématurément distribuée.
- Préférer du code simple et lisible.
- Ajouter des tests à chaque étape.
- Après chaque étape, exécuter les tests.
- Corriger les régressions avant de continuer.
- Documenter les décisions techniques importantes.
- Respecter les critères de 11_ACCEPTANCE_CRITERIA.md.

## CRITÈRE FINAL

La V0.1 est terminée uniquement lorsque :
1. l'application démarre ;
2. un projet PM² peut être créé sans JSON/YAML manuel ;
3. le projet peut parcourir les quatre phases ;
4. RfP/RfE/RfC fonctionnent ;
5. les quatre registres fonctionnent ;
6. le Work Plan fonctionne ;
7. les exigences et livrables sont traçables ;
8. les validations PM² fonctionnent ;
9. les artefacts principaux sont générables ;
10. Markdown/HTML/DOCX/PDF/.pm2 fonctionnent ;
11. les tests critiques passent ;
12. aucune dépendance Internet n'est nécessaire à l'exécution.

## LIVRABLES ATTENDUS

À la fin :
- code complet
- migrations
- tests
- templates
- configuration PM²
- README
- guide utilisateur V0.1
- guide développeur
- script de build
- paquet installable si possible

Ne t'arrête pas après avoir créé l'architecture. Implémente réellement chaque étape jusqu'à une V0.1 fonctionnelle.
