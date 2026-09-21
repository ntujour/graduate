---
name: graduate-admin-regression-check
description: Verify that admin UI changes in this repo still load, edit, save, and persist correctly. Use when the user mentions `course_admin.html`, `course_admin.py`, `cloudrun_admin.py`, IAP/login behavior, or any browser-based save path for course or advisee data.
---

# Graduate Admin Regression Check

Use this skill when the task is to confirm that the admin UI still works end to end after a data or backend change. The goal is to check real persistence, not just that the screen renders.

## When To Use

Use this skill whenever the task involves:

- `course_admin.html`
- `course_admin.py`
- `cloudrun_admin.py`
- browser-based edit/save flows
- IAP or login behavior for the admin service
- confirming that edits land in canonical JSON

If the task is only about static content or public page layout, use a page-editing workflow instead. If the task is only about JSON conversion, use the canonicalization workflow instead.

## What To Verify

Check these in order:

- the admin UI loads successfully
- the relevant tab or form is reachable
- an edit can be made without client-side errors
- the save action completes
- the saved data persists after reload
- the canonical JSON is updated, not just a temporary UI state
- backup behavior occurs when overwrite logic applies

If the task is blocked by IAP or auth, report that clearly and do not treat the failure as a data bug until auth is confirmed.

## Workflow

1. Identify the admin surface and the canonical file it writes.
2. Open the UI and verify the target page or tab is available.
3. Make a minimal, representative edit.
4. Save the change and confirm the request succeeds.
5. Reload the page or refetch the data to confirm persistence.
6. Inspect the canonical JSON or API response to ensure the change landed.
7. If the save path is supposed to create a backup, verify that the backup exists.
8. Summarize the result as pass, fail, or blocked.

## Rules

- Do not accept a successful toast or button state as proof of persistence.
- Do not skip the reload step.
- Do not mix auth failures with schema failures.
- Do not assume the browser session reflects the canonical data store.
- Do not report the flow as healthy until the saved data is visible after refresh.

## Output

Return a short regression note with:

- admin surface tested
- edit attempted
- save result
- persistence result
- whether auth/IAP blocked the test

If something failed, name the failure layer and the likely next check.
