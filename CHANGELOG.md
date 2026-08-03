# Changelog — common-rules

Every change to a file in this folder gets an entry here — same convention
as a project's own `CHANGELOG.md`: newest first, one or two lines, why not
just what. This folder isn't a git repo (see `README.md`), so this file is
the only history that exists for it.

## 2026-08-03

- **This folder is now its own git repository** —
  `codeDEXTER/ai-common-rules` (private), created by aashish and adopted at
  his direction. It reverses the earlier "deliberately not a git
  repository" note, and the three places that asserted it (`README.md`,
  `CLAUDE.md`, and the closing section here) were corrected in the same
  change so they don't contradict reality. What has *not* changed is the
  reason the folder sits outside every project: these rules belong to none
  of them individually, and `apps/` still isn't a repo. `CHANGELOG.md`
  keeps its job — `git log` records that something changed, this file
  records what it was for, and it's still the thing to read first.

- Add **`AGENT-LOG.md`** — a per-project record of which agents ran, in
  what order, what each returned, and what it cost, written by the project
  manager because it is the only role that sees the whole sequence
  (agents cannot see each other). Directed by aashish, who wants to be
  able to look back and analyse how a task was actually run without
  reading a transcript. Two payoffs beyond the record itself: it is the
  evidence base for the improve-the-agents loop — a role whose findings
  keep getting disputed, or a gate that keeps missing the same class of
  problem, shows up here and nowhere else — and it makes the cost of
  ceremony legible, which is what tells you when a lighter tier would
  have done. Entries must include the parts that went badly; a log of
  only clean runs is worthless for analysis.

- **The seven agent definitions now live in `agents/` here**, with
  `~/.claude/agents` symlinked to it. They were sitting in `~/.claude/`,
  which has no version control — so the rules governing the agents had
  history while the agents themselves had none, which is precisely the
  gap this repo was created to close. Editing a file in `agents/` now
  edits the live agent, and the same reserved-for-the-user rule covers
  both. Worth remembering: they are machine-global, and they register at
  session start, so a mid-session change to one is invisible until the
  next session (found the hard way — the first attempt to invoke
  `code-engineer` failed because it had been written minutes earlier).

- Add **"Leave nothing running"** to the run-identity section, directed by
  aashish after watching the first real task go through the agents: any
  agent that starts an app instance must stop it before reporting, on the
  failure path included. Badges say which copy is which but do nothing to
  stop copies piling up, so without this the identity work only manages a
  mess it should have prevented. The stable copy is the deliberate
  exception — it stays up so there is always something to review. Mirrored
  into the `code-engineer`, `test-engineer` and `quality-manager`
  definitions, since those are the roles that actually start things.

- Add four sections to `CLAUDE-workflow.md`, all directed by aashish after
  reviewing two proposals and a decision register in the same conversation:
  **the agent roles and who improves them**, **project phases**, **telling
  running copies apart**, and **findings become well-formed issue drafts**.
  The short version of why: one session that plans, builds, tests and then
  certifies its own work has no independent check anywhere in it, and the
  published research on multi-agent development is consistent that a
  separate reviewer catches what a self-certifying implementer misses.
  Seven specialist agents now live in `~/.claude/agents/` and are governed
  by the same reserved-for-the-user rule as this folder, since an agent
  definition changes behaviour for every project at once.
- Three things in there are deliberate departures worth remembering:
  **there is no `project-manager.md`** (a subagent can't talk to the user,
  and deciding what escalates *is* that role's job, so it has to be the
  main session); **design is two roles** rather than one, because
  exploration and specification hold opposite stances and a single prompt
  holding both comes out timid; and **light ceremony is the default**,
  because full role pipelines measurably *reduced* correctness for most
  models tested — the tiers are a correction, not an efficiency measure.
- Honest caveat recorded at the time of writing: these rules describe
  something plausible, not something proven. No task had run through the
  agents when this was written. finance-tracker and pockets are the two
  pilots; expect the gate's checks and the artifact handoffs to be the
  first things that need correcting.

## 2026-08-02

- Add `CLAUDE.md` — a short pointer file so a session started with
  this folder as its own working directory (aashish wants to keep working
  on these rules directly, in a session separate from any one project)
  orients itself automatically: read `CLAUDE-workflow.md` first, and the
  edits-are-reserved-for-the-user rule applies here too.
- Expand "Confirmation gates" into "Issue lifecycle — the user is project
  manager, the AI is the developer": creating an issue is now reserved
  for the user (not just confirmed), scope and priority must be agreed
  before work starts, picking an issue is the user's call alone (the AI
  advises when asked "what's next" rather than self-selecting), added an
  explicit one-issue-at-a-time rule with an align-first exception for
  work that spans multiple issues, and closing stays reserved for the
  user. Also adds a new rule, directed by the user in the same
  conversation: editing any file in this folder (`CLAUDE-workflow.md`,
  `README.md`, this file) is itself reserved for the user — the AI
  surfaces what it noticed and asks, never edits here unprompted, since a
  change here silently affects every adopting project at once.
- **pockets** adopted `CLAUDE-workflow.md` (second adopter) — new repo
  created today with the pointer in its `CLAUDE.md` from the first
  commit, plus its own specifics (M0 harness commands, `data/` privacy
  rule, `worktree.baseRef: "head"` since it has no remote). Only the
  "Adopted so far" line changed here; no rule text was modified.
- Extracted `CLAUDE-workflow.md` from `finance-tracker/CLAUDE.md`'s "Git
  workflow" / "Issue tracking" / "Confirmation gates" sections — those
  rules turned out to be genuinely project-independent (worktree-per-task,
  the pre-merge checklist shape, the checklist-vs-issues mirror direction,
  the three confirmation gates), so keeping them duplicated inline in every
  project's `CLAUDE.md` would have meant hand-syncing every future change
  across projects. `finance-tracker/CLAUDE.md` now points here and keeps
  only its own specifics (test/build commands, its repo name, its `.env`/
  `finance_data/` gotchas). No other project has adopted this file yet.
