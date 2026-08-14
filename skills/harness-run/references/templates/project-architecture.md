# Project Architecture Snapshot

Run ID: `{{RUN_ID}}`
Updated: `{{UPDATED_AT}}`
Repo: `{{REPO}}`

This is a run-local architecture snapshot. It does not replace target repo architecture docs.

## Source Evidence

Root evidence:

{{ROOT_EVIDENCE}}

Docs evidence:

{{DOCS_EVIDENCE}}

Top-level directories:

{{TOP_DIRS}}

## Runtime Topology

- entry points:
- app/service/CLI shape:
- background workers:
- external dependencies:
- local state:

## Module Boundaries

| Path | Responsibility | Allowed Dependencies | Risk |
| --- | --- | --- | --- |
| | | | |

## Commands

- install:
- build:
- test:
- lint:
- run:

## Unknowns

- Items here must be verified from source, logs, tests, or official docs before being treated as facts.

## Refresh Policy

- Refresh when source structure, entry points, data flow, or validation commands change.
- Do not rewrite from memory.
