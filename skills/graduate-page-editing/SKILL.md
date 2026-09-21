---
name: graduate-page-editing
description: Edit static pages in this repo while preserving source fidelity, stable section anchors, and semantic structure. Use when the user asks to change page copy, layout, or section structure in `*.html` or `style.css`, or when a page needs stable `id` anchors and semantic classes for repeated blocks without changing canonical JSON.
---

# Graduate Page Editing

Use this skill when the task is to update a public page, landing page, or content section without changing the underlying canonical data. The goal is to keep the page maintainable and easy to verify.

## When To Use

Use this skill whenever the task involves:

- editing standalone HTML pages
- changing section structure or layout
- adjusting copy sourced from existing repo content
- updating repeated blocks, cards, or rows on a page
- preserving semantic anchors for later DOM access or regression checks

If the task is actually about data import or canonical JSON, use the canonicalization skill instead. If the task is about admin save behavior, use the admin regression skill instead.

## What To Verify

Check these in order:

- the source content or reference page is known
- standalone content sections have stable, readable `id` values
- repeated blocks have semantic, role-based `class` names, not styling-only hooks
- visible copy stays faithful to the source
- links and assets still resolve
- the page still renders correctly after the edit

## Structure Rules

- Give every independent content section a stable `id` so later DOM access and regression checks can target it directly.
- Give every repeated section, card, row, or block a semantic class that reflects its role in the page.
- Do not rely on styling utility classes alone to identify repeated structures.

## Workflow

1. Identify the page and the content source.
2. Inspect the existing structure and decide which sections need `id` or semantic class updates.
3. Make the smallest possible change that preserves the page's current behavior.
4. Keep the copy source-bound and do not invent missing details.
5. Verify the page renders and that repeated structures are still easy to target.
6. Summarize the edited file, the structure change, and the verification result.

## Rules

- Do not remove stable `id` anchors unless the page structure is being replaced in the same change.
- Do not rely on styling-only classes as the only hook for repeated content blocks.
- Do not leave standalone sections without an `id`.
- Do not invent page content when the source is missing or incomplete.
- Do not change canonical JSON just to fix a page layout problem.
- Do not leave repeated components without a semantic class name.

## Output

Return a short page edit note with:

- the page edited
- the source used
- the sections or repeated blocks that changed
- whether the page still renders cleanly

If the task is blocked, name the missing source or structure mismatch that prevented the edit.
