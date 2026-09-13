---
name: warmup
description: Warm up this session on the project's standard (common-rules proposal 19). Reads HANDOFF.md, the operating rules, the ledger and the last checkpoint in a fixed order, checks the tools, and prints the warm card before any work. Use at the start of every session, after a context compaction, or mid-session ("warm up", "what changed", "refresh the rules").
---

# /warmup

The rules are already on disk. This skill loads them in the same order every
time, so the sponsor never has to type "reread the handoff", "are you using
ruflo" or "what is the current status" again. It asks nothing.

`RULES` below is `/Users/the-sponsor/apps/common-rules`, unless this project's
CLAUDE.md names a different common-rules checkout.

## 1. Cold start, or mid-session

- **No earlier warm-up in this session** (or you cannot tell):
  `RULES/bin/warmup --project . --state .claude/warmup/last.json`
- **Mid-session refresh, or after a compaction:**
  `RULES/bin/warmup --project . --since .claude/warmup/last.json`,
  then save the new state with `RULES/bin/warmup --project . --json --state .claude/warmup/last.json > /dev/null`.
  Only what moved is printed; act on each line.

`.claude/warmup/` is scratch state. Never commit it.

## 2. Read, in the order the card names

The card ends with `Read in order:`. Read every file on that line, in that
order, before any other action: HANDOFF.md → docs/OPERATING-RULES.md → the
ledger(s) → the latest checkpoint → common-rules' CLAUDE-workflow.md.

After a compaction the summary above is a paraphrase. The ledger is the
record. Quote a ruling from disk (the constraints file, the issue, the ledger
ask), never from the summary.

## 3. Act on the card

- **✗ lines are problems.** Fix each before new work — `tracker render`,
  `tracker checkpoint`, fill a placeholder — or record it in the ledger as
  `blocked` with the reason. Never start work over a red card silently.
- **Prohibitions** are verbatim from HANDOFF.md. Put them, word for word, in
  every agent brief.
- **Ruflo is mandatory.** The card shows where the CLI is; warm-up never runs
  it. For every item: `memory search` and `hooks route` before, `hooks
  post-task` and `memory store` after, run from the project root, then
  `daemon stop` for the daemon your calls started. Never kill it by name.
- **`RULES/bin/recall <words>`** searches every project's memory, LESSONS and
  operating rules. Put the hits for an item under CONTEXT in its brief.

## 4. The first message to the sponsor

1. The card, as printed.
2. A steps list for the first item you will take, its ledger id on top.
3. Then start — spawn every unblocked C1/C2 item in one message, each in its
   own worktree with the five-heading brief from `RULES/templates/brief.md`;
   take the first C3 yourself.

While working, keep to one status line in the lead prompt's form:
`N done / N in progress / N blocked / N not started · what changed · waiting on · yours:`

Every sponsor message that is not an answer to a question becomes an `A-nn`
ask row in the ledger, in the same turn.

## Not yet

`/warmup --migrate` — moving a running project onto this standard, with
replaced rules kept in a dated Superseded block — is ledger item W-09 of
proposal 19 and is not built. Until it is, say so rather than improvising it.
