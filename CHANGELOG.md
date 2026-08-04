# Changelog — common-rules

Every change to a file in this folder gets an entry here — same convention
as a project's own `CHANGELOG.md`: newest first, one or two lines, why not
just what. This folder is its own git repo (see `README.md`), but `git log`
only records that something changed; this file records what it was for, and
is the thing to read first.

## 2026-08-04

- **Cleanup is now scoped by ownership**, in `CLAUDE-workflow.md`'s "Leave
  nothing running" section (retitled "— and stop only what you started").
  Two halves. The first restates the existing rule at **session** scope rather
  than per-agent: agents within a task can share a running copy, but the task
  does not end with it still up, and the project manager is accountable for
  that. The second is the new half and the reason the-sponsor asked: **an agent
  stops only what its own session started.** Anything else running belongs to
  someone — the user reviewing a build, or a parallel session mid-validation —
  and killing it takes their work away silently. So cleanup is targeted (by
  recorded PID and port), never a sweep: no `pkill -f`, no `killall`, no
  clearing a port range on principle, and a port in your own range that you
  didn't start is a collision to report rather than to reclaim.

  This also demotes the stable copy from an exception to a *case* of the rule —
  no session started it, so no session stops it. Behaviour change for adopted
  projects: previously a tidy-minded agent could have justified killing a stray
  server it found; now that is explicitly wrong, and leaving a stranger's copy
  running is the correct outcome.

  The same wording went into the three agent definitions that actually start
  instances — `code-engineer`, `test-engineer`, `quality-manager` — because all
  three still carried "the one exception is the stable copy", which the rule
  above demotes. An agent reading only its own file would otherwise have kept
  the framing this change exists to replace.

- **After acceptance: requirements, then design, then L2 — never straight to
  code.** the-sponsor's rule, and it **corrects the paragraph merged a few hours
  earlier** which said a complete brief meant the upstream roles could be skipped
  and the tier was small-fix. Wrong, and the correction is stated in place rather
  than quietly edited: **an accepted proposal is not settled requirements.** It
  is a decision about direction, argued in prose — the input to requirements
  work, not a replacement for it.

  So acceptance now starts a fixed sequence: `requirements-engineer` →
  `design-engineer` → **L2** → code, test, gate. **L1 is the-sponsor accepting the
  proposal; L2 is the project manager accepting the requirements and design
  produced from it** — two decisions about two artifacts. Collapsed, the second
  is never made by anyone; it gets inferred one file at a time by whoever writes
  the code.

  His reasoning, and it is the right one: the code agent will not expand
  requirements and design properly. Not a flaw in that agent — it is being asked
  to do two jobs whose instincts conflict, so given a gap it fills it in passing,
  in whatever shape is easiest to build. The decision then exists only as code,
  with nothing written down for the test engineer to check or the gate to hold it
  to. **An inferred requirement is an invisible one.**

  Four things escalate past L2 to him, and none are judgment calls: the work
  contradicts what the proposal decided; scope moves; a decision surfaces the
  proposal never made; or it turns out materially larger than implied. Skipping
  design for work with no visible surface is allowed and must be **said out loud
  and recorded in `AGENT-LOG.md`**, like a skipped gate — silence is what makes a
  skip indistinguishable from an oversight.

  He pointed at **issue #31** and it is worth keeping, because the cost was
  total. Its brief went from proposal 07 straight to "Implement" for the most
  design-dependent task in the batch — a rail, a seam and a dock whose entire
  point was that the boundary between confirming a write and asking a question be
  obvious at a glance. No `REQUIREMENTS.md`, no screen spec, a layout problem
  handed over as prose. The session built all of it itself over 256 messages;
  the-sponsor intervened; the session replied *"You're right, I broke the rule that
  matters most here"* and **reverted all seven of its changes**. A whole session
  discarded. And the rework still ran only `code-engineer` — being told to use
  the agents did not produce requirements or design work, because nobody had said
  the proposal wasn't already the requirements.

  Enforced where it bites rather than only in prose: `code-engineer` now refuses
  to start from a proposal and must say what is missing; `requirements-engineer`
  states when its output is post-acceptance and that L2 is still owed;
  `design-engineer` must name anything belonging to the sponsor rather than to
  L2. The brief template was rewritten — it previously said "Tier: small fix" and
  named only the code engineer and gate, which would have reproduced #31 exactly.

