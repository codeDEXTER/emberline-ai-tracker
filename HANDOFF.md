# common-rules — start here

This file is read first, in every session, before any other action. The read
order is the one `.common-rules.json` declares: `CLAUDE.md`, this file, then
`docs/OPERATING-RULES.md`, the ledgers in `docs/proposals/NN-*.json`, the latest
`docs/handovers/*-checkpoint.md`, then `CLAUDE-workflow.md`. The standard was
seeded here on 2026-09-14 (proposal 21, S-10).

common-rules is the shared workflow standard for every project under
`/Users/aashish/apps`: the rules (`CLAUDE-workflow.md`), the tools (`bin/`), the
templates, and the `/warmup` and `/standard` skills. It is **not** a project
with a product. Each project under `/Users/aashish/apps` is its own repository,
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
