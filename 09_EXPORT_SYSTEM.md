# PM² Desktop — Export System V0.1

## Supported exports
- Markdown
- HTML
- DOCX
- PDF
- Project archive .pm2

## Export service
ExportService.generate_artifact(project_id, artifact_code, format)
ExportService.generate_project_bundle(project_id, formats)

## PDF
Prefer ReportLab Platypus for deterministic offline PDF generation.

## DOCX
Use python-docx with styles:
Title, Heading 1, Heading 2, Heading 3, Table Grid, Caption.

## HTML
Jinja2 templates + local CSS. No external assets required.

## Markdown
Stable headings, tables and identifiers suitable for version control.

## Bundle
A complete project export contains:
- all selected PM² artifacts
- registers
- supporting documents
- manifest
- frozen methodology YAML (`methodology/PM2_METHODOLOGY.yaml`) and SHA-256
- export report
- validation report

## Validation before export
- Run ValidationService.
- Include ERROR/WARNING summary.
- User can export despite warnings.
- ERROR does not block ordinary export, but gate/approval artifacts must show unresolved errors.

## Determinism
Same database state + same template version should produce materially identical output.

Archive format 1.1 verifies consistency between the methodology file, manifest and database snapshot before opening. Legacy 1.0 archives remain readable; missing snapshots follow the explicit historical compatibility policy.
