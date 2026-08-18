# Shared workflow rules

Common to every project under `/Users/aashish/apps/`. A project adopts them by
pointing here near the top of its own `CLAUDE.md` and layering its specifics
(test command, build command, repo name) on top — never by copying this text in.

Adopted: **finance-tracker** (2026-08-02), **pockets** (2026-08-02).

This file was 1,637 lines and is now under 300. The cut was made on 2026-08-05
after measuring four days of real sessions: two thirds of all spend went to
talking about work rather than doing it, and every merge conflict that day was
in a file these rules had invented. What survived is what the measurement showed
was load-bearing. Process about process is gone.

**Rules that can be enforced are not written here.** They live in
`bin/derecord`, which installs them into a project as git attributes and hooks.
A rule the AI cannot break needs no paragraph. Run it once per project:

```
common-rules/bin/derecord /Users/aashish/apps/<project>
```

---

## The four things that actually work

Measured across 30 sessions and 29.2M output tokens, the gain came from these
and almost nothing else. Do not trade them away.

1. **A worktree per task.** Separate folder, separate branch, always — including
   for this repo. Sessions sharing a checkout overwrite each other's work.
2. **Tool grants, not instructions.** Only `code-engineer` holds Edit and Write
   over code. The other roles are structurally unable to change it, so no rule
   is needed to stop them.
3. **A gate that reads the diff before merge.** `quality-manager` verifies
   against acceptance criteria. It reports; it never fixes and never merges.
4. **Tests, run before landing.** `bin/land` refuses to merge a red branch.

---

## Git

Every chat gets its own branch and folder:

```
git worktree add -b <task-name> .worktrees/<task-name>
```

Never `git checkout -b` in a shared checkout — on 2026-08-05 that re-attributed
another session's uncommitted work mid-edit.

Commit as you go. Uncommitted work is invisible to every other session and to
`bin/whoelse`, which is how two branches end up building the same thing.

**Landing is automatic.** When a branch is done, run `bin/land`. It checks the
tree is clean, the branch is ahead, the merge is conflict-free, the tests are
green and nothing reserved was touched — then merges, through a PR where `main`
is protected. Nothing waits in a queue for the user to notice it.

**A project that has aligned before must stay aligned to keep landing.**
`bin/land` refuses when `.common-rules-version` names a version older than
current — the same signal `rulecheck` has printed all along, made load-bearing
instead of ignorable: a `SessionStart` hook's exit status does not stop a
session, so a stale project's every session got the failure and proceeded
anyway. Only a project that has actually run `rulecheck --align` at least once
is checked — pointing at this file from a `CLAUDE.md` alone is not the same
claim, so a project that never aligned is never blocked here. Fix it with
`rulecheck`, then `rulecheck --align` (which writes `.common-rules-version` but
does **not** commit it — commit it yourself), or, if the branch genuinely must
land first, `LAND_ALLOW_STALE_RULES=1`, recorded in the PR either way.

Nothing sits unmerged more than about two hours of working time. Long-lived
branches are the whole cause of the collision class: on 2026-08-05 two branches
independently created the same new file and independently rewrote the same
renderer, purely because both had been alive for days.

**Record files never conflict.** `CHANGELOG.md`, `AGENT-LOG.md`, `LESSONS.md`
and the checklist are union-merged by `derecord`, so when two branches both
append, both win. Never hand-resolve them — hand-resolving them on 2026-08-05
is what put conflict markers into three Python files and broke `main`. Never
make a commit whose only content is a record entry; append alongside real work.

---

## Tests — the probe you ran is the test

**One command, everywhere.** Tests live in `tests/`, and every project runs

```
python3 -m unittest discover -s tests -q
```

`bin/land` runs it before landing and CI runs the identical string, so a test
written once is enforced in both without anybody wiring anything up. Do not
invent a second command, a second directory, or a second runner: two commands
wearing one name is how a test passes locally and never runs in CI.

**Verification you performed lands as a test.** Measured on 2026-08-10:
**29% of every Bash call a session makes is a one-off verification probe** —
an inline script that proves something and dies with the session. There were
3,873 of them, against 106 from all eight agent roles combined. The proving is
already happening and the code is already being written; it is thrown away
afterwards.

