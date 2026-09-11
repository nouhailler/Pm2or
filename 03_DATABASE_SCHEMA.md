# PM² Desktop — SQLite Schema V0.1

Toutes les tables ont un UUID TEXT comme clé primaire, sauf les tables de configuration statique pouvant utiliser un code TEXT.

## Tables
projects
phases
persons
roles
project_role_assignments
stakeholders
responsibility_assignments
wbs_nodes
tasks
task_dependencies
deliverables
requirements
requirement_tasks
requirement_deliverables
risks
risk_actions
issues
issue_actions
decisions
changes
change_impacts
change_approvals
quality_controls
quality_findings
quality_actions
acceptance_plans
acceptance_criteria
acceptance_tests
acceptances
transition_activities
implementation_activities
meetings
meeting_participants
meeting_actions
communications
reports
documents
document_versions
document_links
gate_reviews
gate_checklist_items
gate_decisions
trace_links
lessons_learned
recommendations
audit_events
settings

## Contraintes
- Foreign keys activées.
- Suppression en cascade uniquement pour les enfants strictement dépendants.
- Les objets métier ne doivent pas être supprimés physiquement lorsqu'ils sont référencés : préférer archived/deleted_at.
- UNIQUE(project_id, code) pour les codes métier des registres.
- CHECK progress_percent BETWEEN 0 AND 100.
- Dates cohérentes : actual_end >= actual_start ; planned_end >= planned_start.
- Change approval obligatoire avant passage à IMPLEMENTING.
- Acceptance finale impossible sans critères applicables.
- Un seul R et un seul Cm par sujet.

## Index
Créer des index sur :
project_id
status
code
owner
planned_start
planned_end
risk score
gate status
document type
trace source/target

## Migration
Alembic obligatoire. Première migration crée le schéma complet.
