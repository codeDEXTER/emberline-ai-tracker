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
Update the ledger with `tracker set` / `tracker ask`, never by hand-editing its JSON.
In a bundle: one commit per issue, naming its id, one gate run, one PR closing all of them.

MUST NOT
{{MUST_NOT_1}}
Hand-append AGENT-LOG.md or HANDOFF.md -- use `bin/spend agentlog --write` and `bin/remember`.

OUTPUT
{{OUTPUT_1}}
Last line, exactly: HANDOFF: status=<done|blocked> commit=<sha> needs=<what the lead must do>

EFFORT
{{EFFORT_NOTE}}
