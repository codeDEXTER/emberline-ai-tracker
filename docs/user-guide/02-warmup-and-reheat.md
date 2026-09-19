# Warm-up and reheat

Warm-up and reheat solve different timing problems. Both read the project
record and produce a compact starting card before implementation continues.

## Use warm-up for a fresh session

Run `/warmup` when a new chat is opening on a project. It reads the required
orientation files in order, checks the declared standard, loads the current
ledger and latest checkpoint, and reports what is pending.

Warm-up is for establishing context. It should happen before making changes.

## Use reheat for a running session

Run `/reheat` when the session is already active and you need to know what
changed since the last warm-up or reheat. It prints the delta, the standard's
current status, and the pending queue without replaying the entire history.

Reheat is for continuity inside a session. It is not a substitute for a fresh
warm-up after a new session or a compaction.

## The practical sequence

1. Fresh chat: `/warmup`.
2. Work on one owned item and record durable decisions.
3. After a compaction or a long pause: `/reheat`.
4. Before handoff: update the tracker and checkpoint.
5. New chat or new agent: `/warmup` again.

The corresponding skills live in [`skills/warmup`](../../skills/warmup/) and
[`skills/reheat`](../../skills/reheat/). The shell checks are available as
`bin/warmup` and `bin/reheat` for repository validation.