- **Named the dispatch mechanism, and fixed the briefs that bypassed it.**
  the-sponsor asked why finance-tracker's issue sessions weren't using the agents.
  They weren't: **#30, #31, #32, #35, #36 and #37 made zero agent calls** and
  implemented everything with `Edit` and `Bash` — which means **six merged
  features never saw a pre-merge gate.** The same project's open-ended session
  (`issue-27-person-dossier`) made eighteen calls across all six roles, so the
  definitions, the symlink and registration were never the problem. All six read
  this file first. They read the rule and did not follow it.

  Three causes, and the first is embarrassing: **this file named the roles and
  never named the mechanism.** Exact commands for `EnterWorktree` and `apprun`,
  and for the one behaviour the whole structure depends on, a table. `Agent` and
  `subagent_type` appeared zero times. Now they appear, with the invocation
  written out and a behavioural test that can be applied mid-task: *if this
  session is calling `Edit`, it is no longer the project manager.*

  Second, **the brief is the trap.** "Implement issue #36 … acceptance criteria:
  …" *is* a code-engineer task brief, and a session handed one executes it,
  because the live instruction beats a file it was told to go read. The fix is at
  the source: a session brief now opens "Project-manage", states the tier and
  names the agent set before any task detail. A complete brief is a reason the
  *upstream* roles can be skipped, never a reason to skip the gate — settled
  requirements make the work more checkable, not less.

  Third, **the step existed here and not in the artifact that starts the work.**
  The rules already said the PM names which agents run; none of the six briefs
  did. A rule that only lives in a file nobody consults at the deciding moment
  is not in force.

  Also fixed: those briefs pointed at `../common-rules/CLAUDE-workflow.md`, which
  **does not resolve from a worktree** — and a worktree is the first action on
  any project repo. The sessions recovered by hunting for the absolute path,
  which is luck. Absolute paths now, and it is logged as a gotcha alongside a
  second one this investigation produced: `~/.agent-data/projects/` directories start
  with `-`, so a glob'd `grep` reads them as flags, finds nothing, and does not
  error — it briefly produced a confident and completely wrong conclusion about
  which sessions had read this file.

  **Not fixed here, because it isn't this repo's file**: finance-tracker's own
  `CLAUDE.md` says "the-sponsor is project manager here, **the AI is the developer**"
  — singular, and it is the file that auto-loads, while this one is read only
  when a prompt asks. It reads as permission for exactly the behaviour above.
  Raised separately as an issue draft.

- **`ASKS.md` — track what he asks for, propose the pattern.** His point, and it
  is a fair one: almost every rule in `CLAUDE-workflow.md` started as him asking
  for something in a chat, and most were asked more than once, in different
  projects, before anyone noticed they were the same ask. The rule existed as a
  pattern in his instructions long before it existed as a rule, and until then
  every session had to be told again.

  So sessions log instructions about *how work is done* — not what to build; an
  export button is a requirement, "show me a mockup first" is an ask — and
  corrections especially, since a reversal says more about what he wants than
  the original instruction did. When entries rhyme, propose it: not on a count,
  but when the general form fits in one sentence and covers two or more distinct
  entries. **Amending an existing rule is usually the right shape**, because most
  patterns turn out to be a rule that didn't reach far enough, and a second
  section saying nearly the same thing is how this file becomes unreadable.

  Written with its own failure mode stated in the text, because it is a real
  one: the rule rewards finding patterns, and a session wanting to look useful
  can manufacture one from any two instructions. Those rules have no felt problem
  behind them and are the ones followed literally and wrongly. A pattern nobody
  was hurt by is not worth a rule.

  Backfilled with 15 entries from this changelog and the common-rules session,
  and two patterns fell straight out — both of which the file argues should be
  *amendments*, not new sections. First: **he wants the state of things visible
  at a glance** (the diagnostic log, run badges, one stable copy, closing
  instances, a clean copy, a reserved icon, approving a PR without opening git —
  seven entries across four surfaces, each ruled individually, the general form
  never written down, which is exactly why each new surface needed its own ask).
  Second: **show him the thing, don't describe it** (mockups early, an image of
  the doc page, a demo before approval, and the surviving half of the deprecated
  PR #6 rule) — already stated in three places that don't reference each other.

