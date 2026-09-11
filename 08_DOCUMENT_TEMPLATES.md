# PM² Desktop — Document Templates V0.1

All templates are generated from structured project data and must expose version/date/status metadata.

## Templates
1. Project Initiation Request
2. Business Case / Opportunity Study
3. Project Charter
4. Project Handbook
5. Stakeholder Matrix
6. Work Plan
7. Outsourcing Plan
8. Deliverables Acceptance Plan
9. Transition Plan
10. Organisational Implementation Plan
11. Requirements Management Plan
12. Change Management Plan
13. Risk Management Plan
14. Issue Management Plan
15. Quality Management Plan
16. Communications Management Plan
17. Meeting Minutes
18. Project Report
19. Quality Report
20. Project End Report
21. Lessons Learned

## Rendering model
Jinja2 is used for Markdown/HTML templates.
DOCX is rendered from structured sections using python-docx.
PDF is rendered from HTML or ReportLab templates.

## Standard metadata
Project
Document title
Artifact code
Version
Status
Author
Reviewer
Approver
Creation date
Last modified
Approval date

## Important
Templates must not duplicate business data manually. Sections should reference current entities and registers. A generated artifact must state its generation timestamp and project baseline/version.
