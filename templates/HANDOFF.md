# {{PROJECT}} — start here

Seeded {{DATE}} from the common-rules warm-up standard (proposal 19,
`docs/proposals/19-proposal-warmup.html`). This file is read first, in
every session, before any other action — `/warmup`'s read order is this
file, then `docs/OPERATING-RULES.md`, then `{{PLAN_LEDGER}}`, then the
latest `docs/handovers/*-checkpoint.md`, then the shared `CLAUDE-workflow.md`.

One paragraph here: what {{PROJECT}} is, what it deliberately is not, and
where any adjacent project (an interface, a companion repo) lives and is
worked on separately, so a new session does not reach across that line by
accident.

---

## Start here

{{ORIENTATION}}

---

## Prohibitions, verbatim

Two prohibitions, non-negotiable. State them exactly as written below in
every brief that touches the area they cover — never paraphrase them, and
never let a session infer a looser version from the shape of a task.

**1. {{PROHIBITION_1}}** Example of the shape a violation takes: a job run
on a mistaken assumption wrote into the real data store and had to be
restored from a backup afterwards.

**2. {{PROHIBITION_2}}** Example of the shape a violation takes: a process
was ended by a name pattern that also matched something the sponsor was
using at the time.

---

## Standing rulings

Every sponsor ruling below is marked one of two ways, and the two are never
blurred into each other:

- **VERIFIED** — his own words, quoted directly, with where the quotation
  comes from (a transcript, an issue, `SPONSOR-CONSTRAINTS.md`). Anyone who
  reads the source can check a VERIFIED ruling against it.
- **[INFERRED]** — the substance is very likely correct, but the specific
  wording recorded is not a direct quotation of his. Marked this way so a
  later session does not repeat it as something he said when it is not.

A ruling carrying neither mark is a mistake in this file, not a ruling —
fix the mark, do not delete the ruling.

- **{{RULING_1}}.** VERIFIED, his words: *"{{RULING_1_QUOTE}}"*.
- **{{RULING_2}}.** [INFERRED — {{RULING_2_NOTE}}].

---

## State, measured

| What | Value | Command | Date |
|---|---|---|---|
| {{MEASURE_1}} | {{VALUE_1}} | `{{COMMAND_1}}` | {{DATE}} |
| {{MEASURE_2}} | {{VALUE_2}} | `{{COMMAND_2}}` | {{DATE}} |

Every row is a measurement, not a promise: re-measure before repeating a
number, and mark a row that has not been re-measured since something moved
rather than carrying it forward as fact.

---

## Plan of record

`{{PLAN_LEDGER}}` is the plan of record — a JSON ledger, validated by
`tools/tracker/ledger.py` and rendered to a page by `bin/tracker render`.
Never a second plan document; a revision adds rows and corrects numbers in
place, it does not scrap old content. Superseded measurements stay, marked
as superseded, rather than being deleted.

---

## How to verify

`{{TEST_COMMAND}}`. Never a browser for verification unless the interface
itself is a browser — browser verification has manufactured defects that
did not exist on other projects and missed real ones. Make every new test
fail against the current code first, and say in the report that you did;
a green test whose setup is load-bearing on the defect it should catch has
proven nothing.

---

## What good looks like

{{GOOD_LOOKS_LIKE}}

When you finish something, say what you verified and what you could not.
Do not certify your own work as done — that is the test engineer's and the
quality manager's call.