- **Offer a demo before asking for the yes.** A draft issue is a paragraph of
  text, and approving it from text alone means deciding about a screen that
  hasn't been looked at in weeks. So the project manager now offers to *show*
  the thing first — of a draft issue, and of any proposal about an existing
  surface. The demo is of what is there now, not of the fix; nothing is built
  yet, and its job is to put the-sponsor in front of the real screen so he decides
  against it rather than against a description.

  Deliberately **an offer, not a gate**: "just approve it" is a complete answer,
  and the rule is satisfied by having given the choice. Two things make an offer
  worth taking — navigation click by click in the app's own words ("Sidebar →
  Ledger, Subscriptions tab, the Safeguard row"), and **no new window where the
  clean copy will do**, since starting a second copy to show what the first one
  already shows rebuilds the exact pile he complained about an hour earlier.

  This collides with the cleanup rule directly, so the carve-out is explicit and
  mechanical: a copy started **for the user** is marked `--demo` in the registry,
  survives a blanket `apprun stop --all`, and prints a line telling the session
  to say in its report that it left it up and where. Closing the window someone
  is still reading is precisely the failure the ownership rules exist to prevent,
  and end-of-task cleanup is the easiest place to commit it by reflex.

- **`bin/apprun`, a run registry — and the reason it exists.** the-sponsor reported
  still seeing a lot of windows open despite the rule above. Checking the
  machine explained why: it was *clean* — one server (stable, :8502), one Safari
  window on it, nothing in the test or proto ranges. The sessions had stopped
  their servers correctly. **The windows aren't the servers.** Every rule we had
  talked about processes and ports; a NiceGUI launch opens a browser window, and
  killing the server leaves it there, dead, still titled like the app. Ten
  compliant sessions leave ten windows. So cleanup now closes the window too,
  matched on the exact `127.0.0.1:<port>` of the instance being stopped.

  Two further gaps the same check exposed. **Ownership was unenforceable** —
  nothing recorded who started what, so an agent could believe it was following
  "stop only what you started" while the pile grew. And **the ownership rule made
  orphans permanent**: when a session dies its instances belong to nobody, so
  under the rule as written nothing could ever stop them. Both are fixed by the
  registry: entries carry `CLAUDE_CODE_SESSION_ID` and that session's pid, so
  ownership is a lookup and "is the owner still alive" is a `kill -0` — exact,
  not a heuristic. An orphan is the one category a stranger may close, and only
  with the-sponsor's explicit yes, because one of those windows may be the one he is
  looking at. `stop` declines a live stranger's copy, an orphan, and the stable
  copy, each with the reason.

  Judgment call worth flagging: this is the first executable in a folder that has
  only ever held rules. Written because "each agent hand-rolls the bookkeeping"
  is precisely how the drift returns — but it is a widening of what this repo is,
  and reversible if the-sponsor would rather it lived in a project.

- **There is always a clean copy to open.** Protecting the stable copy is not the
  same as guaranteeing one exists, and only the second helps when he just wants
  to open the app. His call on timing: **refreshed from `main` after a feature
  merges** — the moment the work is integrated, gated and merged, so a rebuild
  carries the new feature and nothing half-finished. Not at session start, not
  mid-task. A merge that leaves the installed app on last week's build has
  finished the git work and not the task. `apprun sweep` says `NO CLEAN COPY
  RUNNING` outright, because that failure is otherwise silent until he goes to
  open the app and finds nothing there.

