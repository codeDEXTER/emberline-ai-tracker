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
/ `completed`. Name the implementing issues as `issue #N` — that is what makes a
percentage computable, and it is read separately from `blocked by`, which is a
dependency and never progress. `completed` is the word for fully finished —
`done` is a grandfathered synonym, not mass-renamed where it's already written,
but write `completed` from here on (same convention as proposal-status's own
`built` → `completed`, 2026-08-20). `built` keeps its own, narrower meaning here
— shipped but not yet closed — and is not folded into `completed`.

**This is not a per-task obligation.** It changes when the sponsor adds, renames
or closes a feature — which is rare, and is his act rather than a session's.
Nothing here asks a session to append anything when work lands: that was
proposal 08's logbook, and it was rejected for exactly that reason.

A project with no register is reported as **"no features declared"**, never as
0% — undeclared scope is a different statement from none of it done.

**And every project keeps a milestone plan.** A `## Milestones` table in the same
`CLAUDE-checklist.md`: the order of work, and — the column that earns the table —
**what each step proves**.

| # | Milestone | Proves | You get | State |
|---|---|---|---|---|
| 1 | One corpus indexed, answering a question | retrieval is good enough to build on | nothing to hold | completed |
| 2 | The model timed on the real phone | the felt speed, and so the retrieval budget | nothing to hold | in flight |
| 3 | The first real screen, on the device | the design survives contact with a hand | **an app you can use, one corpus** | next |

Same states as the register — including `completed`/grandfathered `done` for a
milestone that is fully finished, not just `built` and shipped. The register
says what the product is made of; this says **what order, what each step
establishes, and when the sponsor gets something he can hold.**

**Three disciplines make it worth the row.** A milestone ends in something *proven*,
not something delivered — "the index builds" is a task, "retrieval is good enough to
build on" is a milestone. **The result that would stop the plan is written before the
work starts**; written afterwards it is a rationalisation of whatever the data
happened to say. And **every row states what the sponsor gets, including when the
answer is nothing** — a plan whose first four steps hand him nothing is a fine plan,
but he should be told that at the start rather than discover it in week three.

Measured on `pocket-internet`, 2026-08-20: the first milestone was five cheap
verifications named in advance. Three ran — two confirmed an estimate and one
corrected a verdict that had already propagated into two proposals. Twenty minutes,
and it changed a conclusion that eleven passes of reading had not.

**One optional column: `Track`.** A project running genuinely parallel work —
finance-tracker has correctness and surfaces moving at the same time — names a track
per row, and the picture below draws one lane per track instead of one rule. Leave it
out and nothing changes; a project with a single thread of work should not pay for the
concept. Tracks are drawn in the order the plan first mentions them, never sorted, and
each lane carries its own *here*: with parallel work there is no single front, and
collapsing them to one would assert an ordering between lanes the plan never claimed.

**And the plan has a picture, generated — `docs/milestones.html`.** `bin/milestones`
reads the table above and renders it: the lanes, the states, and a marker wherever
something reaches the sponsor's hands. Run it after any change to the plan; `bin/land`
refuses a project whose page is missing or stale, on the same opt-in guard as the other
gates.

The page is **generated, never written**. That is the whole design: a hand-maintained
second copy of the plan is the failure this rule already warns about, with extra steps —
the table and the picture drift, and the picture is the one people look at. Staleness is
checkable because the page carries a digest of the plan's content, so the check asks
"does the picture still show this plan" rather than comparing bytes, which a generation
timestamp would defeat. Anything typed into the page is lost on the next run, and that
is the point.

**It is a live document, kept current until the feature is done.** A milestone plan
that is not maintained is worse than none, because it asserts an order of work that
has stopped being true and nobody can tell which rows still hold. Three things move
it, and only three:

- a milestone's **state** changes;
- a milestone's **proof lands** — and if the result differs from what was predicted,
  the row records what actually happened rather than being quietly rewritten;
- the **order changes**, because a proof came back badly enough to reorder what
  follows.

