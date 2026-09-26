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
attachments
document_links
baselines
gate_reviews
gate_checklist_items
gate_decisions
trace_links
lessons_learned
recommendations
audit_events
settings

## Contraintes
- `projects` fige `methodology_id`, `methodology_version`, `methodology_hash` et `methodology_snapshot` à sa création.
- Foreign keys activées.
- Suppression en cascade uniquement pour les enfants strictement dépendants.
- Les objets métier ne doivent pas être supprimés physiquement lorsqu'ils sont référencés : préférer archived/deleted_at.
- UNIQUE(project_id, code) pour les codes métier des registres.
- CHECK progress_percent BETWEEN 0 AND 100.
- Dates cohérentes : actual_end >= actual_start ; planned_end >= planned_start.
- Change approval obligatoire avant passage à IMPLEMENTING.
- Acceptance finale impossible sans critères applicables.
- Un seul R et un seul Cm par sujet.
- Les snapshots de `baselines` sont append-only : aucun UPDATE ou DELETE n'est permis ; seule l'approbation initiale peut compléter `approved_at` et `approved_by`.

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

La migration `0002` ajoute le hash et le snapshot méthodologique aux anciennes bases. Leur complétion ne peut être inférée que pour une identité/version identique à celle installée, avec audit explicite. La migration `0003` ajoute les pièces jointes stockées en base avec leur taille, leur type et leur empreinte SHA-256. La migration `0004` ajoute les baselines et leurs triggers d'immuabilité. Avant toute migration d'une base existante, l'application crée une sauvegarde horodatée `.pre-migration-*.bak`.
