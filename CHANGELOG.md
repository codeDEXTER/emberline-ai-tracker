# Changelog — common-rules

Every change to a file in this folder gets an entry here — same convention
as a project's own `CHANGELOG.md`: newest first, one or two lines, why not
just what. This folder is its own git repo (see `README.md`), but `git log`
only records that something changed; this file records what it was for, and
is the thing to read first.

## 2026-08-03

- **SUPERSEDED, same day, by the proposal framework below.** Kept because the
  failure it was written from is real and the replacement has to keep covering
  it. The gap it named: requirements and design artifacts need a sponsor yes,
  not just the initial scope agreement. Found on
  finance-tracker's `person-dossier` task: a design-engineer's screen spec
  went straight to a code-engineer with no pause, so the sponsor only saw
  what had been designed after it was already built. Agreeing an issue is
  worth working on is a different decision from approving the specific
  requirements or design spec produced for it, and the second one had no
  gate. This is the project manager's job specifically — only it has a
  channel to the sponsor, so a rule written into the agent files alone would
  have nothing to act on — but `requirements-engineer.md`/`design-engineer.md`
  now each close their report format with an explicit statement that their
  artifact isn't self-approving, reinforcing the checkpoint at the point
  it's easiest to skip. A small, already-approved revision (a typo fix)
  doesn't need to go back through this — same judgment as the re-gate
  policy above.

  **Why it was superseded within the hour**: it gated every role transition,
  which would have meant four sequential approvals per feature — and aashish's
  call was one proposal per task instead. His reasoning, and the research
  agrees: a chain of gates a single sponsor approves in sequence decays into
  rubber stamps, and the defence large organisations use for that (a different
  approver at each stage) doesn't exist here. It was also incomplete — it added
  checkpoints without any of the tracking around them: no status, no
  traceability, nothing about what happens after a yes. The single-gate rule
  still prevents the exact failure this was written from, and keeps its better
  half: relaying means showing the artifact, not summarising that one exists.

- **A proposal framework**, adopted by every project referencing this file.
  Prompted by finance-tracker, where 7 numbered proposals carried no status at
  all — and where researching it turned up that tracking was already being
  improvised in three places that disagreed: proposal 06 printing "Proposal 08"
  on its own page, status smuggled into brand lines with no field to hold it,
  `CLAUDE-checklist.md` keeping its own parallel record, and proposal 04 having
  reversed its own conclusion by editing itself.

  The load-bearing decision is aashish's, and it went against what was
  proposed: **one proposal per task, not one per role.** However many agents
  run, they contribute sections and the user decides once. The four-stage
  chain was rejected because stage-gate research is consistent that a gate
  which isn't a real decision point is worse than none — and the defence large
  organisations use, a different approver per stage, is unavailable to a single
  sponsor. One gate can't rubber-stamp itself.

  The rest: six statuses each naming an action (no `deferred`, no
  `partly-accepted` — both decay); status in the document with the index
  regenerated from it, never the reverse; one number sequence with type as a
  field; conclusions immutable while labels and links stay fixable;
  traceability one-way from the cheap-to-edit side. On acceptance a draft issue
  is written for the user and a session is *offered* — named
  `<app> - <no> - <description>` — never started, since picking what to work on
  is his call.

- **Three amendments from the first day of real use**, all from things that
  actually happened rather than anticipated ones. (1) **The user can merge a
  PR from the chat** — the AI summarises what's in it and merges on the word,
  so visiting github.com is optional; it still never merges unprompted, and
  must summarise first or "merge it" becomes a rubber stamp. (2) **`LESSONS.md`
  now has a specified format**, because two sessions created the file
  independently in the same project on the same day and produced incompatible
  layouts — the rule had named the entry types but never the shape. Existing
  entries in the old layout stay as they are; append-only means not
  reformatting someone else's record either. (3) **A fix commit must touch a
  record file**, added to `code-engineer`: a commit that changes behaviour and
  updates nothing leaves the changelog asserting something false, and no test
  run can catch it. That gap recurred one commit after a gate named it, which
  is the signal it belongs in the agent's standing instructions rather than in
  another one-off correction.

