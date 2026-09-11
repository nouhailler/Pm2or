# PM² Desktop — Domain Model V0.1

## 1. Entités fondamentales

### Project
id, reference, name, description, sponsor, business_owner, project_manager, methodology_id, methodology_version, current_phase, status, start_date, target_end_date, actual_end_date, approved_budget, currency.

### Phase
id, project_id, methodology_phase_code, status, started_at, completed_at.

### Person
id, name, email, organisation, function, phone, notes.

### Role
code, name, description, category.

### ProjectRoleAssignment
project_id, person_id, role_code, start_date, end_date, active.

### Stakeholder
id, project_id, person_id/null, name, organisation, function, interest, influence, engagement_level, strategy, status.

### ResponsibilityAssignment
project_id, subject_type, subject_id, role_code, responsibility_type.
Types: R, Cm, S, C, I.
Invariant : pour une même activité/sujet, au plus un R et au plus un Cm.

## 2. Planification

### WbsNode
id, project_id, parent_id, code, name, description, node_type, sequence.

node_type: phase, work_package, task, milestone.

### Task
id, wbs_node_id, owner_person_id, status, planned_start, planned_end, actual_start, actual_end, planned_effort, actual_effort, planned_cost, actual_cost, progress_percent.

### TaskDependency
predecessor_task_id, successor_task_id, dependency_type, lag_days.

### Deliverable
id, project_id, code, name, description, owner, planned_date, actual_date, status, acceptance_status.

### Requirement
id, project_id, code, title, description, source, priority, status, approval_status, verification_method.

Relations : requirement ↔ task, requirement ↔ deliverable, requirement ↔ acceptance test.

## 3. Registres

### Risk
id, project_id, code, title, description, cause, consequence, probability, impact, score, tolerance_status, strategy, owner, due_date, status.

### Issue
id, project_id, code, title, description, impact, priority, owner, due_date, resolution, status.

### Decision
id, project_id, code, title, description, decision_date, decision_owner, outcome, rationale, status.

### ChangeRequest
id, project_id, code, title, description, requester, request_date, priority, reason, status, impact_scope, impact_schedule, impact_cost, impact_quality, recommendation, approver, approval_date.

## 4. Qualité

QualityControl, QualityFinding, QualityAction.
Ils permettent de représenter contrôles, constats/non-conformités, actions correctives et statut.

## 5. Acceptation

AcceptancePlan
AcceptanceCriterion
AcceptanceTest
Acceptance
Relations : Deliverable → Criterion → Test → Acceptance.

## 6. Transition et mise en œuvre

TransitionActivity
ImplementationActivity
Chaque activité peut être reliée à une tâche du Work Plan.

## 7. Réunions et communications

Meeting
MeetingParticipant
MeetingAction
Communication
Report

## 8. Documents

Document
DocumentVersion
DocumentLink

Un Document peut être de type PM²_ARTIFACT, REPORT, MINUTES, EVIDENCE, ATTACHMENT.

## 9. Gates

GateReview
GateChecklistItem
GateDecision

Gates V0.1 : RfP, RfE, RfC.

## 10. Traçabilité
TraceLink :
source_type, source_id, target_type, target_id, relation_type, created_at.

Relations recommandées :
supports, derives_from, impacts, mitigates, resolves, decides, implements, verifies, accepted_by, produces, depends_on, assigned_to, discussed_in, referenced_by.

## 11. Audit
AuditEvent : timestamp, actor, entity_type, entity_id, action, old_value_json, new_value_json.
