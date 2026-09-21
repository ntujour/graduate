# Lightweight Harness Plan for AGENTS.md and Project Skills

## Goal

Align this repository's working conventions with a lightweight Harness Engineering model so the agent can handle multi-step work more reliably across content edits, JSON administration, browser-based verification, and deployment without turning the repo into a general-purpose agent platform.

## Why Harness Here

This repository is no longer just a static site. It has:

- public static pages
- canonical JSON data used by public pages
- import-only sources from Google Sheets, CSV, and Word
- admin UI and Cloud Run write paths
- IAP/auth boundaries
- GCS deployment and cache behavior
- backup and rollback concerns

That combination makes maintenance errors more likely to come from state confusion and incomplete verification than from difficult code alone.

## Decision

Use Harness Engineering for this repo, but keep it repo-specific and lightweight.

Do:

- define task classes
- enforce source-of-truth rules
- standardize verification loops
- standardize rollback and recovery
- create a small number of reusable skills for repeated workflows

Do not:

- build a generic orchestration framework
- add abstract agent concepts that do not map to this repo's real workflows
- over-invest in evaluation infrastructure before the core workflows stabilize

## Current Gap

The current `AGENTS.md` is strong on project overview, deployment links, data sources, and page inventory. It is still missing explicit harness-level guidance for:

1. Memory and task state management
2. Tool selection and tool failure handling
3. Planning and execution loops
4. Evaluation and acceptance checks
5. Constraints, rollback, and recovery rules

## Design Principle

Treat `AGENTS.md` as the repository's operational harness spec, and treat project skills as reusable execution modules for the highest-frequency workflows.

## Non-Goals

This plan does not try to:

- replace normal repo documentation
- automate every deployment or recovery path
- introduce mandatory subagents, complex memory stores, or generalized planners
- benchmark skills at large scale before they prove useful in day-to-day work

## Proposed AGENTS.md Changes

### 1. Add a `Harness Operating Model` section

Purpose: define how work is classified before execution.

Add task classes:

- `content-edit`: static page copy/layout/content updates
- `data-sync`: CSV/Word/Google Sheet to canonical JSON refresh
- `admin-ui`: `course_admin.html` / Cloud Run admin behaviors
- `deploy`: GCS upload, cache headers, public URL verification
- `incident-recovery`: bad JSON, broken deploy, stale public asset, failed save

For each task class, define:

- source of truth
- expected outputs
- required verification step
- rollback source

### 2. Add a `Memory and State` section

Purpose: reduce context loss across long tasks.

Add rules:

- At task start, restate task class, source of truth, target files, and target environment.
- Distinguish canonical data from import-only data:
  - canonical: `data/courses.json`, `data/advisees.json`, `data/regular_event.json`
  - import-only: Google Sheets CSV, Word files, local CSV inputs
- When a task spans multiple steps, maintain a short state record in responses:
  - `goal`
  - `current step`
  - `verification pending`
  - `rollback path`
- If work remains unfinished, record it in `AGENTS.md` Pending Tasks and `LOG.md`.

### 3. Add a `Tool Use Policy` section

Purpose: constrain tool choice and error handling.

Preferred tool order:

1. Read local files first
2. Use browser only for behavior that cannot be confirmed statically
3. Use networked deploy actions only after local verification passes
4. Treat production upload as a separate step from local editing

Add concrete rules:

- For data work, inspect JSON schema consumers before changing fields.
- For admin work, verify both frontend behavior and backend persistence path.
- For deploy work, verify object path, content type, and cache headers.
- When a tool fails, classify the failure as `auth`, `network`, `schema`, `render`, or `deploy` before retrying.
- Do not loop blindly on remote failures; record blocking condition and fallback.

### 4. Add an `Execution Loop` section

Purpose: make multi-step work stable and repeatable.

Standard loop:

1. Identify task class
2. Confirm source of truth and downstream consumers
3. Inspect target files and adjacent dependencies
4. Make smallest coherent change
5. Run local/static verification
6. Run browser verification if UI behavior changed
7. Deploy only if the task includes release
8. Re-check public/admin endpoint
9. Record result in `LOG.md`

### 5. Add an `Evaluation Checklist` section

Purpose: prevent self-reported success without evidence.

Per task class:

- `content-edit`
  - visual structure preserved
  - text matches requested source
  - no broken links/assets
- `data-sync`
  - JSON parses
  - required fields preserved
  - page loaders still render
  - `source` and `importSource` semantics remain correct
