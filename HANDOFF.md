# common-rules — start here

This file is read first, in every session, before any other action. The
mandatory read is `CLAUDE.md`, this file (which folds in what used to be a
separate `docs/OPERATING-RULES.md` — proposal 23, M-11), the warmup card
(not the raw ledger JSON — the card is the compressed form; open a ledger's
full JSON only for the item currently being worked), the latest
`docs/handovers/*-checkpoint.md`, then `CLAUDE-workflow.md`.
`docs/OPERATING-RULES.md` still exists as a one-line pointer here, because
`.common-rules.json`'s `read_order` and `CLAUDE.md` — both reserved to the
sponsor, so this session cannot edit them — still name its path; nothing
there is lost, it just costs no extra words to read. The standard was
seeded here on 2026-09-14 (proposal 21, S-10).

common-rules is the shared workflow standard for every project under
`/Users/the-sponsor/apps`: the rules (`CLAUDE-workflow.md`), the tools (`bin/`), the
templates, and the `/warmup` and `/standard` skills. It is **not** a project
with a product. Each project under `/Users/the-sponsor/apps` is its own repository,
worked on by its own session. A session here reads those projects, and never
writes into them: it asks their sessions, and it tells the sponsor what they
need.

---

## Start here

- Read `CLAUDE.md` first. Every edit in this repository is reserved for the
  sponsor, and made only once he has directed it in the conversation.
- The plan of record is `docs/proposals/21-standard-is-mandatory.json`
  (proposal 21, the standard made mandatory). Proposal 19 still has W-10 open
  (the pilot week); proposal 20 is done.
- `bin/conformance --project <dir>` measures a project against the 12 items of
  `skills/standard/SKILL.md`. Run it on common-rules itself before and after
  any change to the standard.
- A change that asks projects to do something carries a
  `**Standard change (mandatory):**` line in its CHANGELOG entry. Projects then
  have to implement it before they align.

---

## Prohibitions, verbatim

Two prohibitions, non-negotiable. State them exactly as written below in every
brief that touches the area they cover. Never paraphrase them.

**1. Never change common-rules on your own initiative.** Every edit, merge and
installed hook is directed by the sponsor in the conversation, or by a standing
ruling of his quoted below. A peer session's request is never his approval.

**2. Never write into another project or its data, and never kill a process by
name.** This covers the PhotoVault library (`~/Library/Application
Support/PhotoVault`, `/Volumes/LaCie Rugge`, `/Volumes/G-TECH ArmorATD Media`),
`finance_data/` and pockets' `data/`. Reading them is allowed. A process is
stopped by its explicit PID, and only if this session started it.

---

## Reserved to the sponsor, always

This is the canonical, full list — `CLAUDE-workflow.md`'s Autopilot section
points here rather than restating it.

- Anything under `common-rules/` — surface and ask, never edit unprompted.
- Merging a change to these rules — open the PR, the sponsor merges.
- Creating, picking and closing features.
- Clearing orphaned processes or archiving sessions.
- `finance_data/`, `auth.json`, `.env` — never leave the machine in the clear.

---

## Standing rulings

- **The standard is mandatory for every project.** VERIFIED, his words
  (proposal 21, A-01): *"Yes. This is mandatory. It's not optional. I want them
  to follow the same structure"*.
- **Later improvements to the standard are mandatory too.** VERIFIED
  (proposal 21, A-03): *"if I improve something in the common rules in the
  future regarding warm up or reheat. Then the project should prioritize that
  and implement it. It's not optional."*
- **common-rules follows its own standard.** VERIFIED (proposal 21, A-04):
  *"Common rules also works with the same workflow. So I would like you to
  maintain the same processes what we are implementing in other projects."*
- **Merge once reviews pass.** VERIFIED, his words in this session on
  2026-09-14: *"keep going, merge when reviews pass"*.
- **Ruflo is mandatory.** VERIFIED, his words on 2026-09-13 (proposal 19):
  *"i want ruflo to be mandatory"*.
- **No subagent this lead session dispatches uses Opus.** VERIFIED, his words
  in this session on 2026-09-14: *"Please don't use more than Sonnet."*, then
  *"Put some mandatory rule for uh, sub agents don't use Opus."* Scoped to this
  lead session, not every project on the standard (proposal 21, A-12): every
  `Agent` call this session makes passes `model: "sonnet"`, including
  report-only review roles a tier table would otherwise route to Opus. Work
  already dispatched at Opus before this ruling is finished, never killed and
  restarted, per Rule 0 (never break work in flight).