So this is not a request to test more. When you write a snippet to check that a
bug exists, that a fix works, or that two things agree — **put it in `tests/`
instead of pasting it into a message.** It is the same code either way; only
the destination differs.

`bin/land` refuses a branch that changes code and touches no test. If a change
genuinely cannot be tested, say why and re-run with `LAND_ALLOW_UNTESTED=1` —
recorded either way.

**A guard nobody has watched fail is not known to be a guard.** Run a new test
against the broken state first and see it fail, then fix. Two tests written
this week passed against the very bug they existed to catch: one because a
`chdir` test ran from inside the directory it was checking, one because a
`grep -q "__pycache__"` matched a different line.

---

## AGENT-LOG.md — what a task cost

This one is not bookkeeping for its own sake: it is how the user sees where
spend goes, and the measurement that produced this rewrite came from it plus
the session transcripts.

**It is generated, never written by hand:**

```
common-rules/bin/spend agentlog --write
```

which reads the session transcripts and writes one row per task — when it ran,
what it cost, how many sessions, and which agents were invoked how many times.
Regenerate it after a task lands; never edit it. `bin/spend report` totals cost
per task, and `bin/spend report --by-agent` says which roles are expensive.

**Why generated, and not appended by hand.** The rule here used to be "append
one entry when the task lands", with `bin/spend log`. Ten entries were written
that way in finance-tracker and **not one carried the token figure the report
needed** — so `spend report` answered 0 for every row for a week, and nothing
noticed, because the tool had no test. A number that is only right when somebody
remembers to type it is not a measurement.

Generating it also takes the file off the merge surface. Every merge conflict on
2026-08-05 was in a record file this framework invented, and hand-resolving one
is what put conflict markers into `main.py` and left `main` unable to start.

`spend log` still exists for a hand-written note, but nothing reads its numbers.

---

## Autopilot — the operating mode

The user owns **features**. The AI owns **issues**.

Creating, scoping, prioritising and closing a *feature*, and saying yes to a
proposal, are the user's calls. Everything downstream — cutting issues,
sequencing them, resolving disagreements between sessions, choosing between
implementations, deciding what to research — is the AI's job, done without
asking.

**Every project keeps a feature register.** A `## Features` table in its
`CLAUDE-checklist.md`: one row per feature, linking the GitHub issue that *is*
the feature, with a state column. The Tower reads it — that table is the only
answer to "what is this product made of, and how much of it is done".

