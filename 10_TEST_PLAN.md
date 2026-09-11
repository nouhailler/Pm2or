# PM² Desktop — Test Plan V0.1

## Unit tests
- Domain invariants.
- Workflow transitions.
- Gate rules.
- RCmSCI uniqueness.
- Risk scoring.
- Change impact.
- Acceptance.
- Date/cost/progress validation.
- Trace links.

## Repository tests
- CRUD for every entity.
- Foreign key behavior.
- Transaction rollback.
- Project archive save/load.

## Service tests
- Project creation.
- Phase transitions.
- Gate evaluation.
- Register workflows.
- Document generation.
- Validation aggregation.
- Audit events.

## UI tests
Use pytest-qt where practical.
- Create project.
- Navigate phases.
- Create stakeholder.
- Create WBS/task.
- Create risk.
- Create issue.
- Create decision.
- Submit change.
- Evaluate gate.
- Generate artifact.

## Integration scenarios
1. Create project → Launch → RfP.
2. Plan project → RfE.
3. Execute deliverables → accept → RfC.
4. Close project → final report.
5. Change affecting cost/schedule creates required impact fields.
6. High risk beyond tolerance creates warning/escalation.
7. Requirement linked to deliverable and acceptance test reaches ACCEPTED.
8. Export and reopen .pm2 archive.

## Quality gate
Target:
- all critical tests passing
- no unhandled exceptions in primary workflows
- Ruff clean
- mypy clean for application/domain code
- migrations reproducible