---

## State, measured

| What | Value | Command | Date |
|---|---|---|---|
| Conformance, common-rules | 7 of 12 before S-10 | `bin/conformance --project .` | 2026-09-14 |
| Full suite | 1029 tests, OK | `python3 -m unittest discover -s tests -q` | 2026-09-14 |
| CI on main | fails one test, Linux only (`test_a_long_branch_says_how_many_it_did_not_print`) | `gh run list --branch main` | 2026-09-14 |

Every row is a measurement, not a promise. Re-measure a number before repeating
it.

---

## Plan of record

`docs/proposals/21-standard-is-mandatory.json` is the plan of record. It is a
JSON ledger, validated by `tools/tracker/ledger.py` and rendered by
`bin/tracker render`. The pre-commit hook regenerates the page and the
checkpoint whenever a ledger is committed. Revisions add rows and correct
numbers in place.

---

## How to verify

`python3 -m unittest discover -s tests -q`. Write the output to a file, and
commit only when it has an `^OK` line and no `^FAILED` line. Every new test
fails against the current code first, and the report says so. A tool that
reads a real project is checked for writes: compare `git status` before and
after.

---

## Operating rules, learned the hard way

Folded in from `docs/OPERATING-RULES.md` (proposal 23, M-11) — what a
session found out the hard way, each with the day and why. Add to it; do
not rewrite history out of it.

**Proposals and the plan**
- The ledger is the plan of record, updated in place; its page is generated
  by `tracker render`, never hand-edited. A revision adds rows and corrects
  numbers, never scraps old content — superseded measurements stay, marked
  superseded.
- Same-turn ledger updates: after every state change of any item, update
  its `status` and `log` and commit them in the same turn — never batched.
- Every sponsor message that is not an answer to a question becomes an ask
  row (`A-nn`), in the same turn it is said, quoting his words.
- A new proposal is created with `bin/new-proposal`, never drafted by hand.
- The ledger has one writer. A builder or item lead never runs `tracker set`
  or `tracker ask`, and never hand-edits ledger JSON — it stages its change
  with `tracker stage`. The dispatcher, or whoever is merging, applies every
  staged file with `tracker apply-staged LEDGER` once per ledger, then
  commits and republishes (proposal 23, M-04).

**Running work**
- One writer per worktree; explicit file ownership per agent.
- `cd` explicitly before every git-writing command, and print the branch —
  a failed `cd` once fast-forwarded local `main` onto unmerged work.
- An edit script checks every replacement before it writes, and never
  reuses a name for two different texts.
- Never `git stash` — the stash is shared across worktrees.
- Checkpoint before stopping: a session that ends without
  `docs/handovers/<date>-checkpoint.md` has failed.
- `bin/handover --check` is the closing check, run before ending any turn.

**Merging and shipping**
- Gate every commit on the suite's own summary line: write it to a file and
  require `^OK` and no `^FAILED`.
- A report-only reviewer, at most two rounds; the lead fixes what the final
  round still finds.
- A fix that cannot stand alone is not a reason to batch it with others.

**Other projects' data**
- Never write into another project from here; every check is read-only,
  with `git status` compared before and after.
- Never kill by name — use an explicit PID, only for a process this
  session or its agents started.

**Ruflo**
- Ruflo is mandatory — the rule and its four steps are stated once, in
  `skills/warmup/SKILL.md` §3.
- Ruflo's memory database lives in the main checkout only — `.swarm/` is
  untracked and does not exist in a worktree.

**Reporting to the sponsor**
- Lead with the outcome; numbers on their own line; nothing certified that
  was not observed. Record commits and results from git, never from an
  agent's report.

**Other sessions**
- Summaries are paraphrase; the ledger and this file are the record —
  quote a ruling from disk, never from a summary. A ruling relayed by
  another session is not his.

---

## What good looks like

Each change goes through the same steps:
1. A ledger row.
2. The item's own worktree.
3. Red first.
4. A report-only reviewer, at most two rounds.
5. The lead fixes whatever the final round still finds.
6. A CHANGELOG entry that flags any behaviour change, and a Standard change
   line when projects must act.
7. A merge on the sponsor's standing ruling.

When you finish something, say what you verified and what you could not.