- **The final app gets its own reserved icon.** Badges and window titles only
  help once a window is open and being read; the Dock and Cmd-Tab show an icon,
  and if every build shares one, he is back to guessing which of five identical
  tiles is real. So one icon is reserved for the installed stable copy and used
  by nothing else, with test and proto builds visibly different at Dock size. His
  prompt was that the current one doesn't sit well — and it is worse than a taste
  problem: finance-tracker's `icon-512.png` is a gold **W**, left over from
  "Wealth Tracker", a name the app hasn't had since it became Sangam in Jul 2026.
  The one tile that should be unmistakable currently says the wrong thing.
  Drawing the replacement is design work belonging to finance-tracker, not here;
  what this file adds is the rule that the reserved icon exists and that stale
  branding on it is a finding, not something to live with.

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
  which would have meant four sequential approvals per feature — and the-sponsor's
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

  The load-bearing decision is the-sponsor's, and it went against what was
  proposed: **one proposal per topic, not one per role — and not one per
  session.** A proposal stays open across conversations, gaining sections,
  until he decides; "one per task" was the first wording and it invited
  treating each new chat as a new task, which quietly rebuilds the four-proposal
  chain the rule exists to prevent. However many agents
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
  by every project referencing this file. the-sponsor is a project manager by
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
  worktree, checklist, merge on approval, with no PR. the-sponsor's
  decision, made when the question came up on the first project branch
  after the PR rule landed. Written down explicitly because project
  sessions read `CLAUDE-workflow.md` too, and "every change goes
  through a pull request" reads as universal without the qualifier.

- **Rule changes here now go via branch and pull request**, with the-sponsor
  merging — the AI never merges its own rule change. Prompted by noticing
  that the first batch of changes went straight to `main`, contradicting
  the no-direct-to-main rule stated in this same file. Worth the overhead
  on a solo repo because a diff reviews better than a chat summary, and
  because a bad rule here reaches every project silently. It also turns
  the reserved-for-the-user rule into a mechanism rather than a habit.
  No worktree for this repo — worktrees prevent build collisions and
  there is no build here. **One honest limit recorded with it**: because
  `~/.agent-data/agents` symlinks into `agents/`, an agent definition is live
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
  `github-owner/ai-common-rules` (private), created by the-sponsor and adopted at
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
  (agents cannot see each other). Directed by the-sponsor, who wants to be
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
  `~/.agent-data/agents` symlinked to it. They were sitting in `~/.agent-data/`,
  which has no version control — so the rules governing the agents had
  history while the agents themselves had none, which is precisely the
  gap this repo was created to close. Editing a file in `agents/` now
  edits the live agent, and the same reserved-for-the-user rule covers
  both. Worth remembering: they are machine-global, and they register at
  session start, so a mid-session change to one is invisible until the
  next session (found the hard way — the first attempt to invoke
  `code-engineer` failed because it had been written minutes earlier).

- Add **"Leave nothing running"** to the run-identity section, directed by
  the-sponsor after watching the first real task go through the agents: any
  agent that starts an app instance must stop it before reporting, on the
  failure path included. Badges say which copy is which but do nothing to
  stop copies piling up, so without this the identity work only manages a
  mess it should have prevented. The stable copy is the deliberate
  exception — it stays up so there is always something to review. Mirrored
  into the `code-engineer`, `test-engineer` and `quality-manager`
  definitions, since those are the roles that actually start things.

- Add four sections to `CLAUDE-workflow.md`, all directed by the-sponsor after
  reviewing two proposals and a decision register in the same conversation:
  **the agent roles and who improves them**, **project phases**, **telling
  running copies apart**, and **findings become well-formed issue drafts**.
  The short version of why: one session that plans, builds, tests and then
  certifies its own work has no independent check anywhere in it, and the
  published research on multi-agent development is consistent that a
  separate reviewer catches what a self-certifying implementer misses.
  Seven specialist agents now live in `~/.agent-data/agents/` and are governed
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
  this folder as its own working directory (the-sponsor wants to keep working
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
