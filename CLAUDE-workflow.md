# Shared workflow rules

Common to every project under `/Users/the-sponsor/apps/`. A project adopts them by
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
common-rules/bin/derecord /Users/the-sponsor/apps/<project>
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

## AGENT-LOG.md — what a task cost

This one is not bookkeeping for its own sake: it is how the user sees where
spend goes, and the measurement that produced this rewrite came from it plus
the session transcripts.

Every task appends **one** entry when it lands, written by `bin/spend`:

```
common-rules/bin/spend log <issue-or-task-name>
```

which records the date, the task, which agents were invoked and how many times,
the output tokens the session spent, and the commits that landed. One entry per
task, not one per step. `bin/spend report` totals it across a project, and
`bin/spend report --by-agent` says which roles are expensive.

If an entry would take longer to write than the work it describes, the entry is
wrong, not the work.

---

## Autopilot — the operating mode

The user owns **features**. The AI owns **issues**.

Creating, scoping, prioritising and closing a *feature*, and saying yes to a
proposal, are the user's calls. Everything downstream — cutting issues,
sequencing them, resolving disagreements between sessions, choosing between
implementations, deciding what to research — is the AI's job, done without
asking.

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

Defined in `agents/*.md`, registered from `~/.agent-data/agents`. Invoke with the
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

**Then, if a decision is genuinely needed**, ask with buttons
(`AskUserQuestion`) — one question, options that differ in what gets built. If
no decision is needed, skip the buttons entirely.

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

**One installed app per project, ever.** There is exactly one bundle in
`/Applications` for a project, built from `main` and refreshed after a feature
merges. A worktree build is a *development* copy: it carries a distinct name and
icon, never installs itself, and never overwrites the installed one. Two bundles
claiming to be the same app is a bug — `bin/appcheck` finds them.

Never run `build_macapp.sh --install`; never touch `/Applications` directly.

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
- Directories under `~/.agent-data/projects/` start with `-`, so a globbed `grep`
  reads them as flags and silently finds nothing. Use Python `glob`.
- Temp files go to the session scratchpad, never to `/Users/the-sponsor/apps/`.
  Verify the `cd` succeeded — a failed one writes into the repo.
