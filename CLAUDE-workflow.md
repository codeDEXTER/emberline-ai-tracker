# Shared workflow rules — git worktree-per-task, issue tracking, issue lifecycle

This file is common to every project under `/Users/the-sponsor/apps/` — it does
not belong to any single repo (`apps/` itself is not a git repository, on
purpose, so this folder sits outside all of them). A project's own
`CLAUDE.md` should **point here near the top and layer its own specifics on
top** (exact test/build commands, its GitHub repo name, its label taxonomy)
rather than copying this text inline — the point of a shared file is that a
future change here doesn't have to be hunted down and re-pasted into every
project's `CLAUDE.md` by hand.

A project adopts this file by adding a line near the top of its own
`CLAUDE.md`, e.g.:

> Shared workflow rules (git worktree-per-task, pre-merge checklist, issue
> tracking, issue lifecycle): `../common-rules/CLAUDE-workflow.md` — read
> that first. This project's specifics for it: test command is `<...>`,
> build/run is `<...>`, GitHub repo is `<owner/repo>`.

Adopted so far: **finance-tracker** (2026-08-02), **pockets** (2026-08-02).

---

## Check you are on the current rules — before doing anything else

Added 2026-08-04. These rules change several times a day. A session working
from what it read last week is following a version that **no longer exists**,
and nothing tells it so — which is why the user kept having to say "check
common rules" again. That instruction should not have to be given.

**First action in any session on an adopting project, before reading code,
before `EnterWorktree`, before anything:**

```bash
/Users/the-sponsor/apps/common-rules/bin/rulecheck
```

It compares the project's recorded version against the current one and prints
**what changed** — the changelog lines added in between — not merely that
something did. Exit 0 aligned, 1 behind, 2 cannot tell.

If it reports behind: **read the sections those changes touch, then**

```bash
/Users/the-sponsor/apps/common-rules/bin/rulecheck --align
```

Align only after actually reading. `--align` is a claim that this session knows
the current rules, and a false claim there is worse than no stamp at all — the
next session inherits it and skips the check.

**Where the version lives.** `<commit-count>-<short-sha>` of this repo; the
count orders it, the sha identifies it exactly. Each project records the one it
last aligned with in `.common-rules-version` at its root, **committed** like any
other record — so a worktree checkout carries it automatically and needs no
stamp of its own.

**Cannot tell (exit 2) is not "probably fine".** An unreadable rules repo or a
recorded commit that doesn't exist means re-read the rules in full. The whole
point is to stop guessing about this.

**Make it automatic per project.** The rule above still relies on a session
remembering, which is the weakness the rule exists to remove. A project can
close that with a `SessionStart` hook in its `.claude/settings.json`, so the
answer is in context before the session's first thought:

```json
{ "hooks": { "SessionStart": [ { "hooks": [ { "type": "command",
  "command": "/Users/the-sponsor/apps/common-rules/bin/rulecheck --quiet" } ] } ] } }
```

`--quiet` says nothing when aligned, so a current project pays no attention cost
and a stale one cannot be missed.

---

## Git workflow — every chat gets its own branch and folder, always

**No direct-to-main work, and no two chats sharing a working directory.**
`main` is the stable branch — for a project with a built/installed app,
that's what the installed copy actually runs, so a broken `main` is a
broken app on this machine, not just a red CI check. Separately: a project
under `apps/` gets worked on from more than one chat session, sometimes at
the same time, and two sessions editing the same checkout is how one
silently overwrites the other's in-progress work. Both problems share one
fix:

1. **The first action any chat takes on a project — before reading,
   editing, or running anything else — is `EnterWorktree` with `name` set
   to a short kebab-case slug for that chat's task** (e.g.
   `clerk-disambiguation-chips`, `fix-savings-rate-sign`). This creates the
   worktree *and* a same-named branch in one step, under
   `.claude/worktrees/`, and switches the session into it — a private
   folder and a private branch, so this chat can never step on another
   chat's uncommitted changes, and another chat can never step on this
   one's. Don't hand-roll `git worktree add` for this; the tool is what
   keeps the session's working directory, plan file, and memory in sync
   with wherever the work actually lives. Exception: read-only exploration
   (answering a question, no file edits planned) doesn't need one — only
   enter a worktree once the chat is actually going to change something.
   **Gotcha, found 2026-08-02**: with `worktree.baseRef: "head"` set (see a
   project's `.claude/settings.json` — used when the repo has no
   remote-tracking default branch, so `fresh` mode isn't usable), a new
   worktree branches from *this session's* last-known `HEAD`, not
   necessarily a fresh read of `main` — in a long session with several
   merges already done, a brand-new `EnterWorktree` call can still start
   from a `main` that's now several commits stale. Never treat the
   merge-from-main step below as optional, even for a worktree you just
   created a minute ago.
2. **Immediately after, copy in anything gitignored that the worktree will
   need** — `.env`, local data directories, secrets, anything per-machine
   rather than per-commit. `cp ../../../.env .` from a worktree under
   `.claude/worktrees/<name>/` reaches the original checkout's copy. This
   is standard practice for every worktree, not a fallback for when
   something looks broken — a fresh worktree silently missing these files
   produces symptoms (an auth screen instead of the app, a missing API
   key) that look exactly like a real bug. Do it before anything else
   needs it. These files stay gitignored inside the worktree too, so this
   never risks a commit. See each project's own `CLAUDE.md` for exactly
   which files apply to it.
3. **Work entirely inside that worktree** for the rest of the chat — edits,
   commits, tests, verification, all of it. Never edit files back in the
   shared main checkout while a chat's worktree is open.
4. **Merge back into `main` only after the pre-merge checklist below passes
   in full.**
5. **Clean up**: `ExitWorktree` with `action: "remove"` once merged (or
   `"keep"` if the work is paused, not abandoned — a later chat can resume
   it with `EnterWorktree(path: ...)`). Delete the branch after a
   successful merge unless there's a reason to keep it around.

**Merge-from-main policy: REQUIRED.** Before merging a task branch back into
`main`, first merge (or rebase) current `main` into the task branch and
resolve any conflicts there — never resolve conflicts on `main` itself. A
project may downgrade this to `OPTIONAL` in its own `CLAUDE.md` for a
specific low-risk case (e.g. a solo quick-fix branch that branched off
`main` five minutes ago and can't possibly have drifted) — state that
explicitly there, don't assume it here.

### Pre-merge checklist shape — every branch, every time, no exceptions

1. **Compatible with `main`**: the merge-from-main step above is done, and
   it's a clean or cleanly-resolved merge — no conflict markers left in
   anything.
2. **The project's automated test suite passes in full**, inside the
   worktree. See the project's own `CLAUDE.md` for the exact command.
3. **Build a real, runnable local copy from the branch and actually exercise
   the change** — not just tests, which catch regressions in logic, not
   "does this button do the thing it's supposed to." What "build and run"
   means is project-specific (a compiled app, a dev server hit with curl,
   whatever applies) — see that project's `CLAUDE.md`. Remember step 2
   above: any gitignored per-machine file the run needs (`.env`, a data
   directory, a secret) won't exist in a fresh worktree unless copied in
   first, and its absence can look exactly like a real bug.
4. **Add a `CHANGELOG.md` entry** in the project — one or two lines, why
   not just what, matching that project's existing entries' voice. Part of
   the merge, not a follow-up.

Only once all four pass does the branch merge into `main`.

## Issue tracking — the project's own checklist file is the source of truth, GitHub issues are a one-way mirror

**The project's own living checklist file (e.g. `CLAUDE-checklist.md`,
named and placed alongside `CLAUDE.md` so it's read the same way —
automatically, by any session, no `gh` call required) stays authoritative.
GitHub issues exist for visibility (notifications, closing via a merge,
browsing on github.com) — they are never the only place an open item
lives, and no session should need `gh` working just to know what's
outstanding.** Reading `gh issue list` back as if it were the source of
truth is exactly the mistake this rule exists to prevent.

Every item added to the checklist should also exist as a GitHub issue on
that project's repo, labeled on three axes (a project may adapt the exact
label names, but keep the three-axis shape):