**Still not a per-task obligation**, same guardrail as the register. Those three
events happen a handful of times across a whole feature, not once per task, and
nothing here asks a session to append anything when work lands. This is deliberately
not proposal 08's logbook, which was rejected for exactly that reason. The test is
simple: if a session is editing the plan because it *did* something, that is the
logbook and it is wrong; if it is editing because something is now *known*, that is
the plan and it is right.

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
before a word is read. Status is one of `proposed`, `accepted`, `completed`,
`completed in part`, `amends NN`, `superseded by NN`, and lives in
`<meta name="proposal-status">`. `built` is a grandfathered synonym for
`completed` — two proposals already use it and are not mass-renamed, but write
`completed` from here on. An unnumbered proposal is not a proposal; it is a
sketch.

**A proposal that asked numbered decisions must record the answers.**
Measured in finance-tracker (issue #584): 11 proposals `accepted`, 9 carrying
a decision date (`<meta name="proposal-decided">`), 3 recording what was
actually decided — and those three were hand-written the day the gap was
noticed. A date says *when*; it says nothing about *what*, and
`proposal-auditor` has nothing to measure a build against without the answers.
Scoped mechanically, not by taste: a proposal whose `<ol class="decisions">`
list asked something must carry the answers, in the same document, in a block
a reader can find (`id="decided"` — proposal 18, portfolio-pdf, already does
this by hand) before it reaches `accepted`, `completed`, `completed in part`,
or the grandfathered `built`. A proposal that asked nothing needs nothing —
"did it ask?" is checkable, "is it big?" is not.

**A proposal reaches a terminal state — `completed`, or `completed in part`
with its exceptions named.** `completed in part` requires an `id="exceptions"`
block beside the decisions: what was not built, and why. A status claiming
partial completion with nothing named is indistinguishable from quietly
marking something done — the block is what keeps it honest. `built` remains
the grandfathered word for full completion; `completed in part` is new
vocabulary with no prior use to reconcile.

**Grandfathered by decision date, not by list.** Both requirements above bind
proposals decided on or after **2026-08-19**, the day this rule was written.
A proposal decided before that date, or carrying no `proposal-decided` date at
all, is exempt — undated reads the same as "decided before this rule
existed," not as a loophole to leave the meta off going forward.
finance-tracker alone has 8 accepted proposals whose answers are
unrecoverable; inventing them would misstate history worse than the gap does,
and a test that fails on day one against documents nobody can fix gets
disabled. `bin/proposalcheck --project <dir>` is the mechanical form of both
rules and this grandfather; it currently reports 0 blocked proposals across
finance-tracker, mac-explorer, pockets and pip — finance-tracker has 4 that
would fail without the floor (20, 23, 24, 25), all dated before it, so
enforcement is forward-only from here.

**A document is either a proposal or an artifact, and the difference is
whether it carries a status.** A **lead** — a document with no
`<meta name="proposal-part-of">` — is the one thing in its topic asking for
a decision, and must carry a `proposal-status` from the vocabulary above. A
**section** — `part-of` some lead — is supporting material with nothing of
its own to decide (an exploration, a findings run, a design-explorer's
parallel concepts shown side by side before a direction is picked): it
carries no status at all, because there is only ever one decision per
topic, and the lead is where it lives. Six parallel spending-UI concepts
from one design-explorer run (finance-tracker, 2026-08-20) had nowhere to
go but loose, unnumbered `claude.ai` links until this was made explicit —
`NN-<type>-<slug>.html` already had a real answer (make each its own
numbered section of one lead proposal), it just wasn't written down as a
rule anyone could check.

**Grandfathered the same way, a separate floor.** This binds proposals
touched on or after **2026-08-20** — its own day, not reused from the floor
above. `bin/proposalcheck` reports 0 blocked today: pockets carries one
lead with a typo'd status (`superseded-by 14` for `superseded by 14`,
decided 2026-08-04) and pip carries two undated leads with no status at
all — both grandfathered the identical way an undated or pre-floor proposal
already is above, not specially cased.

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
