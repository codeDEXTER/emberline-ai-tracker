# Repository structure

The repository is intentionally split between public explanation, operational
runtime, and durable evidence. The visible root is small by design for a
shared-rules repository; moving contract files only to make the root look
quieter would make adoption and tooling less reliable.

## What belongs at the root

| Path | Why it stays visible |
| --- | --- |
| `README.md` | GitHub's primary project introduction and search-facing entry point |
| `LICENSE`, `LICENSE-DOCS`, `NOTICE` | Standard public licensing and attribution discovery |
| `CLAUDE.md`, `HANDOFF.md`, `CLAUDE-workflow.md` | Startup and shared workflow contracts referenced by tools and adopters |
| `.common-rules.json` | Machine-readable project declaration and gates |
| `VERSION`, `CHANGELOG.md` | Release source and version gate |
| `bin/`, `tools/`, `hooks/` | Executable workflow surface used by adopters and CI |
| `.github/workflows/` | GitHub Actions' conventional and automatically discovered location |

## What belongs under `docs/`

- `user-guide/` explains the product for people.
- `proposals/` contains the decision ledgers and generated tracker.
- `handovers/` contains checkpoints used by the workflow.
- `research/` contains evidence cited by proposal history.
- public HTML pages and assets support the visual introduction.

## Hidden runtime directories

`.claude/` and `.agents/` contain host-specific skills and settings. They are
hidden in normal file browsers and are intentionally separate because Claude
Code and Codex use different installation surfaces.

## What not to add

Do not commit session snapshots, editor state, generated caches, local machine
paths, credentials, or exploratory assets that are not referenced by a public
page or workflow. The repository ignores known machine-local state; check
`git status` before committing.
