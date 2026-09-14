---
name: standard
description: The sponsor's mandatory instruction to put this session and its project on the common-rules standard (proposals 19, 20 and 21), and to implement every later Standard change to it first. The sponsor types /standard himself, so it is his ruling in this session, not a relay from another session. The session states when it will refactor, then refactors to one fixed checklist shared by every project.
---

# /standard: adopt the common-rules standard (mandatory)

The sponsor typed this command in your session. It is his own instruction here, with the same authority as if he had written it out: **the common-rules standard is mandatory for this project, not optional.** Do not ask whether to adopt it. Ask only the questions the steps below reserve for him.

`RULES` is `/Users/the-sponsor/apps/common-rules`. Every project under `/Users/the-sponsor/apps` follows the same steps, so every session speaks the same language: one ledger shape, one card, one proposal shape, one way to ask another session for something.

## 0 Never break work in flight

Do not refactor mid-item, mid-merge, or during a gate or receipt run. Finish the item in flight, or bring it to a clean, committed point first. Your project's own safety rules outrank everything in this command.

## 1 Answer now, in your reply to this command

1. **Project.** The project or projects this session works on, by path. If the session started in a folder above the project, say so. Hooks load from the folder a session starts in.
2. **In flight.** What is running now: ledger ids, agents, gate or receipt runs.
3. **Refactor stage.** The exact point after which you will refactor, named by work, not by clock: "after F-02c merges and its full gate is green". Pick the nearest clean point. Do not wait for a whole phase unless an item in flight truly needs it.
4. **Where you stand now.** If `RULES/bin/conformance` exists, run `RULES/bin/conformance --project <dir>` and paste its summary. If it does not, run `RULES/bin/warmup --project <dir> --check` and `RULES/bin/rulecheck --project <dir>`, then mark each checklist item in section 2 as holds, does not hold, or waiting on common-rules.
5. **Record it.** In the project's ledger, add:
   - An ask: `kind` decision, `state` answered, `quote` "/standard: the common-rules standard is mandatory", `at` the real clock.
   - One item for the refactor: the next free id in your plan, `status` not started, `owner` lead, and `depends` on the item in flight.

   Commit the ledger by path. If the project has no ledger yet, say so. Checklist item 2 creates one.

Then carry on with your current work.

## 2 At the stage you named: refactor to this checklist

Every item is mechanical, so the report can prove it. If a tool below is not in `RULES` yet, mark that item "waiting on common-rules". Never invent a substitute, and re-check at your next `/warmup`.

1. **Rules read and implemented.** Read `RULES/CHANGELOG.md` since your `.common-rules-version` stamp. Implement every `Standard change (mandatory)` entry, as section 3 describes. Then run `RULES/bin/rulecheck --project <dir> --align` and commit the stamp.
2. **Migrated.**
   - Run `RULES/bin/warmup --project <dir> --migrate --dry-run --at <now>` and show the output to the sponsor.
   - Then run it without `--dry-run`. Skip this when the card already reads the project's ledger.
   - A plan that is not yet a ledger becomes one: `RULES/bin/tracker import`, or a conversion script of the project's own that ends with `tracker validate` passing.
3. **Declared.** `.common-rules.json` names:
   - `read_order` and `safety_rules` (a file and its heading);
   - `gates.quick` and `gates.merge`, where the merge gate is what `land` runs;
   - `plan_check` and `plan_page` when the project has its own generator.

   `warmup --check` reads ready.
4. **Installed.** Re-run `RULES/bin/derecord <dir>` so the project has:
   - the pre-commit hook that regenerates the page and checkpoint;
   - the checkpoint hooks;
   - the Agent tag reminder;
   - the Ruflo runtime ignore lines.

   It prints any already-tracked runtime files together with the `git rm --cached` command. Ask the sponsor before untracking them.
5. **Lead prompt.** Regenerate the lead prompt from `RULES/templates/lead-prompt.md`.
   - Carry every project-specific rule into its project sections: safety, test speed, receipts, model routing, whatever the old prompt had.
   - Keep the old prompt under `docs/handovers/superseded/`.
   - List anything you dropped in your report, and why. Drop nothing silently.