- **Recorded the biggest caveat on the first task's result** in the story
  snapshot: none of the thirteen passes used the actual agent definitions.
  They were written mid-session and register at session start, so every pass
  ran as a general-purpose agent with the role's instructions pasted in. That
  preserved fresh context and the written boundaries, but not the tool
  grants — the real inspector cannot edit files at all, whereas a
  general-purpose agent is merely told not to. The shape was proven; the
  machinery that enforces it was not.

- **Added `docs/` and a running story**, with a **low-priority** rule adopted
  by every project referencing this file. aashish is a project manager by
  profession and wants to present this experience to fellow managers in a few
  weeks — the arc from a single chat doing everything, through building an
  agent team, to measuring and trimming it. `docs/story/README.md` holds the
  narrative in chapters, `docs/story/snapshots/` holds point-in-time records
  with real measured numbers, and `docs/` holds plain-language reports for
  someone who wasn't in the room (`ai-working-team.md` is the standard to
  match). Explicitly low priority: it never blocks a task, delays a merge, or
  justifies an extra agent pass — the raw facts already live in `AGENT-LOG.md`
  and the changelogs, so a snapshot can be written later from those. It lives
  here rather than in a project because the story is about the way of working,
  not about any one app. The rule requires snapshots to carry the parts that
  went badly and the mundane interruptions: a record of only smooth runs is
  useless for a presentation and worse than useless for learning.

- **Scoped the pull-request rule to this repo only** — projects keep
  worktree, checklist, merge on approval, with no PR. aashish's
  decision, made when the question came up on the first project branch
  after the PR rule landed. Written down explicitly because project
  sessions read `CLAUDE-workflow.md` too, and "every change goes
  through a pull request" reads as universal without the qualifier.

- **Rule changes here now go via branch and pull request**, with aashish
  merging — the AI never merges its own rule change. Prompted by noticing
  that the first batch of changes went straight to `main`, contradicting
  the no-direct-to-main rule stated in this same file. Worth the overhead
  on a solo repo because a diff reviews better than a chat summary, and
  because a bad rule here reaches every project silently. It also turns
  the reserved-for-the-user rule into a mechanism rather than a habit.
  No worktree for this repo — worktrees prevent build collisions and
  there is no build here. **One honest limit recorded with it**: because
  `~/.claude/agents` symlinks into `agents/`, an agent definition is live
  the moment it is saved, so for those files the PR is a record and a
  review surface, not a gate. Copy-on-merge would gate it but bring back
  the two-copies drift the symlink was adopted to remove.

- **First corrections from real use** — the improve-the-agents loop firing
  for the first time, on evidence from the `run-identity-badges` task in
  finance-tracker rather than on theory:
  - `code-engineer` must now **commit before reporting**. The gate found
    that branch at zero commits, having spent a full pass verifying work
    that existed only in a working tree, with every build stamped to a
    commit predating the change. No brief had said to commit — a process
    gap, so it becomes a standing rule instead of a per-task instruction.
  - `code-engineer` now treats **any value reaching generated code as
    untrusted**, branch names and labels included. A run-label written
    unquoted into a generated `.app` launcher gave arbitrary command
    execution on every launch, and was reported as working until an
    independent pass found it.
  - `quality-manager` now checks **commit state and merge-compatibility
    first**, not as a closing item — they cost seconds, and skipping them
    wasted an entire gate.
  - Added a **re-gate policy**: behaviour changes require another gate,
    documentation and commit-only changes do not, and `AGENT-LOG.md` must
    record when one was skipped. "The gate passed" and "the gate passed an
    earlier version of this branch" are different claims.
  - Not made a rule, but recorded: two of the four things that went wrong
    were the project manager's briefs, not the agents — a criterion written
    wrongly, and a missing instruction. The standing fix is to let
    `requirements-engineer` write criteria rather than the project manager
    improvising them.

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
  only clean runs is worthless for analysis. Every entry names its project
  explicitly even though the file lives inside that project — tasks run
  from worktrees so the location isn't self-evident while writing, entries
  get pasted elsewhere, and collating several projects' logs to compare
  how tasks ran only works if each entry stands on its own. Each agent
  row also carries its own token count, tool-use count and wall-clock
  duration, plus a total row — the figures arrive in the agent's
  completion notification and are only visible at that moment, so they
  get written down as each agent returns rather than reconstructed
  afterwards from memory.

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