- **Priority** — matching the checklist's own cluster the item lives under
  (e.g. `priority:now` / `priority:next` / `priority:later`).
- **Type** — `bug` / `feature` / `improvement` / `research` / `chore`.
- **Area** — project-specific (finance-tracker uses `ui` / `backend` /
  `ai-routing` / `docs` / `infra`).

Keep the checklist and the issues in sync going forward — a new checklist
entry gets a matching issue in the same turn, not as a separate cleanup
pass. The mirror is one-way: an issue closing on GitHub doesn't un-do a
checklist item — check it off in the checklist first (that's still the
record), close the issue to match. See the Issue lifecycle section below:
closing needs the user's explicit approval regardless.

## Issue lifecycle — the user is project manager, the AI is the developer

Added 2026-08-02, working model made explicit. The user is a project
manager and stakeholder here, not expected to track implementation
detail — they set priority, agree scope, and decide what's done. The AI
is the senior developer and domain expert: it researches, writes code,
reviews its own and others' changes, and tests, but never unilaterally
decides what gets built or declares it finished. GitHub issues (and each
project's checklist file — its one-way source of truth, see above) are
the user's interface into this: the one place they can see, without
reading code, what the current problems are and how they're being fixed.
Every rule below exists to keep that interface trustworthy.

### Creating an issue — reserved for the user

The AI does not create issues on its own initiative. An issue gets
created only when the user explicitly specifies that it should be — a new
problem they've named, or something the AI surfaced that the user then
asked to have tracked. Finding a real gap while working (a bug, a missing
test, a stale doc) is worth mentioning; opening an issue for it without
being asked is not.

### Scope and priority — agreed with the user before work starts

Before an issue moves from "listed" to "being worked on," its scope needs
to be agreed with the user in the same conversation (what exactly counts
as done, what's explicitly out of scope) and it needs a priority set — not
inferred or assumed by the AI from where it happens to sit in a list.

### Picking an issue — only the user decides what's next

Only the user accepts an issue into active work. If the user asks "what
should I work on next" or "which issue should we pick," the AI's job is
advisory: survey the existing issue/checklist clusters and describe what
could reasonably come next, with tradeoffs — not silently pick one and
start `EnterWorktree`. Even an "obvious" choice (highest priority, the one
just discussed) still needs the user's explicit yes before work begins.

### One issue at a time — no exceptions without alignment first

The AI works on one issue at a time. The one exception: a single piece of
work that genuinely requires or resolves more than one issue together
(e.g. two issues that turn out to be the same underlying fix). Even then,
that multi-issue scope must be aligned with the user *before* work
starts, not discovered and announced afterward — say plainly "this will
touch issues X and Y, is that the right scope?" and wait for a yes.


### Closing an issue — reserved for the user

Only the user marks an issue complete or closes it. This is a separate,
additional gate on top of checking the item off in the project's
checklist file — checking off the checklist does not by itself authorize
closing the matching issue, and the AI does not run `gh issue close`
without the user's explicit approval in that conversation.

### Document plainly, and show the result, not just describe it

Every piece of work reported back — a turn's summary, an issue comment, a
`CHANGELOG.md` entry — is written in normal human language, not terse
commit-message shorthand standing alone. When the change has any visual
component (a UI page, a rendered HTML doc, a diagram, a changed screen),
include a screenshot or rendered snapshot alongside the written
explanation before asking for the close-approval above — a sentence
claiming something renders correctly is not the same as showing it does.

## The agent roles — and who improves them

Added 2026-08-03. Eight specialist agent definitions live in **`agents/` in this
folder** (`research-agent`, `design-explorer`, `requirements-engineer`,
`design-engineer`, `proposal-auditor`, `code-engineer`, `test-engineer`,
`quality-manager`).
`~/.agent-data/agents` is a symlink pointing here, since that's where Claude Code
loads definitions from — so they carry the same version history as the rules
that govern them, and are covered by the same reserved-for-the-user rule as
this file. They are machine-global (any session on this Mac can invoke them,
not only ones under `apps/`) and **register at session start**, so a change
made mid-session doesn't take effect until a new one.

**The project manager is this session.** There is deliberately no
`project-manager.md`. A subagent cannot talk to the user — its output returns
to whoever spawned it — so a project-manager subagent would relay every
question back through the main session anyway. Since deciding *what reaches the
user* is the project manager's central job, the role sits where the
conversation happens.

The project manager: picks the ceremony tier **and says so out loud** as part
of the scope agreement that already happens before work starts (name which
agents will be invoked and why); relays the actual artifacts between agents
(they cannot read each other's output, and summarizing is where handoff detail
gets lost); enforces the bounds below; and decides what escalates. **It never
writes code, writes specs, or runs the checks itself** — a project-manager
session editing files has become an unsupervised developer with no gate, which
is the failure this whole structure exists to prevent.

| Role | Owns | Never does |
|---|---|---|
| *project manager* (this session) | Ceremony tier, relaying artifacts, enforcing bounds, escalation | Writes code or specs; runs the checks itself |
| `research-agent` | Precedent, feasibility, options with tradeoffs, open questions | Writes REQUIREMENTS.md; picks a direction |
| `design-explorer` | Several structurally different concepts, early — ambition first, feasibility annotated | Converges; produces a buildable spec |
| `requirements-engineer` | REQUIREMENTS.md — numbered, testable criteria | Designs the solution; chooses between directions |
| `design-engineer` | Buildable specs from a locked direction — every state, tokens, consistency | Writes production code; explores alternatives |
| `code-engineer` | Implementation in its worktree | Certifies its own work as done; expands scope |
| `test-engineer` | Validation against criteria; bug reports | Fixes anything it finds |
| `proposal-auditor` | Distance between the accepted proposal and the requirements/design, classified | Writes or fixes either; decides whether drift is acceptable; approves |
| `quality-manager` | The pre-merge gate; LESSONS.md curation | Fixes anything; approves the merge |

**Design is deliberately two roles.** Exploration wants provocation and
structural alternatives; specification wants consistency and complete states.
Held in one role the conservative instinct leaks into the creative half and the
exploration comes out timid. `design-explorer` therefore runs *before*
requirements harden — mockups are a thinking tool for deciding what the thing
should be — and `design-engineer` picks up only once a direction is chosen.

**Improving an agent definition is reserved for the user**, for the same reason
that applies to this folder: it changes behavior for every project at once. Any
agent may surface that its own instructions are wrong, in its report, as an
observation — it never edits itself. The quality manager may flag a pattern
across tasks ("three gates failed the same way"); it reports, it does not act.
An agent that can rewrite the specs it reviews against is no longer an
independent check. **The signal worth watching**: a lesson that keeps recurring
in `LESSONS.md` means an agent's *instructions* are wrong, not that the lesson
needs restating.

### How the project manager actually invokes one

Added 2026-08-04, because the rule above was being read and not followed. Six
finance-tracker issue sessions (#30, #31, #32, #35, #36, #37) each read this
file and then implemented the whole feature themselves with `Edit` and `Bash` —
zero agent calls, and **no pre-merge gate on six merged features**. The same
project's open-ended session (`issue-27-person-dossier`) ran eighteen agent
calls across all six roles. The definitions, the symlink and registration were
never the problem.

Part of what was missing is embarrassingly simple: **this file named the roles
and never named the mechanism.** It gives exact commands for everything else —
`EnterWorktree`, `apprun start …` — and for the one behaviour the whole
structure depends on it gave a table. Delegation was left to be inferred.

It is the **Agent tool**, with `subagent_type` set to the definition's `name`:

```
Agent(subagent_type: "code-engineer", prompt: "<the task brief, in full>")
Agent(subagent_type: "quality-manager", prompt: "<branch, criteria, what to verify>")
```

Independent agents go in one message so they run concurrently. The prompt must
carry the artifact **in full** — agents cannot read each other's output, and
summarising the handoff is where the detail goes.

**Reading the role table is not delegation.** The test is behavioural and it is
easy to apply mid-task: *if this session is the one calling `Edit`, it is no
longer the project manager.* At that moment there is no independent gate left,
which is the exact failure this structure exists to prevent — and it will not
announce itself, because the work still gets done and still looks fine.

**A fully-specified brief is the trap.** An opening message that carries the
issue number, the requirements file, the accepted proposal and a list of
acceptance criteria *is* a code-engineer task brief — and a session handed one
will execute it, because the live instruction beats a file it was told to go
read. That is what happened in all six. The brief being complete is not a reason
to skip the pipeline; the criteria being written down is precisely what makes
`test-engineer` and `quality-manager` checkable.

**Corrected 2026-08-04, same day it was written.** The first version of this
paragraph said a complete brief meant the upstream roles could be skipped and
the tier was small-fix. That is wrong, and the section below says why: **an
accepted proposal is not settled requirements**, and a brief quoting one is not
a substitute for `REQUIREMENTS.md` and a screen spec. Skipping straight to the
code engineer is exactly what produced the failure this rule exists to stop.

### Escalation

- **Always to the user**: anything the issue lifecycle above already reserves;
  a bug dispute unresolved after **two rounds**; an agent repeating the same
  failing approach (stall watch); a requirements ambiguity no agent can settle;
  any scope change discovered mid-task, however small.
- **Handled without escalating**: which agents to invoke for an agreed task,
  routing a confirmed bug back for a fix, re-running a gate after that fix.

### When a gate has to be re-run

After a gate blocks and the code engineer addresses it, whether the gate runs
again depends on what changed:

- **Behaviour changed → re-gate.** Any edit to code that runs.
- **Nothing that runs changed → do not re-gate.** A docstring, a comment, a
  changelog line, or committing already-verified work. Re-running a full gate to
  re-confirm what it just confirmed costs as much as the original pass and
  learns nothing.

When a gate is skipped, **`AGENT-LOG.md` must say so and why**. "The gate passed"
and "the gate passed an earlier version of this branch" are different claims,
and only one of them is true in that case.

### LESSONS.md

Each project keeps its own `LESSONS.md` at its root (not in this folder — it's
operational and written during tasks). Entries are typed and **append-only**;
no agent rewrites, reorders, or deletes another's, and pruning is surfaced as a
suggestion to the user rather than acted on:

- `[bug]` — a confirmed defect (quality manager)
- `[gotcha]` — an environment or tooling footgun (code engineer)
- `[attempt]` — an approach tried that didn't pan out (code engineer)
- `[resolved-dispute]` — a bug report successfully disputed (quality manager)
- `[requirements-gap]` — an ambiguity resolved with the user (requirements engineer)

**The format, because two sessions invented different ones.** On 2026-08-03 two
sessions created `LESSONS.md` independently in the same project and produced
incompatible layouts — the rule named the entry *types* but never the shape.
Use a heading per entry:

```markdown
## [type] YYYY-MM-DD · A one-line title stating the lesson
Written by: <role> · <branch or task>

The finding, and what to do differently. Concrete enough to act on cold.
```

The title must state the lesson, not the symptom — "sed line-trimming is not
`str.strip()`" rather than "build script bug". A reader scanning headings should
be able to tell whether an entry applies to them without opening it.

Entries stay **append-only**: never rewrite, reorder or reformat another
session's, including ones in an older layout. Leave them as they are and match
this shape going forward.

### REQUIREMENTS.md and the checklist complement each other

The project's checklist file stays authoritative for *what to work on*.
`REQUIREMENTS.md` holds acceptance criteria for *the task currently in flight*,
written per feature — not a retroactive spec for the whole project.

## AGENT-LOG.md — what was called, in what order, and what came back

Added 2026-08-03. Each project keeps an `AGENT-LOG.md` at its root, alongside
`CHANGELOG.md` and `LESSONS.md`. It exists so the user can look back at how a
task was actually run — which agents, in what sequence, what each returned, and
what it cost — without reading a transcript.

**The project manager writes it, because no one else can.** Agents cannot see
each other; only the session doing the orchestrating knows the whole sequence.
This is bookkeeping, not development work, so it does not breach the rule that
the project manager never writes code or specs.

**One entry per task**, appended when the task closes — merged, abandoned, or
parked. Newest first, same convention as `CHANGELOG.md`. Committed, not
gitignored: it is project history.

The shape, kept consistent so entries can be compared across tasks:

```markdown
## 2026-08-03 · <task/branch name>
**Project:** finance-tracker
**Task:** one sentence, in the user's terms
**Tier:** feature | small-fix | research   **Phase:** prototype | production

| # | Agent | Why it was called | What came back | Tokens | Tools | Duration |
|---|-------|-------------------|----------------|-------:|------:|---------:|
| 1 | code-engineer | implement the 9 criteria | claimed all pass | 194k | 115 | 18m |
| 2 | test-engineer | independent validation | 3 bugs, 1 critical | 116k | 56 | 11m |
| | | | **total** | **310k** | **171** | **29m** |

**Disputes:** what was contested, who won, on what argument
**Escalated to the user:** what needed a decision, and what was decided
**Outcome:** merged / not merged / parked, and why
```

**Where the per-agent numbers come from, and why they must be written down
immediately:** each agent's completion notification carries its exact token
count, tool-use count, and wall-clock duration. **Those figures are only visible
at that moment** — they are not recoverable later from the transcript without
significant digging. So record them into the log as each agent returns rather
than reconstructing the table at the end of the task, or the numbers will be
guesses, which defeats the purpose of keeping them.

Report tokens to three significant figures (`194k`), duration in whole minutes,
and always include a total row — the total is what answers "was this tier worth
it."

**Name the project in every entry**, even though the file already sits inside
it. Three reasons it can't be left implicit: a task runs from a worktree, so
"where the file is" is not obviously the project at the moment of writing;
entries get pasted into a review or a chat and must still say what they refer
to; and collating several projects' logs to compare how tasks ran is the whole
point of keeping them — which only works if each entry stands on its own. If a
task genuinely spans more than one project, name all of them.

Two things make it worth keeping rather than a chore. It is the **evidence base
for improving the agents** — a role whose findings are repeatedly disputed, or a
gate that repeatedly misses the same class of problem, is visible here and
nowhere else. And it makes the **cost of ceremony legible**: multi-agent work is
substantially more expensive than a single session, so a record of what each
task actually cost is what tells the user when a lighter tier would have done.

Record what actually happened, including the parts that went badly — an agent
that had to be re-run, a fix that broke something else, a tier chosen wrongly.
A log that only records clean runs is worth nothing for analysis.

## Project phases — prototype and production

Added 2026-08-03. Phase is a property of **the surface being changed**, not of
the whole project: a production-phase project can host a prototype-phase
feature. The project's default phase is recorded in its own `CLAUDE.md`; a
per-feature override goes in that feature's checklist entry.

| | Prototype | Production |
|---|---|---|
| Goal | Find out whether this is right | Keep it working |
| Tests | Optional — spikes may be thrown away | Required, suite green before merge |
| Gate | Light: does it run, does it show the idea | Full: criteria checked, built, exercised, changelog |
| Design | Exploration encouraged, nothing locked | Locked direction, every state specified |
| Churn | Expected; rewrites are cheap | Minimal; no unprompted refactors |
| Issues | Only blockers — polish is premature | Everything found gets written down |

**Phase sets the default ceremony tier** rather than adding a second dimension:
prototype defaults to the light tier, production to full. One decision, stated
out loud when scope is agreed.

**Promotion is a deliberate act, and it is the user's.** Prototype code
silently becoming production code is the documented failure mode. Promotion has
its own checklist — tests now written, requirements documented retroactively,
design locked, changelog entry, a pass through the full gate — and until the
user says a feature is promoted it stays prototype.

### Ceremony tiers — light is the default

Published research found full-ceremony role pipelines *reduced* correctness for
most models tested, so:

- **Feature**: full pipeline, every role the task calls for.
- **Small fix**: code engineer + quality manager only.
- **Research / proposal**: research agent and/or requirements engineer —
  nothing merges, so there's nothing to gate.

Research and design steps are optional and run only when the task needs them.

**Model tiers follow ceremony tiers.** `code-engineer` is pinned to `sonnet`; a
separate reviewer catches more of a weaker writer's mistakes than a stronger
one's, which is what makes that safe. **Never downgrade `test-engineer` or
`quality-manager`** — they are the mechanism the trade-off depends on.

## Telling running copies apart

Added 2026-08-03. Several copies of the same app end up open at once and
nothing on screen says which is which. One state is silent and every other
state announces itself: **no badge means the stable copy** — the one the user
reviews and files issues against. Absence is the signal.

| Run | Port | Title | Badge |
|---|---|---|---|
| Stable | project default (e.g. 8502) | `<App>` | none |
| Test (worktree) | 8600–8699 | `TEST · <branch> — <App>` | amber |
| Prototype | 8700–8799 | `PROTO · <branch> — <App>` | violet |

The port within each range is derived from a hash of the branch name, so a
given branch always lands on the same port and a tab left open stays pointed at
the right thing. Existing condition pills (demo data, auth off) stack alongside
— run identity and data state are different questions.

**There is exactly one stable copy at a time.** A new stable build replaces the
installed one; stale builds from a previous version are deleted rather than
left to linger. Two things both claiming to be stable is precisely the
confusion this section exists to remove.

For a packaged app, a distinct bundle name per build keeps test builds separate
in Cmd-Tab and the Dock instead of masquerading as the installed one.

### Leave nothing running — and stop only what you started

Badges say which copy is which; they do nothing to stop copies accumulating.
So: **any agent that starts an app instance stops it before reporting** — dev
server, built `.app`, anything binding a port or opening a window. This is
unconditional and applies on the failure path too; an agent that abandons a
task halfway shuts down what it started on the way out, and says in its report
what it started and that it stopped it.

A validation pass that ends with three servers still up has recreated the exact
confusion this section exists to remove, and leaves the next session with ports
that look occupied for no visible reason.

The rule scopes to the **session**, not to the individual agent. Several agents
in one task may hand the same running copy along — the test engineer reusing the
server the code engineer started is normal and wasteful to forbid. What must not
happen is the task finishing with it still up. **The session that started an
instance is the session that closes it, when the task that needed it is done** —
and the project manager (this session) is the one accountable for that, because
it is the only role that sees the whole task.

#### Never close an instance you didn't start

Added 2026-08-04. The opposite failure is worse than the one above, because it
destroys someone else's work rather than merely littering. **An agent stops only
the instances its own session started.** Anything else that is running belongs to
somebody — the user reviewing a build, or a parallel session mid-validation — and
killing it takes away the thing they were looking at, usually without them
learning why it vanished.

This makes the stable copy a *case* of the rule rather than an exception to it:
no session started it, so no session stops it, and no session builds over it.

In practice that means cleanup is **targeted, never a sweep**:

- Track what you start — the PID and the port — and close by that. An agent that
  didn't record what it started cannot clean up correctly and should say so
  rather than guess.
- **No blanket kills.** `pkill -f streamlit`, `killall <App>`, or anything that
  clears a port range on principle will take down copies you never started. If
  you catch yourself matching on the app's name instead of on your own PID or
  your own derived port, stop.
- A port in your own range that you did *not* start is not yours to reclaim.
  Branch-derived ports collide when the same branch is open twice; that is a
  conflict to report, not to resolve by killing the occupant.
- If an instance you started has already been closed by the time you clean up,
  that is fine — say so and move on.

**Leaving a stranger's copy running is the correct outcome**, even when it looks
like the exact mess the section above is about. Ownership decides, not tidiness.

#### The run registry — `bin/apprun`

Added 2026-08-04. The two rules above are unfollowable without one fact no agent
has: *who started this*. So it gets recorded. `common-rules/bin/apprun` keeps
`~/.agent-data/app-runs.jsonl` — one line per instance, carrying project, phase,
port, pid, url, branch, and the **session id and session pid** of whoever started
it.

Ownership is then exact rather than guessed: `CLAUDE_CODE_SESSION_ID` says whose
it is, and `kill -0` on the recorded session pid says whether that owner still
exists. Three duties, and they are the whole protocol:

```bash
apprun start --project <p> --phase stable|test|proto --port <n> --pid <n>   # on launch
apprun list                                                                # what you still owe
apprun stop --all                                                          # before reporting
```

- **`start` immediately after launching anything.** An unregistered instance is
  invisible to every later cleanup — it is exactly how the pile forms.
- **`stop` refuses what isn't yours.** A live stranger's copy, an orphan, the
  stable copy: all three are declined with the reason. The rule stops depending
  on an agent remembering it.
- **`stop` closes the browser window too** — see below.
- **`sweep` reports orphans** and never clears them without `--clear`, which is
  the user's call, because one of those windows may be what they are looking at.

#### Stopping the server is not closing the window

This is the gap that produced the actual complaint. Every rule here talked about
processes and ports; a NiceGUI or Streamlit launch opens a **browser window**,
and killing the server leaves that window sitting there, dead, still titled like
the app. Ten sessions that each cleaned up perfectly still leave ten windows.

So **cleanup closes the window as well as the process.** `apprun stop` does it —
matching on the exact `http://127.0.0.1:<port>` of the instance being stopped, so
it can only ever hit that one. If the window can't be closed (browser not
running, automation not permitted), say so rather than reporting a clean finish.

#### Orphans — the one thing a stranger may close

An instance whose app is up but whose **owning session is gone** is an orphan.
Nobody will ever come back for it, so the ownership rule alone would keep it
running forever — which is how "stop only what you started" quietly turns into
the pile it was meant to prevent.

`apprun sweep` lists them with their age and project. Clearing them needs the
user's explicit yes; a session never clears orphans on its own initiative, and
never as a side effect of some other task.

**A copy started for the user to look at is not cleaned up on the usual
schedule** — see "Offer a demo before asking for the yes". It stays until they
say they are done, and the session reports that it left it up and where.

**The stable copy is never an orphan**, however long it outlives whatever started
it. Outliving sessions is its entire job.

### There is always a clean copy to open

Added 2026-08-04. Protecting the stable copy is not the same as guaranteeing one
exists, and only the second is any use when the user wants to just open the app.

**The clean copy is refreshed from `main`, after a feature merges.** That is the
moment it is both safe and meaningful to rebuild: the work is integrated, gated
and merged, so a rebuild carries the new feature and nothing half-finished. Not
at session start (which would rebuild for no reason), not mid-task (the rule
against building over the stable copy still holds everywhere else).

So the post-merge routine ends with: rebuild from `main`, replace the installed
copy, restart it, and register it as `--phase stable`. A merge that leaves the
installed app on last week's build has finished the git work and not the task.

`apprun sweep` says plainly when nothing is up — **`NO CLEAN COPY RUNNING`** —
because the failure that matters is silent: the user goes to open the app and
there is nothing to open, and no one noticed.

#### The final app gets its own icon

The badges and titles in the table above only help once a window is open and
being read. The Dock and Cmd-Tab show an **icon**, and if every build shares one,
the user is back to guessing which of five identical tiles is the real app.

So: **one icon is reserved for the installed stable copy and used by nothing
else.** Test and prototype builds carry a visibly different mark — different
enough to tell apart at Dock size, in peripheral vision, without reading a label.
A tinted or badged variant of the same shape is the usual answer; a bundle name
suffix is not sufficient on its own, because the icon is what the eye lands on.

Picking the reserved icon is design work and belongs to a project, not to this
file. Where a project's icon carries **stale branding** — a mark from a name the
app no longer has — that is a finding worth raising rather than living with,
since it makes the one tile that should be unmistakable say the wrong thing.

## Findings become well-formed issue drafts

Added 2026-08-03. Creating an issue stays the user's call (see the issue
lifecycle above). What agents owe is the step before: a finding that surfaces
mid-session must not evaporate when the session ends. Agents produce **issue
drafts** in a fixed shape and the user approves them.

A draft is complete only with all five — an agent that cannot fill them in has
a hunch, not a finding:

- **What's wrong or missing**, in one sentence understandable cold.
- **Where** — file, screen, or flow.
- **Why it matters** — the consequence if never fixed. "Inconsistent" is not a
  consequence.
- **What done looks like** — criteria the test engineer could check.
- **Proposed labels** on the three axes above: priority, type, area.

**Prototype-phase work raises only blocking issues.** Filing polish tickets
against something that may be discarded next week is how a backlog fills with
items that were never real.

### Offer a demo before asking for the yes

Added 2026-08-04. A draft issue is a paragraph of text, and approving it from
text alone means deciding about a screen the user hasn't looked at in weeks.
So **the project manager offers to show the thing before asking for approval** —
of a draft issue, and of any proposal about an existing surface.

The demo is of *what is there now*, not of the fix — nothing is built yet. Its
job is to put the user in front of the actual screen so the decision is made
against the real thing rather than a description of it.

**An offer, not a gate.** The user says "just approve it" often and that is a
complete answer; the point is that they were given the choice, not that they
took it. Don't demo unprompted, and don't hold the question hostage to it.

Two things make an offer worth accepting:

- **Navigation, click by click, in the app's own words.** "Sidebar → Ledger,
  Subscriptions tab, the row for Safeguard" — not "the subscriptions area".
  Name what to look at once there, and what looks wrong about it.
- **No new window where the clean copy will do.** An issue about existing
  behaviour demos on the stable copy, which is already running and is the one
  the user trusts. Starting a second copy to show something the first one
  already shows is how the pile the user complained about gets rebuilt.

A demo that genuinely needs its own instance (a branch, a prototype, a state the
stable copy can't reach) registers as `test` or `proto` like anything else — but
**it is not cleaned up on the usual schedule.** It was started *for* the user; it
stays until they say they're done with it, and the session says plainly that it
left it up and on which port. Closing the window someone is still reading is the
failure the ownership rules exist to prevent, and a demo is the easiest place to
commit it by reflex.

## Proposals — one per task, tracked to a decision

Added 2026-08-03. **Adopted by every project that references this file.**

A proposal is how work that needs a decision reaches the user. It lives in the
project's `docs/proposals/`.

### One proposal per topic, not one per role — and not one per session

However many agents run — research alone, or requirements and design together,
or all four — **a topic produces exactly one proposal.** Each role contributes a
section; the project manager assembles them; the user decides once.

Roles chain freely without stopping for approval. That is deliberate: the user
approves the *plan* (which agents run) up front, then the *result* at the end.
The cost is real and should be stated when it applies — a wrong requirement
wastes the design work built on it too.

**A proposal stays open across sessions until it is decided.** If research runs
today and the user asks for requirements tomorrow, that is the *same* proposal
gaining a section — not a second one. It sits at `draft` the whole time and only
moves to `proposed` when the user is actually being asked to decide.

This is the rule's weak point, so it is stated plainly: "one per task" invites
treating each new conversation as a new task, which quietly rebuilds the chain of
four proposals this exists to prevent. **Before writing a new proposal, check
`docs/proposals/` for an open one on the same topic and extend it.** A second
proposal on a live topic is only correct when the first has already been decided
and this genuinely supersedes or amends it — in which case it says so in its
status.

**What stays absolute:** nothing reaches the code engineer until the user has
accepted the proposal.

That absolute exists because of a real failure on finance-tracker's
`person-dossier` task, worth keeping on the record: a design-engineer's screen
spec went straight to a code-engineer with no pause, and the user only found out
what had been designed once it was already built. An earlier rule (2026-08-03,
now superseded) fixed that by gating *every* role transition. This supersedes it
with a single gate at the end — which still prevents that failure, because the
spec cannot reach a code engineer unapproved.

**Relaying means showing, not summarising.** The proposal contains each
contributing role's actual output, not a note that one was produced. That was
the other half of the earlier rule and it survives intact — a single gate is only
a real gate if what passes through it is legible.

Four separate approvals per feature was the alternative, and it was rejected for
a good reason: stage-gate research is consistent that a gate which isn't a real
decision point is worse than no gate, because it costs time and manufactures
false confidence. Large organisations defend against that with a *different
approver* at each stage. With one sponsor that is impossible, so the chain would
have decayed into a sequence of rubber stamps. One gate cannot.

### Status lives in the document

Six statuses, each naming something that happens next — a status nobody acts on
is decoration:

| Status | What happens next |
|---|---|
| `draft` | Nobody acts. Replaces a `draft-` filename prefix. |
| `proposed` | With the user. Everything downstream is blocked. |
| `accepted` | Draft issue written for the user's acceptance; a session is offered (below). **Not** a commitment to build, **not** authority to create issues. |
| `rejected` | Nothing happens. Kept so the question isn't re-asked in three months. |
| `superseded-by NN` / `amends NN` | Read NN instead / read NN alongside. The IETF Obsoletes-vs-Updates split — whole replacement versus partial change. |
| `built` | The work it authorised is done. History. |

There is deliberately **no `deferred`** (it becomes a graveyard, and for one
developer it is indistinguishable from a checklist item under "Later") and **no
`partly-accepted`** (no mainstream format has it — partial acceptance is a fact
about *the work*, so record the accepted-item list in the checklist entry and
leave the proposal whole).

**Status goes in the proposal itself** — a `<meta name="proposal-status">` plus a
visible chip — and `docs/proposals/README.md` is **regenerated from those tags**,
never hand-maintained. Every established tool works document-as-source,
index-as-derived; none does the reverse. Regenerating is a required step in the
pre-merge checklist, not something done on request: the one team that put status
in the document and left the index manual still needed a bot to stop it drifting.

### Numbering and type

**One sequence** across all proposals regardless of which role wrote them, so
ordering stays chronological and nothing needs renaming. The stage is a `type`
field — `research` / `requirements` / `design-concept` / `design-spec` /
`findings` — not a filename prefix.

### Immutability

**Conclusions are frozen once a proposal is accepted.** Status, cross-links and
typo or label fixes may be corrected freely; a wrong printed number is a label,
not a conclusion. Substantial change means a **new** proposal carrying
`amends NN` or `supersedes NN` — never an edit to the old one.

This is the near-unanimous convention across ADR, PEP, RFC and KEP practice, and
it exists because a document that quietly changes its own conclusion misleads
every later reader with no signal that it happened.

### Traceability runs one way

The checklist entry and the issue say "proposal 06". **The proposal says nothing
about issues.** Reverse lookup is a search, not a stored list.

The asymmetry is the point: maintaining links inside the proposal means editing
it whenever an issue is created, which fights immutability directly and is the
half that rots.

### How a proposal is delivered — artifact, then buttons

Added 2026-08-04 (proposal 01, accepted the same day). In one project the user
had to ask for the rendered view and the decision buttons **every single time**;
in another he never did. The difference was not care — one project had built a
place for proposals to live and the other had not, so he became the convention
himself. Four rules, every adopting project:

1. **A proposal is delivered as a rendered HTML artifact — never as chat prose.**
   Not "here's a summary, shall I write it up?" The document is the delivery.
2. **The committed copy exists before the artifact is shown** — at
   `docs/proposals/NN-<type>-<topic>.html` in the project's repo. **The artifact
   is the view; the repo is the record.** Rule 1 without rule 2 just makes
   prettier things that still vanish.
3. **Delivery is immediately followed by a decision prompt with buttons.** Never
   "let me know what you think". The session that shows a proposal asks the
   question in the same breath, with the options as buttons.
4. **One decision per prompt.** A proposal with four open questions asks four
   distinct questions, each separately answerable — never one bundled question,
   because a bundled question gets a bundled answer and the detail is lost.

**The default button set**, so the options aren't reinvented (and vague) each
time — recommendation first, per the existing convention:

| Button | Means | What follows |
|---|---|---|
| **Accept** | the direction is right | status → `accepted`, draft issue, session offered, requirements and design begin |
| **Amend** | right idea, wrong specifics | the *same* proposal is revised — never a second one |
| **Reject** | not doing this | status → `rejected`, reason recorded in the document |
| **Show me first** | look before deciding | the demo, click-by-click, on the clean copy |

**Buttons appear even when there is nothing to decide yet** — the user's call,
against the recommendation. An early or informational proposal still ends with a
prompt whose option may be no more than "noted". The reasoning is sound: an
absent prompt is ambiguous, and he should never have to work out whether a
question is being asked.

**Reports, findings and gate results get the artifact, not the prompt.** Only
work that actually wants a decision ends with buttons — that restraint is what
keeps the buttons meaningful rather than something to click past.

### When a proposal is accepted

1. A **draft issue** is written for the user's acceptance — what, where, why it
   matters, what done looks like, proposed labels. Creating the real issue stays
   the user's call, unchanged. Where the issue concerns an existing surface,
   **offer the demo before asking** (see "Offer a demo before asking for the
   yes") — click-by-click navigation, on the clean copy where it will do.
2. A **session is offered** for the work, named
   `<app> - <proposal/issue no> - <short description>` — e.g.
   `finance-tracker - proposal 09 - fd closure sign`.

The session is offered, not started. Picking what to work on is the user's
decision, and a session that starts itself has quietly taken it.

3. That session's **first work is requirements, then design, then L2** — not
   implementation. See "After acceptance" below; the accepted proposal is the
   input to that work, not a substitute for it.

#### The brief that starts it — name the agents, or they won't run

Added 2026-08-04. The rules say the project manager "names which agents will be
invoked and why" as part of the scope agreement. Six finance-tracker issue
briefs named none, and none ran. The step existed in this file and not in the
artifact that actually starts the work, which is the only place it could have
taken effect.

So a session brief states the tier and the agent set, up front, before the task
detail — and it is addressed to a project manager, not to a developer:

```markdown
Project-manage GitHub issue #36 in <repo>: "<title>".

From proposal <NN>, accepted <date>. The proposal is the direction, not the
requirements. Agents, in order: requirements-engineer, design-engineer, then
your L2 approval, then code-engineer, test-engineer, quality-manager.
You do not write the code, the specs, or run the checks.

<If REQUIREMENTS.md and a design spec already exist and carry an L2 approval,
say so here and name the agents that remain. Skipping design for work with no
visible surface is fine — say that too, and record it in AGENT-LOG.md.>

Read /Users/the-sponsor/apps/common-rules/CLAUDE-workflow.md and CLAUDE.md first.
EnterWorktree is the first action on this repo.

<context, acceptance criteria, constraints — passed through to the code
engineer in full, not summarised>
```

Two details that look cosmetic and are not:

- **"Project-manage", not "Implement".** The verb sets the role, and the whole
  failure was sessions taking the developer's seat. A brief that opens
  "Implement …" has already told the session to do it itself, and everything
  after that is read in that light.
- **An absolute path to this file.** `../common-rules/CLAUDE-workflow.md` is
  correct from a project root and **wrong from a worktree**, where it resolves
  to `<project>/.claude/worktrees/common-rules/` and does not exist. The six
  briefs all carried the relative form; sessions recovered by hunting for the
  absolute path, which is luck, not a mechanism.

### After acceptance: requirements, then design, then L2 — never straight to code

Added 2026-08-04. **An accepted proposal is not settled requirements.** It is a
decision about direction, argued in prose, and it is the input to requirements
work rather than a replacement for it. So acceptance starts a sequence, and the
sequence is not optional:

1. **`requirements-engineer`** turns the accepted proposal into `REQUIREMENTS.md`
   — numbered, testable, explicit about what is out of scope.
2. **`design-engineer`** turns those requirements into a buildable spec — every
   state, not just the happy one.
3. **`proposal-auditor`** measures how far the pair has moved from the accepted
   proposal, and classifies every divergence.
4. **L2 approval** — the project manager reviews both together, with the audit in
   hand, and approves before any code-engineer work starts.
5. Only then the code engineer, the test engineer, and the gate.

**L1 is the user accepting the proposal; L2 is the project manager accepting the
requirements and design produced from it.** Two different decisions about two
different artifacts. L1 says *this is the direction*; L2 says *this is what
"built" means, and it is complete enough to hand over*. Collapsing them means the
second decision is never made by anyone — it just gets inferred, one file at a
time, by whoever is writing the code.

**Why it cannot be skipped:** the code engineer will not expand requirements and
design properly, and it isn't a flaw in that agent — it is being asked to do two
jobs whose instincts conflict. Given a gap it fills it in passing, in the shape
that is easiest to build, and the decision then exists only as code. Nothing was
written down, so there is nothing for the test engineer to check against and
nothing for the gate to hold it to. **An inferred requirement is an invisible
one.** It fails silently and late, if it ever fails visibly at all.

#### L2 is not the project manager's own opinion — `proposal-auditor` supplies the evidence

Added 2026-08-04. L2 has an obvious weakness: the project manager would be
approving output from a pipeline it commissioned itself. So the comparison is
done by someone else. `proposal-auditor` reads the accepted proposal, the
requirements and the design, and classifies **every** divergence into one of
five buckets:

| | Meaning | Whose call |
|---|---|---|
| `faithful` | says what the proposal decided | — |
| `elaboration` | detail the proposal implied but didn't spell out | **L2** |
| `drift` | something the proposal decided, now changed | **the user** |
| `silent decision` | a decision the proposal never made and can't imply | **the user** |
| `gap` | a proposal decision the requirements don't cover | back to requirements |

That classification is what L2 acts on. Elaboration is what requirements and
design work is *for* and the project manager approves it. Drift and silent
decisions are two of the four escalations below, now detected rather than
noticed. A gap means the work isn't ready for L2 at all.

**It is deliberately not the quality manager.** That agent would otherwise
approve the criteria at L2 and later gate the built work against those same
criteria — marking its own homework at the point independence matters most. The
same principle already stated for agent definitions applies here: an agent that
approved the specs it reviews against is no longer an independent check.

The auditor is **read-only and decides nothing.** It measures distance; the
project manager approves or escalates. It cannot catch a proposal that was vague
to begin with — but it is required to say when the proposal was silent, which is
its own useful finding. It runs **only on post-acceptance work**: no proposal, no
auditor, and a small fix pays nothing for it.

**Escalate to the user when the update is major** — L2 is the project manager's
call, but four things are the user's, and none of them are judgment calls:

- the requirements or design **contradict** something the proposal decided
- **scope moves** — a surface, route, or class of state that the proposal did
  not contemplate is added or dropped
- a decision surfaces that the proposal **did not make and cannot be inferred**
- the work turns out **materially larger or costlier** than the proposal implied

Anything else is L2 and the project manager approves it. When in doubt escalate:
a question costs a message, and a wrong assumption costs the build.

**Skipping design specifically**, for work with no visible surface, is allowed —
and must be **stated out loud and recorded in `AGENT-LOG.md`**, the same as a
skipped gate. Silence is what makes a skip indistinguishable from an oversight.

#### The failure this came from — issue #31

Worth keeping concrete, because the cost was total. The `#31` brief went from
proposal 07 straight to "Implement", for **the most design-dependent task in the
batch**: a rail, a seam, and a dock, where the whole point was that the boundary
between confirming a write and asking a question be obvious *at a glance*. No
`REQUIREMENTS.md`. No screen spec. A layout problem handed over as prose.

The session implemented all of it itself across 256 messages. The user then
intervened — "check common rules and rework the session, use the 3 agents
defined by common rules" — and the session's own reply was *"You're right, I
broke the rule that matters most here"*, after which **it reverted every one of
its seven changes and started again.** An entire session's work, discarded.

And the rework still ran only `code-engineer`. Even being told to use the agents
did not produce requirements or design work, because nobody had said that the
proposal wasn't already the requirements. That is the gap this section closes.

## Keep the story — LOW PRIORITY, every project

Added 2026-08-03. **Adopted by every project that references this file.**

There is a running record in `common-rules/docs/story/` of how working this way
has actually gone — from a single chat doing everything, through building a team
of agents, to measuring and trimming it. the-sponsor is a project manager by
profession and intends to present this experience to fellow managers: what was
tried, what it cost, what broke, what the numbers showed.

**This is explicitly low priority.** It never blocks a task, never delays a
merge, and never justifies extra agent passes. If a session is busy, skip it —
the `AGENT-LOG.md` and `CHANGELOG.md` entries already capture the raw facts, and
a snapshot can be written later from those.

**Where things go:**

- `docs/story/README.md` — the narrative, in chapters. Update when a chapter
  genuinely changes, not per task.
- `docs/story/snapshots/YYYY-MM-DD-<slug>.md` — a point-in-time record with real
  measured numbers. Written when something notable happens: a new way of working
  is tried, a cost figure surprises, an approach is abandoned.
- `docs/*.md` — plain-language reports for someone who wasn't in the room.

**It lives in this shared folder, not in a project**, because the story spans all
of them — it is about the way of working, not about any one app. Project-specific
write-ups stay in that project's own `docs/`.

**What makes a snapshot worth keeping:** real numbers rather than impressions,
and the parts that went badly. A record of only smooth runs is worthless for a
presentation and worse than nothing for learning — the failures are the content.
Include the mundane interruptions too (a toolchain breaking, another session
moving `main`); a story where nothing ordinary goes wrong isn't believable.

## Changing these shared rules — also reserved for the user

Added 2026-08-02. The same principle as the Issue lifecycle section above
applies to this folder itself: the AI does not edit `CLAUDE-workflow.md`,
`README.md`, or `CHANGELOG.md` here on its own initiative, even when it
notices something worth updating (a stale note, a new gotcha, a rule that
turned out wrong in practice). It surfaces that to the user and asks —
the same way an issue doesn't get created or closed without being asked.
A change only happens once the user has explicitly directed it in that
conversation. This file changing behavior for every adopting project at
once is exactly why the bar for changing it, unprompted, is higher than
for an ordinary project file.

### How a change gets made — branch and pull request

Added 2026-08-03, after the first batch of rule changes went straight to
`main`, which contradicted the no-direct-to-main rule stated above in this
same file.

**This applies to this repo only.** Projects do not use pull requests —
finance-tracker, pockets and the rest keep the flow described at the top of
this file: worktree, pre-merge checklist, then merge into `main` on the
user's approval. Stated explicitly because project sessions read this file
too, and "every change goes through a pull request" would otherwise look
like it applied to them. (User's decision, 2026-08-03.)

**Every change here goes on a branch and through a pull request**, even a
one-line fix, even though this is a solo repo. Not ceremony for its own
sake — a diff is far better review material than a summary in chat, and
this repo governs how autonomous agents behave across every project, so a
bad rule lands everywhere at once and may not be noticed for several tasks.
The PR is also what makes the reserved-for-the-user rule above
*structural* rather than dependent on the AI remembering to ask.

The AI opens the PR; **the user merges it.** Never merge your own rule
change.

**The user can merge from the chat instead of GitHub.** Once a PR is open,
summarise what is in it and offer to merge; if the user says so, run
`gh pr merge --merge --delete-branch`, then update local `main` and delete the
local branch. Visiting github.com stays optional, for when the user actually
wants to read the diff.

Two things this does not change. **The AI still never merges without the user
saying so in that conversation** — merging because a gate passed would remove
the one approval gate this whole structure is built around; "convenient" and
"automatic" are different things. And **always summarise the contents before
offering**, or "merge it" becomes a rubber stamp on something unread, which is
the same failure as an implementer signing off its own work.

**No worktree needed** for this repo, unlike the projects. Worktrees exist
so parallel sessions don't collide over a build; four markdown files and a
directory of agent definitions have no build and no test suite to collide
over. A branch is enough.

**Know what the PR does and does not gate.** `~/.agent-data/agents` is a
symlink into `agents/` here, so **editing an agent definition changes the
live agent the moment the file is saved** — before any commit, branch, or
merge. For `agents/`, the pull request is a record and a review surface,
not a gate. It cannot prevent a bad agent change from taking effect; it can
only show what happened and make reverting easy. That trade is deliberate:
copy-on-merge would gate the change but reintroduce exactly the drift
between two copies that the symlink exists to eliminate.

### Notice the repeats — `ASKS.md`

Added 2026-08-04. Almost every rule in this file started as the user asking for
something in a chat. Most of those asks were made more than once, in different
projects, before anyone noticed they were the same ask — which means the rule
existed as a pattern in his instructions well before it existed as a rule, and
in the meantime every session had to be told again.

So **sessions keep a track of what he asks them to do**, in `ASKS.md` in this
folder. Append-only, one entry per instruction, same shape as `LESSONS.md`. What
belongs in it is narrow:

- **Log instructions about *how work is done*** — process, sequence, what to
  show him, what to never do, what to ask before doing.
- **Not what to build.** "Add an export button" is a requirement and belongs in
  an issue. "Show me a mockup before you build anything" is an ask.
- **Log corrections too**, especially ones where he changed a decision he'd
  already made. A reversal says more about what he actually wants than the
  original instruction did.

**When entries rhyme, propose the rule.** Not automatically, and not on a count:
propose when you can state the general form in one sentence and point at two or
more distinct instances that it covers. If you cannot state it in one sentence,
you have a coincidence, not a pattern.

It goes through the normal route — a proposal, his decision, a PR. **Amending an
existing rule is usually the right shape**, not a new section: most patterns turn
out to be an existing rule that didn't reach far enough, and a second section
saying almost the same thing is how this file becomes unreadable.

**The obvious failure mode, stated plainly so it can be caught:** this rule
rewards finding patterns, and a session that wants to look useful can assemble
one out of any two instructions. Rules invented that way have no felt problem
behind them, and they are exactly the rules that get followed literally and
wrongly. **A pattern nobody was actually hurt by is not worth a rule.** If the
honest summary is "he mentioned two vaguely similar things", log both and say
nothing.

The log is not a rule change and needs no PR — but it is in this folder, so
entries are observations of what he said, never inferences about what he'd
probably want.

## Known gotchas on this Mac (not any one project)

- **`../common-rules/` does not resolve from a worktree.** Worktrees live at
  `<project>/.claude/worktrees/<name>/`, so the relative form points at
  `<project>/.claude/worktrees/common-rules/`. Use the absolute path,
  `/Users/the-sponsor/apps/common-rules/CLAUDE-workflow.md`, anywhere a session
  might be running from a worktree — which is everywhere, since a worktree is
  the first action on any project repo. Found 2026-08-04 in six finance-tracker
  issue briefs.
- **Transcript directories under `~/.agent-data/projects/` begin with `-`**, so
  `grep <pattern> *finance-tracker*/*.jsonl` silently reads the filenames as
  options and reports nothing found. It does not error. Prefix with `./` or use
  `--`. Found 2026-08-04, having briefly produced a confident and completely
  wrong conclusion about which sessions had read this file.
- **`gh auth login` can complete the actual GitHub OAuth handshake and then
  fail silently-ish on the last step** — `mkdir ~/.config/gh: permission
  denied` — if `~/.config` itself is root-owned (happens if some earlier
  tool was installed with `sudo`). Fix is
  `sudo chown -R "$(whoami)":staff ~/.config` and retry, or sidestep it
  entirely with `export GH_CONFIG_DIR="$HOME/.gh"` before `gh auth login`
  (no sudo needed, just remember to export it in any new terminal that
  uses `gh` on this machine unless that's also added to `~/.zshrc`).
- **Homebrew and `gh` may be installed but not on a headless/tool shell's
  `PATH`** — Apple Silicon Homebrew lives at `/opt/homebrew/bin`, which a
  fresh non-interactive shell doesn't always inherit. Check
  `/opt/homebrew/bin/gh --version` directly before concluding a tool isn't
  installed.

## Where these rules live, and who sees them

This file, plus each adopting project's own `CLAUDE.md` (which points here
and adds its specifics), read automatically by any Claude Code session
working in that project — a fresh session, a subagent, or a session resumed
inside one of the task worktrees above. It is *not* visible to other AI
tools (ChatGPT, other coding assistants) unless they're separately pointed
at these files or a tool-specific equivalent — there's no cross-tool
standard yet that reads them automatically. This folder is its own git
repository (`github-owner/ai-common-rules`, private) — deliberately separate
from every project's history, since `apps/` itself isn't a repo and these
rules belong to none of the projects individually. `CHANGELOG.md` in this
same folder is still what documents *why* these rules changed; keep it up to
date on every edit here, and commit alongside it rather than relying on
`git log` alone to explain a change.
