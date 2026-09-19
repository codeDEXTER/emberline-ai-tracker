# The tracker and proposals

The tracker is generated from proposal ledgers. A ledger is the durable record
of what was proposed, decided, assigned, measured, and left for later.

## What a proposal contains

A proposal normally records:

- the outcome the work is trying to produce;
- items with stable IDs, owners, tags, value, and risk;
- dependencies and current status;
- asks, decisions, findings, and evidence;
- the next item that should be worked.

Keep the ledger as the source of truth. Use the supported tracker commands to
validate or render it rather than editing generated HTML by hand.

## The four views

- **Tree** shows the proposal hierarchy and dependencies.
- **Kanban** groups work by status.
- **Board** gives a card-oriented view of the current plan.
- **List** is the compact inspection view for filtering and scanning details.

Open the [live tracker](../proposals/tracker/index.html) to see the current
public record.

## A safe update loop

1. Identify the proposal and item you own.
2. Record the decision or status change in the ledger.
3. Run the relevant tracker validation.
4. Regenerate the tracker page.
5. Run the tests and review the diff.
6. Commit the ledger and generated page together.

Generated pages are valuable evidence, but they are outputs. The JSON ledgers
and the workflow rules remain the authoritative inputs.
