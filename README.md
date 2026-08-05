# common-rules

Workflow rules shared across every project under `/Users/aashish/apps/`,
kept in one place instead of duplicated into each project's `CLAUDE.md`.

**This folder is its own git repository, deliberately separate from every
project's.** `apps/` itself is not a repo — each project underneath it
(`finance-tracker/`, `pockets/`, etc.) is independent, and this folder sits
outside all of them on purpose, so these rules aren't tied to any single
project's history or branch. That separation is the point and hasn't
changed; what changed on 2026-08-03 is that the folder gained a repo of its
own (`codeDEXTER/ai-common-rules`, private) rather than having no version
control at all.

`CHANGELOG.md` remains the human-readable record of *why* each rule changed,
and stays the thing to read first — `git log` records that a change
happened, the changelog records what it was for.

## Files

- **`agents/`** — the eight specialist agent definitions
  (`research-agent`, `design-explorer`, `requirements-engineer`,
  `design-engineer`, `proposal-auditor`, `code-engineer`,
  `test-engineer`, `quality-manager`). **`~/.claude/agents` is a symlink to this
  directory**, which is where Claude Code actually loads agent
  definitions from — so editing a file here is editing the live agent,
  and the definitions get the same version history as the rules that
  govern them. Two things to know: they are machine-global (any session
  on this Mac can invoke them, not just ones under `apps/`), and they
  **register at session start**, so a definition added or changed
  mid-session doesn't take effect until a new one.
- **`CLAUDE-workflow.md`** — the actual rules: git worktree-per-task, the
  pre-merge checklist shape, issue tracking (checklist file as source of
  truth, GitHub issues as a one-way mirror), and the issue lifecycle (the
  user is project manager and decides creation/scope/priority/picking/
  closing; the AI researches, builds, reviews, and tests within that).
- **`bin/rulecheck`** — answers "is this project on the current rules?"
  before any work starts, and prints *what changed* if not. The rules move
  several times a day, so a session working from what it read last week is
  following a version that no longer exists. A project records the version
  it last aligned with in `.common-rules-version` at its root, committed
  like any other record. Best wired to a `SessionStart` hook per project
  (`rulecheck --quiet`) so nobody has to remember.
- **`bin/pulse`** — where you see the autopilot running: one page with every
  project's features and their open issues (grouped by title prefix), each
  worktree with its ahead/uncommitted state and how fresh its session is,
  running app instances, and rules alignment. A derived snapshot, honest about
  when it was taken; re-run to refresh. `docs/pulse.html`.
- **`bin/whoelse`** — who else is working in this project, and do we collide?
  Reads `git worktree list`, a `git status` in each, and whether any of it is
  ahead of `main` — the three places that already knew and nobody consulted.
  Overlap is a stop, not a warning. `--contested` gives the batch view for
  sequencing issues before sessions are opened.
- **`bin/apprun`** — the run registry. It exists because one rule in `CLAUDE-workflow.md` ("stop only what you
  started") is unfollowable without a fact no agent otherwise has: who
  started a given instance. It keeps `~/.claude/app-runs.jsonl`, keyed on
  `CLAUDE_CODE_SESSION_ID`, so ownership is checked rather than assumed —
  `stop` declines a live stranger's copy, an orphan, and the stable copy,
  each with its reason. It also closes the browser window, which stopping
  the process does not. Stdlib Python 3 only, no dependencies.
  `apprun sweep` reports orphans from dead sessions and says outright when
  no clean copy is running. A copy started with `--demo` — one the *user*
  is looking at — survives a blanket `stop --all` and says so.
- **`ASKS.md`** — an append-only log of what the user has asked for about
  *how work is done* (not what to build), and the patterns found in it.
  Sessions add to it; when entries rhyme, the pattern is proposed as a rule
  or, more often, as an amendment to one that didn't reach far enough.
  Adding an entry is not a rule change and needs no PR.
- **`CHANGELOG.md`** — every change made to the files in this folder,
  documented in plain language.

## How a project adopts this

Add a short pointer near the top of the project's own `CLAUDE.md`:

> Shared workflow rules (git worktree-per-task, pre-merge checklist, issue
> tracking, confirmation gates): `../common-rules/CLAUDE-workflow.md` —
> read that first. This project's specifics for it: test command is
> `<...>`, build/run is `<...>`, GitHub repo is `<owner/repo>`.

Then keep only the project's own specifics in its `CLAUDE.md` — the exact
test/build commands, its repo name, its label taxonomy, any gitignored
files a fresh worktree needs copied in, and anything else genuinely
specific to that project. Don't copy `CLAUDE-workflow.md`'s text inline;
that defeats the point of sharing it.

## Editing these rules

**Reserved for the user, same as the issue lifecycle rules inside
`CLAUDE-workflow.md` itself.** The AI does not edit any file in this
folder on its own initiative — not to fix a typo, not because it noticed
a stale note or a gotcha worth recording. It surfaces what it noticed and
asks; a change only happens once the user has explicitly directed it in
that conversation. The reason the bar is higher here than for an ordinary
project file: if a rule here changes, every adopting project benefits (or
is affected) automatically — that's the reason this folder exists, but it
also means an unprompted change here silently changes behavior everywhere
at once, not just in the one project a session happens to be in.

When the user does direct a change: add a `CHANGELOG.md` entry here
explaining why, and if it actually affects behavior for an
already-adopted project (not just wording), mention that to the user —
worth a one-line heads-up next time you're working in that project too.
