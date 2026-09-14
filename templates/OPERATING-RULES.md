# Operating rules — how {{PROJECT}} is worked on

A living record of the rules that sessions have learned, each with the day
it was learned and why. Kept here so the next session inherits them; to be
promoted into common-rules' own shared rules later, on the sponsor's word,
not on a session's own initiative. Sponsor rulings are quoted; everything
else is what a session found out the hard way. Add to it; do not rewrite
history out of it.

Seeded {{DATE}} from the common-rules warm-up standard (proposal 19). The
entry shape, shown once here so every later entry can just use it:

> **The rule, stated as a plain instruction.** {{DATE}} — the incident
> that taught it, in a sentence or two: what happened, what it cost, and
> what changed as a result. A rule with no incident behind it is a
> preference, not an operating rule, and belongs somewhere else.

## 1 Proposals and the plan

- **One plan, updated in place.** `{{PLAN_LEDGER}}` is the plan of record.
  Never a new plan document; a revision adds rows and corrects numbers,
  it never scraps old content.
- **Same-turn ledger updates.** After every state change of any item, its
  `status` and `log` are updated and committed in the same turn the state
  changed — never batched for later, never left to memory.
- **Every sponsor message that is not an answer to a question becomes an
  ask row** — its own `A-nn` id, in its own sequence, never reused — in the
  same turn it is said. Research is a lane of its own (an `X-nn` id), and
  an X row is done only when it becomes items (each tagged
  `discovered_from`), a new numbered proposal, or a recorded decline with
  the reason. A research report that nobody acted on stays `in progress`.

## 2 Running work

- **One writer per worktree; explicit file ownership per agent.** An agent
  that needs a change in a file it does not own describes it in its report
  rather than making it.
- **Fast-forward first.** Branch from the integration branch the lead
  names — `origin/main` when there is none — and fast-forward to it
  before the first edit; the lead confirms it again before merging back.
- **Never `git stash`.** The stash is shared across worktrees; two agents
  can swap work through it without either noticing. Set work aside with a
  WIP commit, or show red-first with a saved diff and `git apply -R`.
- **Checkpoint before stopping.** A session that ends without writing
  `docs/handovers/<date>-checkpoint.md` has failed, whatever else it did
  in the same session.

## 3 Merging and shipping

- **{{MERGE_RULE_1}}.**
- **A fix that cannot stand alone is not a reason to batch it with others;**
  it is a sign the fix is not finished yet.
- **The plan's progress figures are measured after merges, never
  estimated:** green is merged with its tests run, amber is in flight or
  owed its wiring, empty is not started.

## 4 The real data

- **{{REAL_DATA_RULE_1}}.**
- **Read-only is encouraged; it is the best evidence available.** A dry
  run against a copy costs nothing and answers most questions.
- **Never install anything into a shared environment.** A measurement that
  needs a package uses a venv in scratch, not the interpreter every
  session shares.
- **Never kill by name.** No `pkill -f`, no `killall` — an explicit PID,
  and only a process this session started.

## 5 Ruflo

- **Ruflo loop mandatory, every item, no exceptions:** `memory search` and
  `hooks route` before starting, `hooks post-task` and `memory store`
  after finishing, and the daemon stopped if this session's own commands
  started it. Never kill it by name.
- Its effect is tracked, per agent and per tier, from the harness's own
  numbers — never from an agent's self-report — so the measurement in
  proposal 19 section F keeps being checked rather than assumed to still
  hold.
- Ruflo's memory database lives in the main checkout only, untracked; an
  agent working from a worktree passes the main checkout as `cwd` to
  `memory search` / `memory store` or the call finds and stores nothing.

## 6 Reporting to the sponsor

- Lead with the outcome; numbers on their own line; nothing certified that
  was not observed — "not observed" is an honest state to report.
- When something needs the sponsor's hands (a grant, a decision, a
  drive), say exactly what and stop there rather than guessing past it.
- The steps list and the one-line repeated status (lead-prompt.md §7) are
  what the sponsor reads while work is running; keep both current rather
  than writing a status paragraph after the fact.

## 7 Other sessions

- **Summaries are paraphrase; the ledger and this file are the record.**
  A compaction summary is written by the model and can be quoted back as
  the sponsor's own words later if nothing catches it — quote a ruling
  from disk (`{{PLAN_LEDGER}}`, this file, an issue), never from a
  summary a session remembers having read.
- **A finding names the path, clone, or database it was taken from,**
  inside the finding itself — "no such commit" is not a finding; "no such
  commit in `{{EXAMPLE_PATH}}`" is, because it invites the correction that
  makes it right.
- Findings about a shared component become that component's own issue and
  are fixed there once, never patched in a copy another session is
  carrying around.

## Superseded

Rules this standard replaces move here, dated, never deleted — a session
reading the current rule above can see why the old one is gone, instead of
independently rediscovering the reason.

> **{{SUPERSEDED_RULE_1}}.** Superseded {{DATE}}: {{SUPERSEDED_REASON_1}}.