| # | Feature | State |
|---|---|---|
| [#2](…/issues/2) | Capture a document and see it filed | **in flight** — issue #1 |
| [#3](…/issues/3) | Import the backlog | blocked by #2 |
| [#8](…/issues/8) | Get it onto the second phone | version 2 |

States: `in flight` · `next` · `blocked by #N` · `later` / `version N` · `built`
/ `done`. Name the implementing issues as `issue #N` — that is what makes a
percentage computable, and it is read separately from `blocked by`, which is a
dependency and never progress.

**This is not a per-task obligation.** It changes when the sponsor adds, renames
or closes a feature — which is rare, and is his act rather than a session's.
Nothing here asks a session to append anything when work lands: that was
proposal 08's logbook, and it was rejected for exactly that reason.

A project with no register is reported as **"no features declared"**, never as
0% — undeclared scope is a different statement from none of it done.

**A question to the user is a cost, not a safety move.** Before asking, check
whether the answer would change what gets built. If either answer leads to the
same work, pick one, say which you picked, and continue. A question about
coordination between two sessions is never the user's to answer.

Ask only when:
- it is a feature-level call (what to build, whether to ship, what it is for)
- it touches money, data loss, or something outward-facing
- the answer is genuinely reserved (below)

**When there is nothing to decide, show no buttons.** Do the work and report it.

Reserved to the user, always:
- anything under `common-rules/` — surface and ask, never edit unprompted
- merging a change to these rules — open the PR, the user merges
- creating, picking and closing features
- clearing orphaned processes or archiving sessions
- `finance_data/`, `auth.json`, `.env` — never leave the machine in the clear

---

## Issues

Cut issues **vertically**. One capability end to end — never "backend for X"
and "UI for X" as two issues. That split produced the #30/#31 race: two
sessions, one capability, guaranteed conflict, and the user left as referee.

One issue in flight per **surface**, not per issue. Two issues that touch the
same file are one issue, or one queue.

Record dependencies when issues are created, not when they collide.

---

## Working alongside other sessions

Before starting, run `bin/whoelse`. It reports every worktree, what is
uncommitted in it, and how far ahead it is.

**Overlap is a stop, not a note.** If another session is on your surface, do not
proceed in parallel and do not ask the user which of you should win. Message it
with `mcp__ccd_session_mgmt__send_message`, agree who holds the surface, and the
other one queues.

A finding on another task's surface is a **handover**, not a note in a file: the
session that found it tells the session that owns it, and stops.

---

## The agent roles

Defined in `agents/*.md`, registered from `~/.claude/agents`. Invoke with the
Agent tool and an explicit type — naming the type is the whole mechanism:

```
Agent(subagent_type: "code-engineer", prompt: "...")
```

| role | for |
|---|---|
| `research-agent` | before a direction exists: precedent, options, tradeoffs |
| `requirements-engineer` | a chosen direction written down as testable criteria |
| `design-explorer` | several structurally different concepts, early |
| `design-engineer` | one locked direction turned into a buildable spec |
| `code-engineer` | building it — the only role that may write code |
| `test-engineer` | validating against the criteria, raising bug reports |
| `quality-manager` | the pre-merge gate; reports, never fixes, never merges |
| `proposal-auditor` | how far requirements and design drifted from the proposal |

A role never certifies its own work. The code engineer does not decide it is
done; the gate does. The gate does not merge; `bin/land` does.

**Escalation is bounded.** Code engineer and test engineer negotiate through at
most two rounds of bug reports. If they still disagree, the gate decides.

---

## Ceremony is opt-in

The full chain — research, requirements, design, proposal audit, L2 — runs only
on work the **user has flagged as a feature they care about**. It is not the
default, and never applies to every issue.

Everything else goes: issue → `code-engineer` → gate → `land`.

**This is measured, not preference.** Five arms built one frozen spec under five
process weights. All five scored 22/22; the arm running exactly this default did
it 2.4×–22.7× cheaper than the rest, and the heaviest arm was the slowest of all.
Argue for more process against that, not against a taste.
(`experiments/pockets-core/RESULTS.md`, branch `experiment/results`.)

The chain, when it does run:

1. A proposal, delivered as an HTML artifact, then a decision (below).
2. On acceptance: requirements, then design — never straight to code.
3. `proposal-auditor` measures the drift from what was accepted.
4. The project manager grants L2, or escalates to the user if the drift is
   material. The auditor measures; it does not decide.

**Research is triggered by conditions, not by taste.** Run `research-agent`
when: no direction has been chosen yet; the same problem has been solved twice
differently; a proposal names an unfamiliar technology; or the user asks
"should we build X". A task session created *from* a proposal has already had
its direction chosen — it does not re-research it.

---

## Talking to the user

**Show, don't summarise.** A proposal, a design or a result goes to the user as
a rendered HTML artifact, not a wall of text in chat. The user reviews by
looking. Do not ask them to read requirements prose.

**Number every proposal, and lead with the number.** Proposals live in
`docs/proposals/` as `NN-<type>-<slug>.html`, numbered sequentially per project,
never reused. The visible heading and the `<title>` both read
`NN · status · Title` — so the sequence and where a thing stands are legible
before a word is read. Status is one of `proposed`, `accepted`, `built`,
`amends NN`, `superseded by NN`, and lives in `<meta name="proposal-status">`.
An unnumbered proposal is not a proposal; it is a sketch.

**Then, if a decision is genuinely needed**, ask with buttons
(`AskUserQuestion`) — one question, options that differ in what gets built. If
no decision is needed, skip the buttons entirely.

**Ask before code, in one batch, and do not wait.** Collect what the spec leaves
undetermined, put it in one message, then pick a default for each and keep
working — recording what you picked and what it blocks. A question that blocks
nothing is recorded, not asked. The bake-off arm that did this logged six
questions, received no answers, and still finished; the control asked two and
silently resolved nine, which it happened to get right.

**Offer a demo before asking for a yes**, and before closing a feature. Say what
to open and what to click. The user should see the thing working, not read that
it works.

**When a session is finished, offer to close it.** Do not leave it idling.

---

## Verifying a change — in the browser pane, not in a real app

**Verify against the dev server in the in-app Browser pane.** It is DOM-aware,
gives console and network access, opens no window on the user's desktop, and
touches neither Safari nor Chrome. `preview_start` with the project's launch
config, then read the page, the console and the network calls.

**Do not build and open a `.app` to check ordinary work.** That was the old
pre-merge step 3 and it was wrong: `build_macapp.sh` produces a real macOS
window (WebKit — the Safari engine), so every verification left a window on the
user's screen and another bundle on disk. Four `Sangam.app` bundles accumulated
this way, all claiming the same identity.

Build a `.app` only when the change *is* the packaging — the native window, the
icon, the bundle, the launch path. Then build with a mode
(`RUN_MODE=dev ./build_macapp.sh`) so it gets its own identity, and delete the
bundle when done. Never `open` a URL on macOS from a session: that launches the
user's default browser.

---

## Running apps — one copy, one icon

`bin/apprun` owns every running copy, keyed on `CLAUDE_CODE_SESSION_ID`:

```
apprun start <project>      apprun list      apprun stop      apprun sweep
```

A session stops only what it started. `apprun sweep` clears dead entries.

**Start servers through `apprun`, or adopt them.** Every command also looks for
app processes running out of `apps/` that no entry covers, and shows them as
UNREGISTERED — they have no owner, so they are orphans and only the user may
clear them. If you started one by hand, `apprun adopt --port N` makes it yours
to stop when your task ends. Starting a server directly is not the problem;
leaving it unclaimed is. Before this, `list` reported a clean machine while two
copies were up, because the registry only knew what it had been told.

**Install from `main` at the end of every feature.** When a feature is done —
not each issue, the feature — check out `main`, pull, run the suite, and install:

```
git checkout main && git pull
python3 -m unittest discover -s tests -q     # or the project's own command
./build_macapp.sh --install
```

The installed app is what the user actually opens, so a feature that is merged
but not installed is a feature they cannot see. Never install a red build: if
the suite fails, an old working app beats a new broken one — say so and stop.

**One installed app per project, ever.** There is exactly one bundle in
`/Applications` for a project, and it is built from `main`. A worktree build is
a *development* copy: it carries a distinct name and identifier, and
`--install` is refused from anywhere but a stable build. Two bundles claiming
one identifier is a bug — macOS keys on `CFBundleIdentifier`, so that is not two
copies but one identity with two bodies, and which one opens is undefined.
`bin/appcheck` finds them; it should always report every identifier unique.

Never touch `/Applications` by hand — `--install` is the only path in, and it
removes its own staged copy from `dist/` so the install cannot leave a duplicate
behind.

---

## Seeing the state

- `bin/pulse` — snapshot page: features, issues, worktrees, rules alignment
- `bin/tower` — live view: session graph, pipeline, event ticker
- `bin/spend` — what tasks and agents have cost
- `docs/workflow.html` — the bird's-eye map

`pulse` and `tower` bind to **127.0.0.1 only**. They render private session data
and are never published as an artifact.

---

## Changing these rules

Reserved for the user. The AI surfaces a proposed change and opens a PR; the
user merges. Never edit `common-rules/` unprompted, including `agents/`.

`ASKS.md` logs process asks. When the same ask appears three times, propose a
rule — once, as a PR.

Adding to this file is a cost. It was cut from 1,637 lines because its length
was making it go unread. A new rule must either replace something, or be
enforceable by `derecord` — in which case it belongs in code, not here.

---

## Known gotchas on this Mac

- Plain `git` is broken pending an Xcode licence. Use
  `/Library/Developer/CommandLineTools/usr/bin/git`.
- Directories under `~/.claude/projects/` start with `-`, so a globbed `grep`
  reads them as flags and silently finds nothing. Use Python `glob`.
- Temp files go to the session scratchpad, never to `/Users/aashish/apps/`.
  Verify the `cd` succeeded — a failed one writes into the repo.
