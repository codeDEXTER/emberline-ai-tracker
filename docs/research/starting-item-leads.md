# Starting an item lead with no sponsor click (proposal 24, H-03)

Research only — no session was started for this. Commands below were read
from `claude --help` / `claude agents --help`, never run.

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
claude --bg -p "print 'handover proof run' and exit" --worktree handover-proof
```

Then confirm with `claude agents --json` that the id it printed shows up,
`claude logs <id>` shows the expected line, and `claude rm <id>` cleans up
the worktree it made.
