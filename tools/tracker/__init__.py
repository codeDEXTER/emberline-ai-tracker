"""The proposal ledger toolkit (proposal 19).

`bin/tracker <command>` imports `tools.tracker.<command>` and calls its
`main(argv)`. Each command lives in its own module so that parallel work on
render, check, sync and import never touches the same file; `ledger.py` is the
one shared contract and changes only through the lead.
"""
