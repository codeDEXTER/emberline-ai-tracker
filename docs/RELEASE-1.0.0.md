# common-rules 1.0.0

The first baseline of the standard. A project that adopts this tag gets a
fixed target instead of a moving `main` — which matters, because the reason
this release exists is that the standard had outrun every project following
it (finding 21/F-02).

Cut on a green `main`: all twelve conformance checks holding, the card
reading ready, and the full suite passing.

## What a project gets

**One card, one order.** `/warmup` on a fresh session, `/reheat` on a running
one. Both read HANDOFF.md, the operating rules, the ledger and the last
checkpoint in a fixed order, run the twelve conformance checks in process,
and print the card before any work. Anything typed after the command is
carried through as context.

**A ledger that is the record.** Items with a status, a size (value, points,
risk) and a routing tier; lettered parts for anything that cannot reach 100%
in one go, nested to three levels; findings as rows; asks that record the
sponsor's own words. Pages are generated from it and never hand-edited.

**A tracker page.** Proposals expand to items, items to parts, parts to
sub-parts. One filter bar over four views — tree, Kanban, board, list — with
a Pending filter that reaches inside the dropdowns. Progress over time is
computed from the ledgers' own git history, never written by a model.

**A gate that is fast enough to sit through.** `bin/quiet --jobs auto` shards
the suite across processes and splits within a slow file, and reports one
verdict line read from the runner's own summary rather than its exit code.
Measured on this repo: **965.6s serial to 201.5s**, 1,853 tests.

**Tools that replace bookkeeping, not judgment.** `bin/commit-if-green`,
`bin/pr-body`, `bin/item-notes`, `bin/worktree-sweep`, `bin/workflow-stamp`,
`bin/ruflo-item` (several ids per call, and `from-ledger` to backfill),
`bin/land`, `bin/handover --check`, `bin/spend`, `bin/conformance`,
`bin/rulecheck`.

**Rules with a measured reason.** A gate runs in the foreground and is never
polled; briefs dispatch in one message; builders run affected tests and the
full suite runs once at integration; the lead runs on Opus and subagents
never do. Each of these exists because something was measured, and the
CHANGELOG entry says what.

**A staging branch, available and off by default.** A project may declare
`staging_branch`; reviewed work lands there, the full suite runs there, and
`main` only fast-forwards from a green staging. Undeclared, nothing changes.

## What is deliberately not in 1.0.0

**L-07 is at 80%, on the back burner.** "Use the existing tool, not an inline
copy" — the rule is in the briefs and its measurement fails: `cat`/`sed -n`
reads are 9.54 per 100 tool calls against the 6.40 that would count as
halved, and the figure moved backwards since the interim reading. The
sponsor ruled on 18 Sep 2026: "L7 will remain on back burner". Shipping an
honest 80% with a recorded reason is better than a version that never cuts.

**Adoption is not included, because it cannot be.** W-10, S-07 and S-08 are
items owned by other projects' sessions. This repo is prohibited from writing
into another project, so a release of the rulebook cannot carry the work of
adopting it. `docs/handovers/2026-09-18-adoption.md` has the per-repo table
and the shortest path.

**V-03, the lock, is not in this release.** `.common-rules-version` still
holds the bare `<count>-<sha>`. Recording which mandatory entries a project
has implemented — so `rulecheck` can name what is pending rather than saying
"behind" — lands in 1.1.0.

## Adopting it

In the project, not here. Each project's own session owns its ledger.

1. `/standard`, then the twelve-item checklist in `skills/standard/SKILL.md`.
2. `bin/warmup --project . --migrate --dry-run`, read it, then run it for real.
3. `bin/rulecheck --project . --mandatory`, queue each entry as a ledger item
   owned by `lead`, implement, then `--align`. It refuses while any mandatory
   entry is pending, by design.
4. `bin/warmup --project . --check` reads ready before new feature work.

## Versioning from here

`VERSION` holds the semver; `.common-rules-version` holds the
`<count>-<sha>` that orders two versions unambiguously. The bump rule:

- **MAJOR** — breaks a project already following the rules. Declared with a
  `**Breaking change (major):**` line in the CHANGELOG entry, never inferred.
- **MINOR** — any entry carrying `**Standard change (mandatory):**`.
- **PATCH** — everything else.

`bin/version-check --check` runs in the merge gate and fails when `VERSION`
and the CHANGELOG entries since the last release disagree, so the number
cannot drift from what the changelog says happened.