6. **The ledger speaks the common language.**
   - Every blocked row and every open decision ask carries `owner`: `sponsor`, `lead`, or `session:<name>`.
   - Anything needed from another project's session is a `requests` entry (`RQ-NN`, `from`, `to`, `state`, `unblocks`), not prose in a report or a `proposed_changes` entry.
   - Model routing lives in exactly one table in the ledger (`tiers` or `model_routing`).
   - Every row carries its `[ruflo · tier · model]` tag.
   - Declare `readiness_weights` if the project computes readiness.
   - When the sponsor switches something off, record it in `switches` with `by` and `at`.
7. **Proposals.**
   - Create every new proposal with `RULES/bin/new-proposal`, which writes the page and its ledger in the checked shape.
   - `RULES/bin/proposalcheck --project <dir>` is clean for every proposal numbered after the declared legacy floor.
   - Older proposals are grandfathered, never rewritten.
8. **No hand-kept duplicates.**
   - A page generated from a ledger is regenerated, never edited.
   - A hand-kept document mirroring a ledger (a `.md` twin, a hand-updated artifact) is either retired, with a one-line pointer to the ledger, or declared as `plan_page`.
9. **Ruflo around every item.** Use `RULES/bin/ruflo-item start | done | note | recall`, with `RUFLO` and `RUFLO_NAMESPACE` set so the project's existing memories stay reachable. A project wrapper that stores the same keys also counts.
10. **Publishing.**
    - Record a published tracker or plan page with `RULES/bin/tracker published`, adding `--page` for a declared `plan_page`.
    - Commit the sidecar on its own.
    - Do not log the republish in the ledger.
11. **CLAUDE.md pointer.** The migration writes the warm-up pointer block between `<!-- common-rules:warmup -->` markers, using the declared read order. CLAUDE.md belongs to the sponsor.
    - Show him the diff.
    - This command authorizes committing that pointer block and nothing else in CLAUDE.md.
12. **Card.** `/warmup` prints ready, and `RULES/bin/conformance --project <dir>` reports every item holding, once that tool exists.

## 3 Every later change to the standard is mandatory too

common-rules keeps improving the standard: warm-up, reheat, the ledger, the card, proposals. The sponsor's ruling covers every such change, today's and future ones. "If I improve something in the common rules in the future regarding warm up or reheat, then the project should prioritize that and implement it. It's not optional."

1. **Spot it.** A CHANGELOG entry that changes the standard carries a line beginning `**Standard change (mandatory):**`, saying what each project must do. `rulecheck` says the project is behind, and the card shows it, whenever `RULES` has moved past the project's stamp.
2. **Queue it first.** At the next `/warmup`, read every entry since your stamp. For each entry with a Standard change line, add a ledger item owned by `lead` that names the entry. It runs next, straight after the item in flight, ahead of other queued work. Tell the sponsor in one line which entries you queued.
3. **Implement it**, the same way as the checklist in section 2, and record the evidence in the ledger.
4. **Only then align.** Run `rulecheck --align` once every Standard change entry since your stamp is implemented. Aligning the stamp without implementing them is forbidden: the stamp says the project follows the rules, and it would then be false. An entry with no Standard change line is information only. Read it, then align.

If you cannot implement an entry (a tool is missing, or it conflicts with a project safety rule), do not align past it. Block the ledger item with `owner` set to `sponsor` or `lead`, say why, and tell the sponsor.

## 4 Report when the refactor is done

- **Lead with the count:** `standard: N of 12 hold`.
- **Then only the items that do not hold,** each with why and what is needed, and who from, as a ledger owner.
- **Then any rule you dropped from the old lead prompt,** and why.
- **Record it in the ledger:** close the refactor item with its evidence (commit shas and the command outputs quoted above), using the real clock.

## Boundaries that do not change

- The project's own safety rules and prohibitions outrank this command.
- Never write into another project; ask its session through a `requests` entry.
- In CLAUDE.md, only the warm-up pointer block. Everything else in it stays the sponsor's.
- Never kill processes by name. Never `git stash` in a shared checkout.
- A summary is not a citation. Quote the sponsor's rulings from disk.
