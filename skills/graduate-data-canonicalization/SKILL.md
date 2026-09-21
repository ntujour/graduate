---
name: graduate-data-canonicalization
description: Normalize imported course, advisee, or activity data into this repo's canonical JSON. Use when the user asks to sync Google Sheets, CSV, or Word data into `data/courses.json`, `data/advisees.json`, or `data/regular_event.json`, when a source-of-truth question comes up, or when a field change may affect downstream loaders such as `courses-data.js` or `advisees-data.js`.
---

# Graduate Data Canonicalization

Use this skill to keep the repository's data model coherent. The goal is not just to transform input files into JSON, but to preserve the canonical/import-source boundary and avoid silent breakage in pages that read the JSON.

## When To Use

Use this skill whenever the task involves:

- converting Google Sheets, CSV, or Word data into canonical JSON
- deciding whether a file is formal data or import-only source
- changing a field that may affect page loaders or admin tools
- reconciling local CSV/Word input with existing canonical JSON
- verifying that backups are created before overwriting canonical data

If the request is about editing page copy only, use a page-editing workflow instead. If the request is about browser save/persistence behavior, use the admin regression workflow instead.

## Canonical Sources

Treat these as canonical:

- `data/courses.json`
- `data/advisees.json`
- `data/regular_event.json`

Treat these as import-only unless the task explicitly says otherwise:

- Google Sheets CSV exports
- local CSV files
- Word documents

## Inputs To Inspect First

Before changing any data, inspect:

- the canonical JSON file
- the script that produces or updates it
- the page loaders that consume it
- any admin UI or API path that writes it back

For this repo, the most common consumers are:

- `courses-data.js`
- `advisees-data.js`
- `course_admin.py`
- `cloudrun_admin.py`
- `courses.html`
- `courseplan.html`
- `advisee.html`
- `advisee_faculty.html`

## Workflow

1. Identify the canonical file and the import source.
2. Confirm the field mapping and any renamed or deprecated fields.
3. Check downstream consumers for schema assumptions before editing.
4. Make the smallest possible transformation that preserves meaning.
5. Preserve `source` as the canonical origin and `importSource` as the upstream import reference when the file format supports both.
6. If overwriting canonical JSON, verify that the backup path is created first.
7. Validate that the page loaders still render and that the JSON parses cleanly.
8. If the task includes deployment, hand off to the deploy verification workflow after local validation passes.

## Rules

- Do not treat import sources as canonical just because they are easier to edit.
- Do not change schema fields without checking the consumers first.
- Do not remove legacy compatibility fields unless the page loaders and admin tools have been updated in the same change.
- Do not claim the data is fixed until the canonical JSON and its consumers agree.
- Do not skip backup verification when canonical JSON is overwritten.

## Checks

Use the following checks as the default acceptance criteria:

- JSON parses successfully.
- Required fields are still present.
- Canonical `source` / import `importSource` semantics are preserved.
- Relevant page loaders still render without errors.
- Admin write paths still target the canonical JSON.
- Backup files exist when overwrite behavior is involved.
- If the task mentions a source/import source boundary, state it explicitly in the result rather than implying it.

## Output

Return one of these outcomes:

- updated canonical JSON with a short summary of what changed
- a blocked report explaining the schema mismatch or missing source
- a verification report stating that canonical JSON, consumers, and backup behavior are consistent

Keep the report short and concrete. Name the canonical file, the import source, and the consumer files you checked.
