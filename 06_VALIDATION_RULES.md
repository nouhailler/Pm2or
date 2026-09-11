# PM² Desktop — Validation Rules V0.1

Rules have severity ERROR, WARNING or INFO.

## Project
ERROR: project name and reference required.
ERROR: methodology required.
WARNING: no project manager assigned.

## Governance
ERROR: at least one PM assignment.
ERROR: at most one active person can be assigned as PM.
WARNING: no PSC.
WARNING: no PO.

## Responsibilities
ERROR: a subject cannot have more than one R.
ERROR: a subject cannot have more than one Cm.
WARNING: actionable subject without R.

## Requirements
ERROR: approved requirement must have source and priority.
WARNING: approved requirement without verification method.
ERROR: requirement marked VERIFIED must have at least one verification/acceptance test.

## Deliverables
ERROR: deliverable without owner.
WARNING: deliverable without planned date.
ERROR: deliverable marked ACCEPTED without acceptance record.
WARNING: deliverable without acceptance criterion.

## Tasks
ERROR: task end before start.
ERROR: progress outside 0..100.
WARNING: completed task without actual dates.
WARNING: task without owner.
WARNING: task without linked deliverable when the project configuration requires deliverable traceability.

## Risks
ERROR: probability and impact required before assessment.
ERROR: score must equal configured probability × impact scale or methodology-defined matrix.
WARNING: high/critical risk without response strategy and owner.
WARNING: risk beyond tolerance without escalation.

## Issues
ERROR: issue cannot be CLOSED without resolution.
WARNING: overdue open issue.

## Changes
ERROR: approved change must contain impact analysis.
ERROR: IMPLEMENTING change requires APPROVED status.
WARNING: change affecting budget without cost impact.
WARNING: change affecting schedule without schedule impact.
WARNING: high-impact change without decision record.

## Acceptance
ERROR: acceptance cannot be final without criteria.
ERROR: acceptance test requires expected result and outcome.
WARNING: failed test on accepted deliverable.

## Quality
WARNING: finding without corrective action when severity requires one.
ERROR: quality action cannot be CLOSED without evidence when evidence is required.

## Gates
ERROR: any unmet mandatory checklist item blocks approval.
WARNING: unresolved non-mandatory item.
INFO: gate approved with reserves.

## Traceability
WARNING: orphan risk, issue, change, decision or requirement.
WARNING: deliverable without linked task.
INFO: orphan document.
