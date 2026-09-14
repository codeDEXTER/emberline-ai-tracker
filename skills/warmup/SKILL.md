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
- **`page changed since last publish: <stem> → <url>`** means the rendered
  page (`docs/proposals/tracker/<stem>.html`) no longer matches what was last
  published to that URL. Republish it yourself, in the same turn, in this
  order:
  1. Finish and commit ledger edits first. Committing the ledger re-renders
     the page (derecord's pre-commit hook does it); if the card still shows
     the page as stale, run `tracker render` and commit that.
  2. Publish that committed page file with your Artifact tool **to the same
     URL** the line names — update the existing artifact in place, never
     create a new one.
  3. Record it: `RULES/bin/tracker published docs/proposals/<stem>.json --url <url>`
     (add `--by <your session's name>`), then commit the sidecar on its own:
     `docs/proposals/tracker/<stem>.published.json`, with nothing else in
     that commit.

  **When `.common-rules.json` declares `plan_page`**, the page of record is
  the file that project's generator writes, not the tracker page, and the
  line names that file: `page changed since last publish: <page> → <url>`.
  It speaks when the ledger moves, not when only a generated date does. Same
  order, with the page swapped in:
  1. Commit ledger edits first, then regenerate the page with the project's
     own generator (the `plan_page` command) and commit it.
  2. With your Artifact tool, publish that file in place to the same URL.
  3. Record it: `RULES/bin/tracker published docs/proposals/<stem>.json --url <url> --page <path>`,
     `<path>` being the committed file the generator wrote, relative to the
     project root; then commit the sidecar on its own. Without `--page`,
     `tracker published` refuses on such a project.

  A republish is not logged as a ledger event. The sidecar's `at` and `by`,
  in git, are the record. This is the one exception to "every state change
  gets a log entry": a log entry would itself move the page, and the line
  would come straight back.

  A republish needs no sponsor prompt: when the ledger's `switches.publish`
  is on (the default), republishing a changed page is part of keeping the
  ledger current, like rendering it. When `switches.publish` is switched off,
  nothing is published — the card prints no such line and `tracker published`
  refuses to record. The line never fails `warmup --check`; it is a to-do,
  not a broken standard. Only a session's Artifact tool can publish; no hook
  or script does it for you.
- **A page published before it was recorded.** When a tracker page is
  published for the first time, or you find one already published (a URL in
  the handover, lead prompt or log) with no `<stem>.published.json`, record
  it at once with `tracker published`; from then on the card tells you when
  it moves. The card gives no hint for a missing sidecar, because a project
  that never publishes must see nothing.

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

## Moving a running project onto the standard

1. `RULES/bin/warmup --project . --migrate --dry-run` first. It writes nothing
   and lists what it would do: run derecord, import the plan into a ledger
   under the next free proposal number, supersede rules, point CLAUDE.md at
   the read order. Only rules `RULES/templates/supersedes.json` names are
   superseded -- nothing is guessed. Show the sponsor that list.
2. `RULES/bin/warmup --project . --migrate`. Each superseded rule moves,
   verbatim and dated, into `## Superseded` in docs/OPERATING-RULES.md; nothing
   is deleted. Nothing is committed.
3. CLAUDE.md is the sponsor's: land will not land a branch that touches it.
   Say that it changed and let him commit it.

The card afterwards lists what was superseded. When you catch yourself
following a rule on that list, stop: the line names what replaced it. When a
migration shows a rule the standard replaces that the list does not name, add
an entry to supersedes.json with where it was seen -- do not move it by hand.
