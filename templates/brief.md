[ruflo · {{TIER}} · {{MODEL}}] {{ITEM_ID}} {{TITLE}}

CONTEXT
{{RECALL_HITS}}
{{CONTEXT_PACK}} -- written by the Haiku scout, templates/scout-brief.md, before this brief is sent.

Bundle form for small issues on one surface: one row per issue below, empty for a single-item brief.
ITEMS
{{BUNDLE_ITEMS}}

OWNS
{{OWNED_FILES}}

MUST
{{MUST_1}}
Reach {{VERIFY_LEVEL}} from the project's verification ladder ({{VERIFY_TOOL}}).
Read a file with the Read tool (`offset`/`limit`), never `cat` or `sed -n`.
Run the gate with `bin/quiet -- {{TEST_COMMAND}}`, never a raw test runner.
Stage ledger updates with `tracker stage` -- never `tracker set`, never `tracker ask`, never hand-editing its JSON. You never write the ledger or its page directly; the lead applies every staged change with `tracker apply-staged` when it merges your branch in (proposal 23, M-04).
In a bundle: one commit per issue, naming its id, one gate run, one PR closing all of them.

MUST NOT
{{MUST_NOT_1}}
Size the work yourself: this brief never carries the item's points (proposal 25, D3); `tracker route` is the lead's.
Hand-append AGENT-LOG.md or HANDOFF.md -- use `bin/spend agentlog --write` and `bin/remember`.
Run `tracker apply-staged` yourself, for any ledger, ever -- staging is as far as you go; applying staged changes is the lead's alone, even when no one else appears to be touching the same ledger right now (proposal 23, M-04).

OUTPUT
{{OUTPUT_1}}
Last line, exactly: HANDOFF: status=<done|blocked> commit=<sha> needs=<what the lead must do>

EFFORT
{{EFFORT_NOTE}}
