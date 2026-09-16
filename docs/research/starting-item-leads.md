# Starting an item lead with no sponsor click (proposal 24, H-03)

Research only — no session was started for this. Commands below were read
from `claude --help` / `claude agents --help`, never run.

## Correction, 2026-09-16: proof run taken

The command below is wrong as written: `claude --bg` refuses `-p` ("--bg and
--print conflict"); the prompt is the positional argument:
`claude --bg --model opus --worktree <name> "<prompt>"`. Three proof runs
started with no click and were removed with `claude rm <id>`, but none
finished: two stopped on a login refresh held by another Claude process, the
third on "Login expired · Please run /login". Haiku also has no auto mode, so
an unattended lead must run on a model that does. H-03 is blocked on the
sponsor's sign-in; see its ledger log.

**Proven, 2026-09-16 after the sponsor signed the CLI in:** session
9a77f7f0 (`claude --bg --model opus --worktree h03-proof4 "<task>"`) started
with no click, ran `bin/conformance --project .` itself in auto mode with no
permission prompt, replied `standard: 12 of 12 hold`, reached state `done`,
and was removed with `claude rm 9a77f7f0`. The CLI keeps its own sign-in,
separate from the desktop app's: check `claude auth status` before a
dispatcher relies on this.

## Mechanism 1: `claude --bg -p "<prompt>"`

- **Click needed:** none. `claude --bg` "start[s] the session in the
  background and return[s] immediately" — a plain CLI call, runnable from
  inside another Claude session's Bash tool.
- **Session id captured:** printed to stdout on start (the "short id" the
  help text says `claude attach`, `logs`, `stop`, `rm` take). Capture it
  from the command's own output, no polling needed.
- **cwd / worktree:** `--bg` combines with `-w/--worktree [name]`, which
  "creates a new git worktree for this session" — the dispatcher's own job
  today, done by the CLI instead. Without `-w`, `--bg` inherits the caller's
  cwd like any other invocation, so the dispatcher must `cd` into the
  intended worktree first if it is not asking the CLI to make one.
- **Stopped by id:** `claude stop <id>` (alias `kill`) stops it, keeping the
  conversation; `claude rm <id>` deletes it and its worktree "when that is
  safe." Exactly the explicit-PID discipline OPERATING-RULES.md already
  requires, at the session level instead of the process level.
- **Risks:** `-p` alone does not carry the "start as an item lead" role —
  the prompt has to be the full lead-prompt.md substitution, sent as the
  argument or via `--append-system-prompt-file`. A malformed or truncated
  prompt fails silently into an ordinary background session, not an error;
  nothing forces the dispatcher to check `claude agents --json` after
  starting it. `--dangerously-skip-permissions` is a separate flag and must
  never be added implicitly.

## Mechanism 2: desktop MCP `mcp__ccd_session_mgmt__send_message` (etc.)

- **Click needed:** none from the tool itself, but CLAUDE-workflow.md:427
  documents it only for messaging a session that already exists (agreeing
  who holds a contested surface) — not for creating one. No sibling
  "start a session" tool was found in this pass; confirming that gap (or
  finding the missing tool) is the lead's first step if it picks this
  mechanism.
- **Session id / cwd / stop:** unknown without that missing tool; cannot be
  compared fairly against mechanism 1 from research alone.
- **Risk:** building on an assumed tool that turns out not to exist wastes
  the proof run entirely.

## Mechanism 3: a scheduled task (cron / launchd)

- **Click needed:** none once installed, but installing the schedule is a
  one-time human step (or an `osascript`/`launchctl` call this session is
  not authorized to make unattended), and it starts leads on a timer, not
  the moment a bundle unblocks — the wrong trigger for a dispatcher that is
  supposed to react to the ledger.
- **Session id / stop:** whatever `claude --bg` prints, same as mechanism
  1 — the schedule is only the trigger, not a different start mechanism.
- **Risk:** a stale schedule keeps firing after the plan is done; nothing
  in this project's tooling watches for that today.

## Recommendation

Mechanism 1. It needs no click, no unverified tool, and no separate
scheduler; captures its own id; and composes with `-w` for the worktree the
dispatcher would otherwise create itself. The proof run the lead should do
first, without sending it anything but a no-op:

```
claude --bg --worktree handover-proof "print 'handover proof run' and exit"
```

Then confirm with `claude agents --json` that the id it printed shows up,
`claude logs <id>` shows the expected line, and `claude rm <id>` cleans up
the worktree it made.

## Follow-up: naming, so a background lead is visible and not mistaken for a chat (proposal 24, H-04)

Mechanism 1 above (`claude --bg -p ...`) also takes `--name`, unused in the
proof run. Every session the dispatcher starts in the background is started
with `claude --bg --name <name>`, so it shows by that name in `claude
agents` and the desktop session list, distinct from an interactive chat:

- `bg · <project> · dispatcher` for the dispatcher itself.
- `bg · <project> · lead · P<nn> <item ids>` for an item lead, e.g.
  `bg · common-rules · lead · P26 C-03`.

`<project>` is the project's own directory name (`common-rules`, not a
display title), matching what `bin/handover --check`'s new check reads from
`--project`. `<item ids>` is the bundle the lead was started for, exactly as
the dispatcher named it when it read the plan -- the same ids that end up in
the item's own ledger log, so the name and the ledger agree on what that
session is doing.

`bin/handover --check` and the tracker page list running background leads
by this name, with their session id. `bin/handover`'s check 5
(`check_background_names` in `bin/handover`) reads `claude agents --json`,
filters to sessions whose `background` field is true, and flags any of
those not named by the convention above -- SKIP, not FAIL, when the
command itself is not available (nothing on disk can answer that from
inside a sandboxed worktree). **Not verified end to end**: this pass never
had a real background session running to point `claude agents --json` at,
so whether the command's real JSON shape actually carries a `background`
field (or something else entirely) was not observed -- only the naming
logic and the new handover check were exercised, against a stub
(`HANDOVER_AGENTS_BIN`). The lead-prompt Dispatcher form and the H-03 proof
run are the next places this needs to be wired in and actually watched
once a real background session exists to watch.
