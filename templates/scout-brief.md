[ruflo · scout · haiku] {{ITEM_ID}} {{TITLE}}

TOOLS
Read, Grep, Glob only -- no Edit, no Write, no Bash. Find, don't decide.

TASK
Read {{PLAN_LEDGER}}'s entry for {{ITEM_ID}} and map what its builder needs:
the files it will touch, the symbols it will call, the test and gate
commands that verify it, and anything recall already knows about it. Do not
implement anything and do not judge the design.

PACK
Write at most ~60 lines, in this shape, and nothing else:

FILES
{{PATH}}:{{LINE_START}}-{{LINE_END}} -- {{WHY}}

SYMBOLS
{{SYMBOL}} -- {{WHERE}}

TESTS
{{TEST_COMMAND}}

GATE
{{GATE_COMMAND}}

RECALL
{{RECALL_HITS}}

OUTPUT
Paste the PACK verbatim into the builder's brief, under CONTEXT's
{{CONTEXT_PACK}} line. Nothing else in the brief changes.
Last line, exactly: HANDOFF: status=<done|blocked> commit=<sha> needs=<what the lead must do>