- `admin-ui`
  - load succeeds
  - edit succeeds
  - save succeeds
  - backup is created when overwrite occurs
- `deploy`
  - target object uploaded
  - metadata correct
  - cache behavior acceptable
  - public URL reflects new content
- `incident-recovery`
  - failure reproduced or isolated
  - fallback path identified
  - restore source confirmed

### 6. Add a `Recovery and Rollback` section

Purpose: define how to recover from predictable failures.

Add rules:

- Before overwriting canonical JSON, rely on `backup/` copy creation and verify backup path.
- If public deploy looks wrong but local files are correct, treat deploy state separately from content state.
- For stale public pages, inspect cache headers before rebuilding data.
- For broken admin saves, verify IAP/auth state separately from JSON write logic.
- If a deploy or remote write fails, stop after bounded retries and document manual fallback.

## Proposed Skill Set

Start with three core skills only. Defer all optional skills until these three are in active use and clearly reduce error rate or operator time.

### Core Skill 1: `graduate-data-canonicalization`

When to use:

- user asks to sync Google Sheets, CSV, or Word data into canonical JSON
- user asks which file is the formal source of truth
- a field change may affect `courses-data.js` or `advisees-data.js`

Responsibilities:

- inspect import source and canonical JSON
- preserve `source` vs `importSource`
- validate downstream consumers
- verify backup behavior when overwrite path is involved

Outputs:

- updated JSON or a blocked report with schema mismatch details

### Core Skill 2: `graduate-admin-regression-check`

When to use:

- user asks to verify admin behavior
- changes touch `course_admin.html`, `course_admin.py`, or `cloudrun_admin.py`
- browser-based persistence needs confirmation

Responsibilities:

- open admin UI
- check load, edit, save, and post-save reload
- verify whether the change persisted to JSON
- note whether IAP/auth blocked the run

Outputs:

- short regression report with pass/fail for load, edit, save, persistence

### Core Skill 3: `graduate-deploy-verify`

When to use:

- user asks to publish or confirm a public page/data update
- a task touches GCS-hosted public assets

Responsibilities:

- verify local target artifact
- upload only the intended objects
- verify public URL content
- verify content type and cache headers

Outputs:

- deploy checklist with local artifact, uploaded object, public URL evidence

## Skills Deferred for Now

These may become skills later, but they should not be part of the first rollout:

- page editing skill for static content/layout tasks
- incident recovery skill for deploy/auth/data failures

Reason:

- both workflows still benefit more from better `AGENTS.md` constraints than from early specialization
- if created too early, they risk encoding unstable procedures

## Suggested Rollout

### Phase 1. Minimum viable harness in `AGENTS.md`

- add `Harness Operating Model`
- add `Memory and State`
- add `Tool Use Policy`
- add `Execution Loop`
- add `Evaluation Checklist`
- add `Recovery and Rollback`

Deliverable:

- updated `AGENTS.md`

Success condition:

- the repo has a clear answer for task classification, source of truth, verification, and rollback without reading multiple files

### Phase 2. Core skill drafts

- draft `graduate-data-canonicalization`
- draft `graduate-admin-regression-check`
- draft `graduate-deploy-verify`

Deliverable:

- three `SKILL.md` drafts with trigger descriptions and workflow steps

Success condition:

- each skill corresponds to a repeated workflow already present in this repo
- each skill has a clear trigger boundary and a concrete output

### Phase 3. Lightweight validation only

- prepare 2 to 3 realistic prompts per core skill
- define simple pass/fail checks for each prompt
- avoid heavy benchmark infrastructure unless the skill is reused enough to justify it

Deliverable:

- lightweight skill trial set

### Phase 4. Trial and tighten

- use the new AGENTS rules on one content task, one admin task, and one deploy task
- use at least one core skill on a real task before expanding the skill set
- identify missing constraints or over-specific instructions

Deliverable:

- revised `AGENTS.md` and refined skills

## Recommended Next Step

Implement Phase 1 first. Without the `AGENTS.md` harness rules, individual skills will drift because they will not share a common task model, verification standard, or recovery policy.

## Immediate Priority Order

1. Update `AGENTS.md` with the minimum viable harness sections.
2. Draft `graduate-data-canonicalization` first, because source-of-truth mistakes are the highest recurring risk.
3. Draft `graduate-admin-regression-check` second, because browser-visible success can diverge from JSON persistence.
4. Draft `graduate-deploy-verify` third, because deploy errors should be checked after local and admin workflows are stable.
