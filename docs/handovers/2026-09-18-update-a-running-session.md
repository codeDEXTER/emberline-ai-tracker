# Paste this into a session that is already running

Copy everything between the rules below into any open session — in any project
under `apps/` — to bring it up to date with the standard as of 18 Sep 2026.

A running session holds the *old* copy of the skills and the rules in its
context. The files on disk are current (the skills are symlinks into
common-rules), but nothing re-reads them on its own, so an open session keeps
following what it loaded at its start. This text tells it to re-read and what
changed.

---

The common-rules standard moved today. Re-read it before your next action,
then tell me in one line what you had to change about how you were working.

1. Run `/reheat` for this project. If you cannot tell whether this session
   ever warmed up, run `/warmup` instead. Both now take context: anything I
   type after the command is passed through as `--context "<my words>"`, in
   the same run, quoted as I typed it.

2. Re-read these, because your copy predates them:
   `/Users/the-sponsor/apps/common-rules/CLAUDE-workflow.md`,
   `templates/brief.md`, `templates/lead-prompt.md`, and the skill you just
   ran. Then run
   `/Users/the-sponsor/apps/common-rules/bin/rulecheck --project . --mandatory`
   and queue every pending entry as a ledger item owned by `lead`, ahead of
   other work. Do not `rulecheck --align` until each is implemented — it
   refuses anyway, and aligning early would make the stamp assert something
   false.

3. Four rules apply to you from this moment, not after the queue:

   **Never background a gate and poll it.** Run it in the foreground, one
   blocking call, and read the verdict line in the same turn. Scope the run
   to fit — `tools/affected_tests.py` before the full suite, not the two
   dozen modules a ledger change names. If the tool backgrounds the call
   anyway at its ~120s cutoff, read the output exactly once when notified and
   act in that same turn. Never end a turn whose only purpose was waiting. One
   agent turn costs about 134,000 cache-read context tokens to produce a few
   hundred written ones, so cost follows the number of turns, not the work in
   them.

   **Dispatch in one message.** Every unblocked brief goes out together;
   branches are reviewed in one pass. Six briefs in one message cost one
   turn, six messages cost six. 72% of this project's spend went to lead
   orchestration against 25% to implementing.

   **Use the tool, not the shell copy.** Read files with the Read tool, not
   `cat` or `sed -n`. This is the one lever that is failing on measurement —
   9.54 such calls per 100 tool calls against 6.40 to call it halved, and it
   has moved backwards since the interim reading. I am part of that number
   too.

   **The merge gate is `bin/quiet --jobs auto`,** and `bin/workflow-stamp
   --check` runs before it. If this project declares `gates.merge`, it and
   the CI workflow must carry the identical string.

4. Three new tools are available. None is mandatory; each replaces something
   you are doing by hand:
   `bin/commit-if-green` (runs the gate, commits and pushes only on a green
   verdict), `bin/pr-body --item <ID>` (a PR body from the ledger item and the
   diff), `bin/item-notes --item <ID>` (the `ruflo-item done` note and the
   ledger event text, drafted from the same facts).
   `bin/ruflo-item` now takes several ids in one invocation, and
   `bin/ruflo-item from-ledger <LEDGER> --since <DATE>` backfills the records
   conformance check 9 asks for.

5. If you are mid-item, finish it or bring it to a clean committed point
   first. Never refactor mid-merge or during a gate run.

---

## One thing this text cannot do

`argument-hint` in the skills' frontmatter is read by the **client**, not by
the session. A running app has already parsed it, so the `/warmup` and
`/reheat` commands keep losing their highlight when you type after them until
the app is restarted. Restart it once; the pass-through then works everywhere.

Nor does this text implement the pending mandatory changes — it queues them.
Each project's own session does the work, because writing into another
project is prohibited. `docs/handovers/2026-09-18-adoption.md` has the
per-repo table and the shortest path (`PhotoVault/app`, 16 entries).
