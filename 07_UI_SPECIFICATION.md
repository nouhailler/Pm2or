# PM² Desktop — UI Specification V0.1

## Main window
- Menu: File, Project, View, Tools, Help.
- Left navigation tree.
- Central stacked pages.
- Right contextual panel for properties/actions.
- Bottom status bar with project, phase, validation count.

## Dashboard
Cards:
Phase, gate readiness, progress, budget, schedule variance, open risks, open issues, pending changes, deliverables, requirements, quality.
Section "Actions requises".
Timeline with phases and gates.

## Project
Tabs:
Overview
Objectives
Scope
Constraints
Budget
Milestones

## Governance
Tabs:
Team
Roles
Stakeholders
RCmSCI/RAM
Governance decisions

## Launch
Wizard:
Initiation Request
Business Case
Project Charter
RfP

Each wizard saves structured fields, displays completion %, validation messages and links to source entities.

## Planning
Tabs:
Handbook
Work Plan
WBS
Gantt
Stakeholders
Requirements
Acceptance
Transition
Organisational Implementation
Outsourcing
Management Plans
RfE

## Execution
Tabs:
Tasks
Deliverables
Meetings
Reports
Quality

## Monitoring & Control
Tabs:
Performance
Schedule
Costs
Requirements
Changes
Risks
Issues
Decisions
Quality
Acceptance
Transition
Implementation

## Registers
Each register supports:
table view, filters, search, create/edit dialog, status transitions, export, linked entities, audit history.

## Closing
Wizard:
RFC
Final acceptance
Lessons learned
Final report
Administrative closure

## Documents
- Artifact list by phase
- status/version
- generate
- preview
- export
- open containing folder
- history

## UX requirements
- French UI.
- Keyboard navigation.
- Undo for safe local edits where practical.
- Confirmation for destructive actions.
- No blocking modal for routine validation.
- Validation displayed inline and in dashboard.
- Tables support sort/filter.
- Every entity detail page includes "Relations / Traçabilité".

## Accessibility
- Qt standard keyboard navigation.
- Labels for controls.
- Avoid color-only status indication.
