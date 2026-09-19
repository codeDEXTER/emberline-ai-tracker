# What is Emberline?

Emberline is an open-source **AI agent memory and project tracker** for
developer workflows. It is designed for projects where work moves between
Claude Code, OpenAI Codex, and human reviewers.

## The problem

Chat sessions are good at doing work and poor at preserving a project-wide
view. Decisions get buried, context becomes stale, proposals lose their next
step, and a new session can repeat work that was already completed.

## The solution

Emberline keeps the durable parts of the work in a shared project record:

- decisions and open questions;
- proposals, owners, status, and dependencies;
- evidence and handover checkpoints;
- a generated tracker that shows the same work in several views.

The workflow has two entry points:

- **Warm-up** starts a fresh session from the current record.
- **Reheat** refreshes a session that is already running.

Both commands point back to the same source of truth. The tracker is a view of
the record, not a second place where work should be hand-edited.

## What Emberline is not

Emberline is not an autonomous approval system, a replacement for tests, a
general chat archive, or a promise that an agent will remember everything that
was said. Durable decisions must be recorded, and a human still decides what
is accepted.

## Who it is for

Use it when a project has more than one session, agent, or contributor and the
cost of losing context is greater than the cost of keeping a small ledger. It
is especially useful for long-running work, handovers, parallel sessions, and
projects that need visible proposals before implementation.
