# Checkpoint — 2026-09-16 19:12

Reason: manual · branch: measure-record · HEAD: 1aa28f1

<!-- ledger-digest: 16a1811f1a8ffd41b58f9b8e46d52b5e3a7fd5969619ef912222bb6c4877646d -->

## Proposal 19 · Warm-up

15 done / 1 in progress / 0 blocked / 0 not started

### In progress

- W-10 · [ruflo · low · haiku] · Pilot on the PhotoVault engine; measure the exit conditions · exit conditions re-measured

### Blocked, and why

- none

### Open asks

- none

### Next unblocked

- none

## Proposal 21 · The standard is mandatory

9 done / 0 in progress / 0 blocked / 2 not started

### In progress

- none

### Blocked, and why

- none

### Open asks

- none

### Next unblocked

- S-07 · [ruflo · low · haiku] · PhotoVault app on the standard
- S-08 · [ruflo · low · haiku] · PhotoVault engine on the standard

## Proposal 23 · Eight levers for token spend

16 done / 3 in progress / 0 blocked / 0 not started / 2 in testing

### In progress

- L-01 · [ruflo · lead · opus] · Fresh lead per milestone or day · measured 2026-09-16: FAIL. The common-rules lead session itself (3cff917f, main transcript, deduped by message id) spent 76.1% of its 16 Sep tokens (165.5M over 348 requests) on requests above 500k context; max context 671k; 15 Sep 39.3%. No other lead session exists after the rule landed. The rule is written but not followed: this lead ran one session across 14-16 Sep instead of starting fresh per milestone
- L-07 · [ruflo · medium · sonnet] · Use the existing tool, not an inline copy · measured 2026-09-16: FAIL. Mining script reconstructed and rerun, 8-14 Sep vs 16 Sep, all apps transcripts: cat/sed -n reads 12.80 -> 7.67 per 100 tool calls (-40%, not halved); hand-appended HANDOFF/AGENT-LOG 2 -> 1 (too thin to judge); raw flutter test not measurable (no Flutter sessions after). Reconstruction does not reproduce the original 15 Sep magnitudes, so the original script's window differed
- M-03 · [ruflo · medium · sonnet] · Trim Ruflo's tool loading · measured 2026-09-16: build half questioned. M-03 landed as dcc3c1b, 18 lines of skills/warmup/SKILL.md only -- no .mcp.json or loading change, so nothing can move tool-definition tokens. Before: first-request context median 52,795 tokens over 10 ruflo-project sessions (4-5 Sep, thin); after: 0 ruflo-project sessions exist. bin/ruflo-item --help exits 0

### Blocked, and why

- none

### Open asks

- none

### Next unblocked

- none

## Proposal 24 · Autonomous work without missing anything

2 done / 1 in progress / 1 blocked / 0 not started

### In progress

- H-02 · [ruflo · medium · sonnet] · Thin dispatcher and short item leads · measured 2026-09-16: FAIL. The session that dispatched bundles K/L (3cff917f) reached 671k context on 16 Sep and 843k on 15 Sep, against a 150k dispatcher cap. No session has run in the dispatcher form yet

### Blocked, and why

- H-03 · transcripts under ~/.agent-data/projects/-Users-the-sponsor-apps-common-rules--claude-worktrees-h03-proof*/

### Open asks

- none

### Next unblocked

- none

## Exact next action

W-10 · [ruflo · low · haiku] · Pilot on the PhotoVault engine; measure the exit conditions
