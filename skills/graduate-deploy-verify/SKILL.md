---
name: graduate-deploy-verify
description: Verify that public site or data deployments in this repo actually updated the intended GCS object, metadata, cache behavior, and public URL. Use when the user asks to publish or confirm a change to `gs://ntujour-graduate` or any other public asset under this project.
---

# Graduate Deploy Verify

Use this skill when a change needs to be published and checked from the public side. The goal is to confirm that the right object was uploaded and that the public URL serves the expected content.

## When To Use

Use this skill whenever the task involves:

- uploading to GCS
- verifying public pages under `gs://ntujour-graduate`
- checking cache behavior after a publish
- confirming metadata such as content type or cache control
- validating that a remote public URL matches the local artifact

If the task is only local editing, do not use deployment verification yet. First finish the local workflow and only then verify the public state.

## What To Verify

Check these in order:

- the local artifact is the correct version
- the intended object path is known
- only the intended object(s) are uploaded
- metadata matches the expected content type and cache policy
- the public URL serves the new content
- the remote content matches the local artifact

If the deployment is stale, distinguish between a bad upload, a cache issue, and a wrong object path before changing more files.

## Workflow

1. Identify the file or files that should be published.
2. Confirm the canonical local artifact.
3. Upload only the intended object(s).
4. Set or verify metadata if the deployment path depends on it.
5. Open the public URL and compare the result with the local artifact.
6. If the public page is stale, check cache behavior before rebuilding unrelated data.
7. Record the exact object path and verification result.

## Rules

- Do not treat upload success as proof that the public URL changed.
- Do not assume the wrong object path is a cache problem.
- Do not rebuild data until you know the deploy path is correct.
- Do not mix local content errors with remote publish issues.
- Do not stop at the bucket copy; always check the public URL.

## Output

Return a short deploy note with:

- local file or artifact checked
- object path uploaded
- metadata or cache behavior verified
- public URL checked
- whether the remote state matched the local artifact

If the deploy failed, name the failure layer and the first corrective action.
