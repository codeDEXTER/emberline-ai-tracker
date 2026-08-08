# Changelog — common-rules

## 2026-08-07 · rulecheck reads whether a project adopts the rules instead of assuming it (#61)

`bin/rulecheck` treated every directory under `apps/` as a project that follows
these rules. `idea-lab` does not, and says so in its own words: it is **v2**,
governing what happens *before* anything is agreed, and `LAB-RULES.md` opens
with "deliberately separate from `../common-rules/`" while `CLAUDE.md` adds
"no gates, no worktrees, no issues here — ideas are cheap on purpose."

So rulecheck reported `idea-lab has NEVER recorded a rules version` and would
have gone on reporting it forever. Two costs, and the second is the one that
matters:

- **Every session had to re-derive that it was a false alarm** and dismiss it.
  A permanent warning that is always wrong trains sessions to skim the warnings
  that are right.
- **The only remedy it offered was `--align`, which would have written a false
  record.** The stamp is load-bearing *because* it is trusted without
  re-checking — the next session inherits it and skips reading the rules. A
  wrong stamp is therefore worse than a missing one, and `--align` on a
  non-adopting project now refuses and says why rather than complying.

**Adoption is read from the declaration that already exists.** `README.md`,
"How a project adopts this", says a project adopts by adding a pointer to
`CLAUDE-workflow.md` near the top of its own `CLAUDE.md`. That pointer is now
the check. Deriving it means there is no second roster to drift — and drift is
not hypothetical: `CLAUDE-workflow.md:7` still reads "Adopted: **finance-tracker**
(2026-08-02), **pockets** (2026-08-02)" after `pip` and `mac-explorer` had also
adopted. A hand-maintained list of who follows the rules had already stopped
being true. *(Left alone in this PR — that line is prose in the rules file and
changing it is the user's call, not a side effect of a tool fix. Flagged in the
PR body.)*

Mentioning `common-rules` is deliberately **not** enough to count. idea-lab's
CLAUDE.md names it in order to disown it; a substring match on the folder name
would have kept the false alarm exactly as it was.

Two cases the naive version got wrong and this one does not:

- **An existing stamp counts as adoption on its own.** Rewording a project's
  CLAUDE.md must not silently un-adopt a project that has aligned before.
- **common-rules does not adopt itself.** Running rulecheck inside this repo —
  the usual way this was hit — reported the rules as never having recorded a
  version *of themselves*. It now says so plainly and exits 0.

`tests/test_rulecheck.py` covers all of it: the idea-lab case, `--align`
refusing to write the stamp (asserted on the filesystem, not on the message),
the stamp-implies-adoption rule, `--quiet` staying silent for a non-adopter so
the SessionStart hook does not print, common-rules never acquiring a stamp, and
a guard that the four real adopting projects are still checked — so a fix that
quietly stops checking everything fails the suite.

Exit codes now read: 0 aligned **or not an adopting project** · 1 behind · 2
cannot tell.

## 2026-08-08 · 7-DAY reads GitHub now, and REPORT is a live tab

Asked directly: *"why do you measure checklist, why can't you use git to
measure progress"* — and separately, that the one-off narrative completion
reports written for a few projects should be "in the app... tracked live."

**7-DAY was still checklist ticks after DONE moved off them.** The previous
entry fixed the DONE bar to score feature completion from issue closures, but
PROGRESS's 7-DAY figure kept reading the git log of hand-ticked `- [x]` boxes
in `CLAUDE-checklist.md` — a session could tick a box with no issue behind it,
or close an issue and never touch the checklist, and the two numbers on the
same screen told different stories about the same project. `7-DAY` now builds
its burnup from the register's own implementing issues' `closedAt`: the same
denominator `project_completion` already scores DONE from, so the two cannot
drift apart. A project whose register has no closed implementing issue yet
still falls back to the checklist history — labelled `checklist` on screen,
never blended silently with GitHub-sourced numbers.

**REPORT is a new section on every project's page**, sitting above BOARD:
completion %, features closed, features naming an issue, issues open, issues
closed in the last 7 days (with an unclaimed-issues callout), velocity, and
weekly token cost, plus the burnup chart. It costs no new fetches — every
figure is a rollup of what BOARD and PROGRESS already collect — so it
refreshes on the same cadence as the rest of the screen.

What it deliberately does not do: the narrative half of those one-off reports
(a wrong metric caught, dead code found, a missing test named) came from a
session actually reading code. That is investigation, not a query, and
nothing in a 5-second collector can re-run it unattended. REPORT says so in
its own footer rather than implying it replaces the written reports — those
stay as the historical record; REPORT is the thing that stays current.

## 2026-08-08 · The bar follows features now, and unclaimed closures are visible

Reported: *"in financial tracker i am closing issue, but the progress bar does
not increase."* Two separate causes, and fixing only one would not have
satisfied the report.

**The bar showed checklist ticks.** Closing a GitHub issue moves a feature's
percentage and never ticks a `- [x]` box in `CLAUDE-checklist.md`, so the most
prominent number on the row measured something the sponsor was not doing. It
now shows feature completion — the same arithmetic `whole_product` uses across
the estate, computed once in `project_completion` so the two cannot drift apart.
Checklist ticks remain the fallback for a project with no register, labelled
`% items` so it is never read as the same number.

**Measured before fixing anything**, because a bar reading the right thing
would still barely move: **18 issues closed on finance-tracker in a day, and 17
of them belong to no declared feature.** Only #127 was inside the register.
That is why the bar moved to 1% and stayed there — it was correct, and silent
about almost everything that happened.

So the estate view now says how much work the register does not cover:
`44 issue(s) closed in the last 7 days that no declared feature claims`. Neither
this proposal nor this fix decides whether those 44 belong inside a feature or
are legitimately excluded housekeeping — that is the sponsor's call, per
`CLAUDE-workflow.md`, and it could not be made while the number was invisible.

One test guards the render path specifically, not just the arithmetic: the unit
test on `project_completion` passed even when the bar was reverted to checklist
ticks, because nothing forced `render_all`'s actual HTML to use it. A second test
against the rendered output catches that regression — verified red before the
fix, green after.

## 2026-08-08 · Cap the strip, not the table

The previous fix capped `.cell.wide` to stop the sessions strip crowding out the
estate table. Both regions are wide, so it capped the table as well — the ALL
view then rendered **3 of 6 projects above a large empty gap**, which is worse
than the inverted priority it was meant to fix.

A CSS selector matching more than intended fails silently and looks like a
layout decision. The strip now carries its own class, and a test asserts the
bare `.cell.wide` rule constrains no height — verified by putting the over-broad
cap back and watching it go red.

Third fix in a row on the same screen, and the third one that only a screenshot
could have caught.

## 2026-08-08 · Fits the window it actually ships in

Opening the app — properly, at its real size, for the first time — showed three
more defects that every check I had run was blind to. The window is roughly
1180x760 of content; I had designed and verified everything at 1280x900.

**The estate table rendered 3 of 6 projects.** The sessions strip took ~240px
while the table showing every project got ~80px, so mac-explorer, pip and
pockets were simply not on screen — on the view whose entire job is "which app
is stuck". The priority was exactly inverted: the strip is a footnote and was
being treated as content. It is capped now and the table gets what is left.

**The header said `NEEDS YOU · 8` above five rows**, because drift was still
counted per project after being consolidated into one line. A header that
disagrees with the thing directly under it is worse than no header: it makes the
reader distrust both, which is roughly what "I don't know what to do" sounds
like.

**A band row was sliced mid-word** — "worst is pip at 34" cut in half at the
cap. Smaller cap.

None of this was visible to `curl`, to the test suite, or to rendering the same
HTML at a size the app never uses. The only thing that found it was looking at
the window.

## 2026-08-08 · The screen was working and useless, which is not the same thing

aashish: *"this app doesnt work. i dont know what to do."*

I had verified every change with `curl` and never once opened the window. It
renders fine. It is also useless, in three specific ways, all of which I built.

**The headline read `0% of declared scope`** while four features were declared
**done**. Completion came only from closed implementing issues, and a `built`
feature names none — the work predates the register. Proposal 05 already settles
this: the sponsor closes features and his State column is the authority. It now
reads **13%**. This was the first number on the screen and the one he asked for
by name.

**The NEEDS YOU band held 8 items, of which 1 was a decision.** The rest were
rules-drift rows and contested notes. Worse, the drift was largely
self-inflicted: every merge to common-rules bumps the version, so a day of work
in this repo pushed every project 28–31 versions behind and the band filled with
nagging about a number I had moved. #75 capped it at two rows plus a count,
which was not nearly enough. Drift is a *state*, the header already carries it,
and one line here says how bad it is and what to run.

That is the second time this exact failure has been built and the second time it
had to be measured on a live screen to be seen — a signal that never resolves
becomes wallpaper, and I keep re-creating it one level up.

**A footnote was being sliced in half** by the scrolling region's boundary,
which reads as a rendering fault. It also cited a closed issue number, which is
developer chatter on the sponsor's screen. Shortened.

The lesson is not any of the three fixes. It is that "the tests pass and curl
returns 200" answered a different question from "is this screen any use", and I
reported the first as though it settled the second, repeatedly, for a day.

## 2026-08-07 · A feature stops being counted as a ticket too

Implements #93, reported as the feature and issue lists being inconsistent —
which they were, because the same thing was in both.

A feature **is** a GitHub issue; that is how the register identifies it. So every
declared feature also appeared in the pipeline's queued list. Measured: **32 of
103 open issues were features**, and `QUEUED` read **95** when the real queue was
63. Per project it was every single one — 9 of 9, 9 of 9, 7 of 7, 7 of 7.

`pipeline_data` now excludes them from queued, merged and the in-flight mapping.
`QUEUED` reads 64 (not 63 — filing #93 itself added one, which is the count
moving correctly).

This is the defect proposal 10 removed once already, arriving from the other
direction. `IN FLIGHT · 19` counted eighteen git ahead-counts as work; this
counted features as tickets. **A feature is not a ticket to work — it is the
thing tickets roll up into**, and listing it as queued invites picking it up as
one.

The exclusion depends on `collect()` computing features *before* the pipeline, so
the keys exist to pass in. That ordering is load-bearing and invisible, so a test
reads the source and asserts it — verified by swapping the order and watching it
go red. Swapped back silently, nothing else would fail: the queue would just
quietly grow by 32 again.

## 2026-08-07 · The register is read from main, not from whatever the checkout is parked on

Implements #91. All four registers were merged; the Tower reported three.

pip's register was on `origin/main` while its working checkout sat a commit
behind, with another session mid-work in it. `feature_data` read
`proj["path"]/CLAUDE-checklist.md` — the working file — saw no table, and
reported **"no features declared"** for a project that had declared nine.

**A feature is declared when its register is merged.** Whether a particular
working copy has pulled is an accident of who is working where, and the answer
to "what is this product made of" must not move because of it. Same class of
defect as #73: an answer that quietly depends on local state it does not
mention.

`origin/main` first, then `main`, then the working file. The order matters and
is commented, because a *local* main can itself be behind — which is exactly the
case that produced this. The working file is a last resort rather than an error:
degrading to *less* scope than exists is the failure mode here, so an
unreachable remote must not drop a project to zero.

Reading from git also means an uncommitted register edit does not count yet.
That is correct rather than unfortunate, and it matches the rule the State
column already follows.

The estate now reports **32 features in 4 of 6 projects**, with pip's checkout
untouched — the overlap rule says do not reach into a surface another session
is holding, and fixing the Tower was the better answer than fixing their
checkout.

**One inconsistency is left open deliberately.** `checklist_progress` — item
counts, and so the burnup — still reads the working file, so a project can now
show features from `main` and item counts from a checkout that is behind.
Aligning them would make declared scope wholly a merged fact; leaving items on
the working tree keeps them a live signal of what a session is doing. That
changes what the burnup measures, so it is recorded on #91 for the sponsor
rather than decided in passing.

## 2026-08-07 · workflow.html catches up with the feature-register rule

#88 changed `CLAUDE-workflow.md` and did not update `docs/workflow.html` in the
same PR, which is exactly what `docs/README.md` requires and what
`tests/test_workflow_stamp.py` exists to enforce. **It merged red**: the stamp
said version 104 against rules at 130.

That test was written this morning, in this repo, for this failure mode — and
the rule it protects was still broken by the next rules change, by me, hours
later. The test did its job; the process around it did not, because the PR was
merged without the suite being run against the merge result rather than against
the branch.

The page now describes the register rule and is stamped 130.

## 2026-08-07 · Every project keeps a feature register, and the board stops losing features

Two things, found together because landing the first real registers is what
exposed the second.

**The rule.** `CLAUDE-workflow.md` now requires a `## Features` table in every
project's `CLAUDE-checklist.md`, in the shape pockets already used and the Tower
already parses. It is the only answer to "what is this product made of, and how
much of it is done" — a question the sponsor asked by name and which the estate
could answer for one project in six.

Worth being explicit about the tension, because it looks like a rule that was
already refused: **this is not proposal 08's logbook.** That was rejected for
imposing a per-task append on every session. A register changes when the sponsor
adds, renames or closes a feature — rare, and his act rather than a session's.
Nothing here asks a session to write anything when work lands. A project with no
register still reports "no features declared", never 0%.

**The bug.** Landing the registers immediately showed the board undercounting:
pockets declares **7** features and the board rendered **6**. The `version 2` one
parsed as kind `later`, there was no LATER column, and the grouping dropped it —
silently, since #70 merged. Any state the parser produced without a matching
column disappeared the same way, and a state the register did not spell out fell
through to `declared`, which had no column either.

There is now a LATER column, an unstated state parses as `next` rather than into
nothing, and an unrecognised state is parked in NEXT rather than lost — a
register can be hand-edited, so an unexpected value is something to correct, not
a reason for a feature to stop existing. Verified across all four registers:
7 + 9 + 9 + 7 declared, 32 rendered.

A quiet undercount is worse than a wrong column: the board is meant to answer
what the product is made of, and an undercount makes it a wrong answer that
looks right. The guard is verified by removing the LATER column and watching it
go red.

## 2026-08-07 · The heavy collectors stop blocking the first page too

Follow-on to #86, found by merging #76's cost work into it and measuring the
combination rather than assuming the two composed.

#86 stopped a render waiting for a *recollect*, but the **first** render is
deliberately synchronous — a page with no data is worse than a slow first page.
With cost added, that first page took **57 seconds**. The app looked hung on
launch, which is a worse defect than the one #86 fixed.

So the three collectors with their own long TTLs — `staleness` (fetches),
`history_data` and `cost_data` (walk git and every transcript, 26.8s cold) —
now go through `cached_async`: return whatever is cached immediately, refresh in
the background. They return None on the very first call, which every one of
their renderers already treats as absence: no staleness line, no history yet, no
cost note.

Cold first page: **57s → 5.2s**. Warm: ~2ms. History appears at ~24s, cost at
~56s, and the window is responsive the whole time. A region arriving a few
seconds late is far better than a window that will not open.

Their private cache blocks were removed rather than left alongside — two caches
over one value is how a number ends up stale in a way nobody can reproduce.

One test failure here was the test's fault, not the code's: the single-refresh
assertion saw two because the previous test's background thread was still alive.
Fixed with a release event and a join in `tearDown`, since a test that fails
from its own leftovers teaches the next person to distrust the suite.

## 2026-08-07 · Cost is per week, because per feature attributes nothing

Implements #76, rescoped by measurement rather than by preference.

**Per feature attributes 0%.** Measured across the estate: of 67,393,007 tokens,
**96.8%** sit in `(main checkout)` and `(management)` pseudo-tasks and **3.1%**
in worktrees that have since been deleted. Zero was attributable to a declared
feature. Two structural reasons, neither fixable in the Tower: most work never
happens in a task worktree at all, and the ones that do have their key —
the worktree directory — destroyed by the act of landing. Built as originally
specified, #76 would have shipped a column of dashes and a footer holding all
the spend. That was reported before writing any of it.

So the unit is the week. **"What did this week cost, and what moved"** sits on
one line of the PROGRESS section beside the burnup, and a 7-DAY COST column on
`ALL` makes it comparable across projects. On the live estate that immediately
reads: finance-tracker **27.6M tokens for +14 items**, common-rules **18.2M**
against no checklist to move at all.

**`spend` now carries per-day tokens through `tasks_for`.** `_read` already
counted them and the aggregation dropped them. This matters more than it looks:
summing whole task totals for tasks that merely *touch* the window overstates
the estate's week by **4,492,100 tokens — 7.1%** — because a task spanning the
boundary gets counted entire. That is a wrong answer rather than a rounded one,
and it was measured by building the tempting version and comparing.

A test asserts **no cost appears against any individual feature**, which is the
number the data cannot support and therefore the one most likely to be added
back by someone who has not seen the 0%.
## 2026-08-07 · A render never waits for a collection

Implements #86, reported by aashish as *"this app is slow and time
non-responsive. it also shows outdated data."*

**The slowness was real and reproducible.** Measured against the running app:
every recollect blocked the HTTP response for **~4 seconds**, and with a 5s
cache against a 10s auto-refresh that meant the window froze for four seconds
out of every ten.

**The "outdated data" was not.** Checked against ground truth, the rules stamp,
the decision count and the absent staleness line were all correct. What was
wrong was *lateness*: the visible page ran up to 14s behind because each refresh
took 4s to arrive. It read as stale because it was late — a useful distinction,
because the fix for one is not the fix for the other.

`collect()` now serves the cached snapshot immediately and refreshes in a
background thread, one at a time. Requests went from ~4s every other hit to
**~2ms**, warm or cold. The first render still waits, deliberately: a page with
no data at all is worse than a slow first page.

The cost of not blocking is that a snapshot can be a cycle old, so **the page
now states its own age** — `data is current` or `data is 9s old · refreshing in
the background`. A number whose age is visible is honest; a number that is
silently late is the thing that was reported.

**A far worse defect turned up while measuring.** In the unmerged #76 branch,
`cost_data` declared `COST_TTL`, `_cost_lock` and `_cost` and never referenced
them, so it rescanned every transcript on every 5-second collect. Cold, that
call takes **26.8 seconds**. It would have shipped with #85 and made the app
close to unusable. Fixed on that branch, and it is the honest argument for
measuring rather than reviewing: nothing about reading the code made it obvious,
and the app being slow is what led to it.

The no-blocking guarantee is pinned by tests, verified by reinjecting the old
inline collect and watching them go red — including one asserting only a single
background refresh runs at a time, since otherwise a slow sweep spawns a thread
per request and does the same expensive work many times over.

## 2026-08-07 · The Tower switches by project

Implements #81. The tab bar is the project list now — `ALL · pockets ·
finance-tracker · …` — and a project page carries everything about that app at
once: its features by state, its burnup and velocity, its queued and merged
work, its sessions. No second click, no filtering by eye.

**The lenses are retired rather than re-cut.** BOARD / LEDGER / PROGRESS
answered a real constraint — six projects' data does not fit in 900px. One
project's does, so changing the axis removes the need for the split entirely.
`render_ledger` is deleted with them: a cross-project feature table is exactly
what a project-first screen does not want.

**NEEDS YOU stays above the tabs and is never filtered**, and that is enforced
rather than intended: `render_needs_you` takes no project argument, so it cannot
be filtered by construction. A decision waiting in an app the sponsor is not
looking at must still reach him, and filtering the band is the tempting
simplification that would make the screen actively worse. Verified by
reinjection — adding a `project` parameter turns the guard red.

**The whole-product figure moved from the retired LEDGER to `ALL`.** A statement
about every project cannot sit on a page showing one.

`?project=` is URL-borne for the reason `?view=` was: the page re-requests
itself every 10s and DOM state does not survive it. Verified in a browser again
here — the stamp advanced 20:33:36 → 20:34:21 through a real reload with pockets
still selected.

Two things worth recording about the build. Deleting `render_ledger` also took
`sparkline` with it, because that function sat between it and `render_progress`
— caught by the tests immediately, restored from main, and a reminder that
cutting by line range between two named functions is only safe if nothing has
been inserted between them since.

And the screen reported on itself mid-build: the staleness line from #73 read
*"running 55cbe16 · main is 4 ahead"* while another session's spend work landed.
That is exactly what #73 was for, and it prompted the merge before this was
committed rather than a conflict at PR time.

## 2026-08-07

- **`spend` was hiding 88% of what it measured, and now counts management
  separately.** Reported as "pockets shows zero tasks"; the cause was much
  wider. Attribution read the **first** `cwd` in a transcript — the launch
  directory — and a management session launches from `apps/` and only enters a
  project later via `EnterWorktree`. Every one of them was therefore dropped
  from every project. `spend today` had been saying management chats are 88% of
  all spend the whole time; the per-project figures simply excluded them.
  Measured: pockets reported **0 tasks** on a day it spent 836k output tokens
  across four agents; finance-tracker reported **4M** against a real **31.7M**.

  Two fixes were tried and rejected before this one, and both are recorded
  because the reasoning matters more than the patch. *Any cwd inside the
  project* counts a one-line `cd` in a bash command as a session's work — it
  put five sessions in two projects at once. *The dominant cwd* stops the
  double-counting but silently loses a task, because a session that spent more
  records elsewhere stops being that task at all.

  The accepted split is the sponsor's call: **task rows measure worktree
  sessions only, and orchestration gets its own row.** A session that spent all
  its time in exactly one worktree is that task; one that never left the main
  checkout stays `(main checkout)` as before; one that moved between worktrees
  is `(management)`. The point is that no single label is honest for a session
  that legitimately spans ten worktrees — charging it to one over-claims that
  task and hides nine others.

  What this does not do: split a management session's cost across the tasks it
  served. That would make every task row a fraction with no session behind it,
  and it was rejected for the same reason the hand-written log was — a number
  nobody can trace is not a measurement. Management cost is now visible and
  attributed to a project; which task inside it consumed what is still unknown.
## 2026-08-07 · The Tower switches by project, not by lens

Proposal 13, from the sponsor looking at what had just been built: *"rather than
switching board, ledger and progress, I should be able to switch between
projects with all details."*

He is right, and the interesting part is why the lenses existed at all. BOARD /
LEDGER / PROGRESS answered a real constraint — six projects' features, history
and flow do not fit in 900px, so the estate view had to be cut three ways. But
**one project's data fits easily**: the largest is pockets at 7 features, 6
sessions and 9 history points; finance-tracker is 3 sessions and 21 history
points. Change the axis to project and the split stops being necessary at all,
rather than needing re-cutting per project. The lenses were the answer to a
volume problem that disappears when the question changes from "show me a way of
looking" to "show me one app".

So the tab bar becomes the project list, a project page composes everything that
already exists filtered to one app, and `ALL` becomes a one-line-per-project
estate summary.

**NEEDS YOU stays above the tabs and is never filtered.** It is the autopilot's
blocking state: a decision waiting in an app the sponsor is not currently
looking at must still reach him, and filtering it is the one change that would
make the screen actively worse rather than better.

Worth recording plainly: the `ALL` page is almost exactly the **Portfolio**
option from proposal 11 — the one recommended then and turned down in favour of
Ledger and Board. That recommendation was wrong *at the time*: as the only view
it hid individual features behind an expand, and with one register declared it
had nothing to compare. As a summary above per-project pages it is the right
shape, because comparison is what a top level is for. Rejecting it as the answer
and adopting it as the roof are both correct, a day apart.

The costs are stated in the document rather than discovered later: the
cross-project feature table goes, "everything blocked anywhere" becomes six tab
visits, and the tab bar grows with the estate — six fit, twelve would need
grouping.

Cut as #81. #76 (cost per feature) was unblocked by #78 the same hour and
immediately re-queued behind #81, because cost is a column on a feature list and
#81 moves where that list lives.

## 2026-08-07 · spend can be asked about a project by path

Implements #78, which exists only to unblock #76 (cost per feature on the
Tower).

`bin/spend` measured everything through `_tasks_here()`, which derived the repo
root from the **current working directory** and took no path. The Tower cannot
use that: its collectors run in a thread pool, and a process-global `chdir`
there is the kind of race that produces a wrong number occasionally rather than
an obvious failure — the worst way for a cost figure to be wrong.

So `_repo_root()` takes an optional path, `tasks_for(path=None)` is the public
form, and `_tasks_here()` is now a thin wrapper over it. **An access change, not
a measurement one**: task grouping, token counting and the CLI are untouched.
Checked project by project — the path form and the CLI agree on all five,
including finance-tracker's 4,018,382 tokens and the two that legitimately have
none.

**The first version of the no-chdir test was useless and passed anyway.** It
called `tasks_for(repo)` from inside that same repo, so a reinjected `chdir` to
that directory changed nothing observable and the guard went green against the
exact bug it existed to catch. It now runs from outside the project, and
reinjecting the chdir turns it red.

## 2026-08-07 · The Tower's whole open queue, in one pass

Implements #73, #74, #70, #71, #75, #66 and #63 — every open Tower issue but
one. All seven touch `bin/tower`, so they went through as a queue on one branch
rather than as parallel branches racing on a single surface.

**The two corrections came first, and not because they were small.** A screen
that can be silently stale and an amber warning that is wrong three times in
five undermine every other number on it.

`#73` — Tower.app runs a pinned checkout refreshed only by
`build_towerapp.sh --install`, so it falls behind on every merge. Against the
live pinned copy it was **5 commits behind**; two days behind before today's
rebuild, serving the pre-proposal-09 screen while every session reported those
problems fixed. The header says so now, and says nothing when current — a
permanent line would be the wallpaper problem #75 exists to fix. A checkout
*ahead* of main is not stale: that is a session working, and warning there would
put the line on the screens most likely to be read.

`#74` — three of five contested pairs were `AGENT-LOG.md`, which carries
`merge=ours`. A file with a merge driver cannot conflict; that is the point of
#44, #45 and #57. It asks `git check-attr` rather than parsing `.gitattributes`,
so glob rules work and the answer is the one git will use at merge time. A
failure degrades to warning rather than silence: over-warning is recoverable,
under-warning hides a real collision.

**PIPELINE is gone, replaced by BOARD / LEDGER / PROGRESS tabs** (#70, #71, #66,
#63). It replaces rather than joins: PIPELINE was already a board of work by
state, and a board of *features* by state beside it would have been two boards
of one shape at different altitudes.

The tabs are links, not CSS state, because the page re-requests itself every
10 seconds and the DOM does not survive that — measured, then verified in a
browser by watching the timestamp advance through a real reload with LEDGER
still selected.

`PROGRESS` is a third tab rather than a sixth region, because the screen is
900px and detail belongs behind a tab. It draws a burn**up** — two lines, done
and total — from each checklist's own git log. No new record file and no
revival of proposal 08's rejected logbook. The gap between the lines is the
whole point: finance-tracker really went `4/24 → 18/51`, completing 14 items
in seven days while its percentage fell, because scope grew faster. Nothing is
smoothed or clamped monotonic — mac-explorer's total genuinely went 8 → 5, and
a dip is a re-scoping, which is information. Velocity names its window; there is
no ETA, no projection, no "on track", by the rule proposal 08 set.

**Two things were found by looking rather than by reasoning.** Escalating rules
drift put *five* rows in the band, because every project is 8–18 versions
behind — recreating the wallpaper one level up, which is the exact failure #75
was meant to fix. The worst two get rows and the rest is a count. And
`project_tag` shortened names into the prose: "idea has never recorded a rules
version". The tag is built for compact chips, so the band uses full names.

**One test was wrong and the test was fixed, not the code.** A branch name typed
into the sponsor's own State column is his prose, and rendering it is faithful;
the defect #65 fixed was the Tower *deriving* labels from directory names. The
guard now asserts the board and ledger take no worktree argument at all — they
cannot leak a name by construction.

**#76 is deliberately not implemented, and the reason is recorded in the code.**
Cost per feature needs `bin/spend`, whose `_tasks_here()` derives the repo root
from the *current working directory* and takes no path. Reaching it from a
collector would mean a process-global `chdir` inside a server that fans
collectors across threads — the kind of race that yields a wrong number
occasionally rather than an obvious failure. #76 puts changing `spend` out of
scope and says it is its own issue, so that is where this stops. The join it
needs already exists: spend keys tasks by worktree name, and `feature_of_issue`
maps a worktree's issue to a feature.

Tests: 34 → **73 passing**. The new guards were verified by reinjection —
putting the staleness line back on permanently, and removing the contested
filter — not by trusting a green run.

## 2026-08-07 · Five things the Tower should know, and doesn't

Proposal 12. Every finding came from using the screen for a day rather than from
thinking about dashboards, and two of them sharpened under checking.

**The Tower cannot tell you it is stale, and it is stale constantly.** Tower.app
runs `bin/tower` from a pinned checkout refreshed only by
`build_towerapp.sh --install`. Measured two hours after a rebuild: the app on
`208c789`, main on `cd19f10`. It falls behind on every merge. Before that
rebuild it had been two days behind, serving the pre-proposal-09 screen — the
truncated names, the 310px void — while every session reported those fixed. A
status screen that is confidently wrong with no hint that it might be is the
worst defect one can have, so this is a correction rather than a feature (#73).

**Three of five contested warnings are false by construction.** All three are on
`AGENT-LOG.md`, which carries `merge=ours` — confirmed in pockets and
finance-tracker. A file with a merge driver cannot conflict; that is the entire
point of #44, #45 and #57. `contested_pairs()` is `whoelse`'s logic, predates
the merge drivers, and has never been told they exist. Three in five is enough
to teach a person to ignore amber, which costs the two that are real (#74).

**Four million tokens are measured and none reach the screen.** `bin/spend`
reports 4,018,382 across 8 finance-tracker tasks. Note how it labels them —
`adoring-euler-ba942f`, `compassionate-bassi-fd5327` — which is exactly the
branch-name noise proposal 10 removed, and exactly why cost has never been
useful here. Cost per worktree is trivia; cost per *feature* is a decision.
#65's register plus `worktree_issue()` is the join that turns one into the
other (#76).

**A warning that never resolves is wallpaper.** `5 behind: finance-tracker,
idea-lab, mac-explorer +2` sat unchanged in the header through a dozen merges,
four proposals and six issues. Against version 114 the real spread is pip 11
behind, mac-explorer 9, finance-tracker 8, pockets 2, idea-lab never stamped —
and the screen renders all of them identically. It has to be able to escalate or
it will be tuned out again within a week (#75).

**The decision queue is under-reported.** Open PRs reach NEEDS YOU only when
they belong to a worktree with a mapped issue, so a PR from an unmapped branch
is invisible. How many decisions are waiting, and how long the oldest has
waited, is the number that says whether the autopilot can keep going without the
sponsor. The age is the part that matters: four things waiting ten minutes is a
working autopilot, four waiting two days is a stalled one (#75).

Three things are ruled out in the document rather than left to drift back in:
no new region (900px is already tight and #70 is about to take PIPELINE's
space), no forecast of any kind (proposal 08 refused an ETA on four days and #63
held the line on six — cost and drift both invite "at this rate…"), and no new
bookkeeping, since every figure above is derivable today and the logbook was
rejected once already.
## 2026-08-07 · Three ways to show the features, and the two he picked

Proposal 11, a design exploration rather than a proposal with one answer.
Building #65 is what made it necessary: the information was right and the
layout it landed in was the one the deleted regions left behind. Measured on
the running screen — five "no features declared" lines shouting over the one
project with real features, every feature title truncating because the region
sits in the 2fr half of a 3fr/2fr split despite being the spine, blocked
features drawing an empty bar that reads as 0%, and no whole-product figure
anywhere.

Three structurally different answers were drawn, not three skins: **A** a
cross-project feature ledger, **B** a board with columns by state, **C** a
portfolio of one line per project with the whole-product figure first.

**aashish chose A and B.** Recorded plainly, because it went against the
recommendation: the paper argued for C first with A later, and argued against
building B at all on the grounds that it has no home for a completion
percentage and three of its four columns are empty on today's data. He read
that and chose otherwise. It is his screen. The original reasoning is left
unedited in the document so the disagreement stays visible rather than being
tidied into agreement after the fact.

Taking both raised two questions the options paper never had to answer, and
both are settled in the document rather than left to be discovered mid-build.
**The completion figure lives in A's header** — taking A alongside B resolves
the objection to B instead of overriding it, and B gets no bolted-on figure.
**The two views do not share one screen**: B is the region on the main screen,
because "what is running, what is done" answered by position is the job that
screen exists to do, and **A becomes its own `/features` route**, which is the
same move the Tower already makes with `/pulse` and `/session/<id>`. A gets
better as registers land without ever making the main screen taller, and the
900px budget from #56 is untouched.

Three fixes land with whichever option, since they are corrections rather than
choices: a blocked feature gets no bar at all, the features region moves to the
wider column, and undeclared projects collapse to one grouped statement.

**Drawing the merged screen changed one of the two issues before either was
built.** Assembled, A and B collide in two ways neither had alone. The board and
the existing PIPELINE are the same widget at different altitudes — one counting
issues by state, one counting features by state — which is the noise this
redesign set out to remove, reintroduced somewhere new. And four columns in the
wider half of a 3fr/2fr split are ~150px each, so titles would truncate *worse*
than they do now, which is the defect #70 exists to fix.

Both have one answer: **the feature board replaces PIPELINE rather than sitting
beside it.** It follows from the ask — features, not issues, not branches — and
it gives the board the full width four columns need. Issue-level flow moves to
`/features`, where it is detail rather than noise. #70 was rewritten to say so
before any code was written against it.

**Then the sponsor chose tabs, and a measurement decided how to build them.**
Both views now live in one full-width region where PIPELINE was, switched by a
tab — and the obvious dependency-free implementation is broken here. The Tower
re-requests itself every 10 seconds, and CSS tabs (hidden radios plus a
`:checked` sibling) hold their state in a DOM that every reload destroys. Tested
against a 3-second refresh: selecting LEDGER came back on BOARD, while a
`?view=ledger` query string survived intact.

So the tabs are **links**, and the server renders the chosen view —
`/?view=board` and `/?view=ledger`. The meta refresh re-requests the current URL
including its query string, so the choice sticks, and no JavaScript is involved,
which keeps proposal 09's rule that the Tower's only interaction is a link. It
also retires the separate `/features` route drafted an hour earlier: a query
string already is one.

Worth recording as a near miss. Building CSS tabs would have produced a screen
that silently flipped back to BOARD every ten seconds, and the blame would have
landed on the tab rather than on a refresh nobody was thinking about.
## 2026-08-07 · The Tower reads the features register, and names no branches

Implements issue #65, the core of proposal 10. The screen's spine is now each
project's declared `## Features` table. Nothing is inferred.

**What was actually wrong.** Three sources, all of them the wrong thing:
worktree directory names, issue title prefixes (`title.split(":")[0]` — two
issues shared a "feature" only if somebody typed the same words before a
colon), and `##` headings, which in three of four projects are priority
buckets. `Now` is not a feature and never finishes.

**No worktree or branch name is rendered anywhere now** — not in a label, not
in a hover, not in a disclosure. `tests/test_tower_render.py` pins it across
every renderer that takes a worktree, verified by reinjecting a name into the
strip's hover and watching the guard go red. The `<details>` listing 18
worktree names from #51 is a count instead: a worktree with no mapped issue has
nothing to identify it *by* except its directory.

**The parsing subtlety that would have corrupted every percentage.** A register
row reads either `in flight — issue #1` or `blocked by #2`. Those are opposite
facts. Reading every `#N` in the row would have made each blocked feature
inherit its blocker's progress, so `IMPLEMENTS` and `BLOCKED_BY` are separate
patterns and only the first ever reaches a figure. On the live register that is
the difference between "0/1 issues" and five features silently claiming
Milestone 0's completion.

**Completion is split, per proposal 05.** The percentage is derived from issues
— a measurement nobody maintains. **Done** comes only from the sponsor's State
column. A feature whose tickets are all shut but which he has not closed reads
`100% · awaiting your close`, which is the honest state and a useful prompt.

**Undeclared scope is still not zero.** Only pockets has a register, so
finance-tracker, pip and mac-explorer read "no features declared — 18/54
checklist items ticked, against no product definition". Proposal 08's rule, and
it binds harder here because a completion figure is the thing the sponsor asked
for by name: a number over an invented denominator would be worse than none.
`feature_data` calls `PULSE.checklist_progress` rather than counting ticks with
a local regex, specifically so the "lines that look like items but could not be
parsed" warning survives instead of being quietly dropped.

**Deleted:** `compute_hulls` (dead since #52), `burnup_data`, `render_burnup`
and the per-package bars, and the `groups`/`prefix_total` payload that existed
only to feed the hulls. `AT THE WALL` also went — it named worktrees and said a
second time what the NEEDS YOU band says first and larger.

Fixed on the way, having been recorded on this issue during #64: the sessions
summary did not sum. `22 · 0 active, 1 needs you, 4 idle` left 17 of 22
sessions in no bucket, because the contested branch assigned a class and
counted nothing. Every session now lands in exactly one bucket and the line
reads `11 · 1 needs you, 5 contested, 5 idle`.

Also fixed: `graph_err` included `hulls_err`, so a failure inside a collector
rendered nowhere would have blanked both NEEDS YOU and SESSIONS.

## 2026-08-07 · Handovers and the commit ticker come off the Tower

Implements issue #64, the first of proposal 10's queue. Two regions gone:
HANDOVERS was two AI sessions coordinating, the EVENT TICKER was commit
subjects. Neither is something the sponsor needs at a glance — *"I don't want
to know what internal communication is going on."*

**The point was the space.** At 1280×900 the two regions were 453px and 186px.
Removing them, and correcting a row template that still declared a row for them,
**doubled the pipeline's visible height from 211px to 425px** — the region that
had room for about four rows since #56. Work packages went from 211px to 425px
against 478px of content, so it now very nearly fits without scrolling at all.

**What was deliberately kept.** `/session/<id>` survives: it is reached from the
sessions strip, and it still shows what a session last said *and what was handed
to it*, so the cross-session-message parsing (`_XSM`, `_first_sentence`,
`resolve_cwd`) stays. Only the region that listed those messages is gone. This
was checked rather than assumed — the issue asked for exactly that check, and
`_first_sentence` turned out to be shared between `message_edges` and
`session_digest`.

**What went with them, which is worth naming.** `collapse_repeats()`, `times()`,
`_epoch` and `DEDUP_WINDOW` — the byte-identical de-duplication built in #52 —
had no subject left once both regions went, so they are deleted. That is #52's
work being removed two commits after it landed, deliberately: the regions it
made honest are not on the screen any more. Git keeps it if #66 wants it back.
`session_owner_dirs()` also went; it had already been dead on main.

**Test coverage was retargeted rather than dropped.** The de-duplication tests
are gone with their subject, but the escaping test — which happened to use
`render_handovers` — now runs against `render_strip` and `render_needs_you`
with a payload that also tries to break out of a `title` attribute. Losing that
guard because the renderer it happened to be written against was deleted would
have been the quiet kind of regression.

Found while verifying, not fixed here: `render_strip`'s summary line does not
sum (`22 · 0 active, 1 needs you, 4 idle`) because the contested branch
increments no counter. Mine, from #52, invisible until many worktrees were
contested at once. Recorded on #65, which rewrites that function.

## 2026-08-07 · Proposal 10: the Tower has been reporting the plumbing

aashish, on the screen proposal 09 had just finished: *"it doesn't help when you
are saying some random branch name. What features are done, what is the degree of
completion of the whole product, and what things are running. I don't want to
know what internal communication is going on."*

He is right, and the cause is that the Tower reads three things that are all the
wrong thing: **worktree directory names**, **issue title prefixes**
(`title.split(":")[0]` — two issues share a "feature" only if someone typed the
same words before a colon), and **`##` headings in `CLAUDE-checklist.md`**, which
in three of four projects are priority buckets. `Now` is not a feature and never
finishes.

**Features already exist as a first-class idea in these very rules** — "the user
owns features, the AI owns issues" — and **pockets already declares seven** in a
register with states and linked issues. The Tower has never read it. That is the
whole diagnosis: not a labelling bug, a wrong source.

**The honest blocker, and it is not the Tower's.** "Degree of completion of the
whole product" is a fraction, and the denominator exists for **one of four**
active projects. finance-tracker, pip and mac-explorer have never declared what
their features are, and there are no GitHub milestones anywhere. A percentage
across the estate would be a number over an invented denominator — the same lie
proposal 08 refused when it insisted a project with no checklist reads "no
declared scope", never 0%. So those three render "no features declared" until
their registers land.

Draft registers for all three were written the same day and are with the sponsor
for correction. Creating and scoping features is reserved to him, so they are
proposals: 9 candidates for finance-tracker, 9 for pip, 7 for mac-explorer, each
listing the open issues that roll up into it — which is what makes a percentage
computable, and also the honest test of whether a feature is real.

**Progress does not need the logbook proposal 08 rejected.** The history is
already on disk and unread: the tick count at any past commit is recoverable from
`git log` of each checklist, and the register's issues carry real close
timestamps. finance-tracker has 20 such revisions, pockets 9, pip 11.

Two decisions taken in-role rather than asked. **A feature's percentage comes
from its issues; "done" comes only from the sponsor's State column** — proposal 05
already says he closes features, so a feature whose tickets are all shut reads
"100% · awaiting your close". And **the per-package bars are dropped**: with
features as the spine they measure the filing structure again.

Cut into a queue on one surface — #64 (handovers and ticker off, pure removal),
#65 (features as the spine, no branch names anywhere), #66 (what moved today) —
plus #63 for burnup and velocity, which is independent of all of it.

## 2026-08-07 · derecord corrects a changed rule instead of freezing it (#57)

`bin/derecord` installed `.gitattributes` rules by asking *"is there a line for
this path?"* and nothing more. Once a pattern was present its value was frozen
forever: changing a rule in `gitattributes-for-projects` silently failed to
reach any project that had already adopted, **and the script reported success**.

Its own header called it "Idempotent: run it as often as you like." That was
true in the weak sense — running twice added nothing twice — and false in the
sense the header invites you to rely on, which is that running it makes the
project match the shared rules.

**It had already bitten.** `AGENT-LOG.md` moved from `merge=union` to
`merge=ours` earlier the same day, because the log became generated output and
union-merging generated output interleaves two tables into a file that is
neither side's truth. finance-tracker was corrected by hand; **pockets was still
on `merge=union`**, and `derecord` on it printed `0 record rule(s) added` and
`is done`.

The check is now "is there a line for this path *with this value*?", and a stale
value is rewritten in place. Local rules for patterns the shared file says
nothing about are never touched. The output says `added` / `corrected` /
`already matches the shared rules` rather than only ever counting additions.

`tests/test_derecord.py` covers it: a stale value is corrected, missing rules
are still added, unrelated local rules survive, a second run is a genuine no-op,
and the success wording cannot come back. Verified by running the new tests
against the **old** script first — two failed, which is the only way to know a
guard guards anything.

**Behaviour change for adopted projects:** re-running `derecord` now rewrites a
record-file merge strategy that has drifted from the shared rules. Run it once
per project to pick up the `AGENT-LOG.md` change.

## 2026-08-07 · Proposal 09 is built

Status flip only, no behaviour: `accepted` → `built`, in the document's
`<meta>`, its visible chip, and the index row — the README derives the index
from the documents, so all three have to agree or the table is lying.

All four issues are merged to main: #50 (d00ecd5 lineage), #51 and #52 (dd8dd0e),
#56 (d00ecd5). `built` is the first use of that status in this folder; the
vocabulary has carried it since the index was written and nothing had earned it
until now.

The chip is `--accent` rather than the `--gain` an accepted proposal gets, so
built and accepted are distinguishable at a glance on the proposals index —
otherwise the only difference is a word in a table cell.

## 2026-08-07 · The Tower fits its window, and stops growing with the tree

Implements issue #56, which finishes proposal 09. **The page now fits 1280×900
exactly** — verified in a browser at 900px, and again at 820px where the caps
must *not* apply.

**The issue was filed on a diagnosis that turned out to be wrong, and that is
the useful part of this entry.** It said the pipeline was "the last 780px
between the screen and one glance" and that collapsing two of its lists would
get under budget. Measured by hiding whole regions and re-reading the page
height, at 1280 wide:

| state | height |
|---|---|
| before | 1,792px |
| **entire pipeline region deleted** | **1,196px** |
| pipeline *and* handovers deleted | 912px |

Deleting the whole pipeline still overshot by 296px. The reasoning error was
forgetting the grid: the page is
`header + band + max(pipeline, work-packages) + max(handovers, ticker) + strip`,
so work packages (472px) and handovers (453px) set a floor that no amount of
pipeline cutting reaches. Once the pipeline drops below 472px every further chip
removed buys exactly nothing.

**So the fix is not a cut at all.** The regions are capped and scroll inside
themselves. Nothing is dropped, nothing is hidden behind a disclosure, and the
page fits by construction rather than by tuning.

That last part is the real point. The page height was a *function of how much
work exists* — it went 1,721 → 1,792px during the hour #51 and #52 were being
built, purely because worktrees were added. Any fix that works by cutting
content would have gone out of budget again on its own the next busy week.
aashish chose this over cutting content for that reason.

**Two CSS rules do all the load-bearing work, and both were wrong first.**
`align-items:start`, inherited from the uncapped layout, makes a grid item size
to its content and overflow its track — so the cap never binds and the scrollbar
lands back on the page, looking exactly like the cap "not working". Same net
effect if `min-height:0` is missing. `tests/test_tower_render.py` pins both,
verified by reinjecting `align-items:start` and watching it go red, because
either one reads as harmless in review.

The band is capped too, at 22vh. Unbounded, three waiting items took 28% of the
screen and squeezed the pipeline to 165px — it is the most important region and
still must not own the window.

Below 1001px none of this applies: a narrow window is a browser being read, not
the wall screen, and locking that to the viewport would squash six regions into
nothing. It stays a normally scrolling single column.

No behaviour change for any adopted project: this is `bin/tower` and its tests.

## 2026-08-07 · What needs you is first on the Tower, and the graph is retired

Implements issues #51 and #52, the last two of proposal 09. Built as one branch
rather than two: both re-cut the same surface, and `CLAUDE-workflow.md` says two
issues that touch the same file are one issue or one queue — running them in
parallel is the #30/#31 collision class.

**The two things that needed him used to be two circles among 23.** They are a
band at the top now, in words, at 17px: the issue title, the project, why, and
how long it has waited. When nothing needs him it collapses to one line and
gives its height back — reserving empty space is the failure mode this proposal
exists to fix, so the empty state had to be a line and not a box.

**`IN FLIGHT · 19` was an 18x overstatement.** One of those nineteen was a
mapped issue; eighteen were git ahead-counts wearing the same chip. In flight
means a mapped issue now, and the ahead-of-main worktrees collapse into a
`<details>` that expands in place — collapsed, not hidden, and no JavaScript.

**The graph from concept 07 is retired, not deferred**, on aashish's call. 615px
bought 23 labels in a 4-column grid where position was enumeration order, size
and fill were constant, and one edge ever rendered. It is a 117px strip of state
dots — measured, against the ~118px the proposal estimated. Every worktree is
still reachable: the hover carries the name, the mapped issue and the age *in
full*, because a title attribute has no width to fit and so cannot truncate. The
six worktrees that have a transcript link through to `/session/<id>`; the other
21 have no session to open and render as plain dots rather than dead links.

The one contested pair the graph ever drew — as a 470px diagonal with its
caption floating unanchored at the midpoint — is a row in the band now, which is
where an actionable collision belongs.

**Repeated events collapse, and only byte-identical ones.** Four of nine ticker
lines were the same event recorded by four agent logs a minute apart. The window
is 900s and the count is always shown. A row differing by one character stays
its own row: the claim is "this is literally the same event N times", and
anything looser hides real events. `_epoch` returns 0.0 on an unparseable stamp,
which puts a row outside every window and leaves it *uncollapsed* — the safe
direction, and `tests/test_tower_render.py` pins it, because the tempting
implementation folds two junk-stamped rows together on the strength of both
being equally unparseable.

**One collector change, and it is the same shape as #50's.** `needs_input` was a
set of names, so the reason and the wait were computed and thrown away — the
screen could say "needs you" but never why or for how long, which is most of
what the band is for. It is a dict now. Same two conditions, same inputs,
nothing new collected.

**The no-scroll budget still is not met, and this says so rather than claiming
it.** The page is **1,721px at 1280 wide**, down from 2,283px after #50 and
2,241px before any of this. The target is 900. What remains is the pipeline
column at 780px — eight queued chips, four merged, and the wall — which neither
of these issues touches. Closing the rest means cutting the queued list, and
that is a content decision nobody has taken yet, not something to slip in here.

No behaviour change for any adopted project: this is `bin/tower` and its tests.

## 2026-08-07 · The Tower is HTML now, and stops cutting words in half

Implements issue #50, the first of proposal 09's three. The page was one
hand-positioned SVG: every `render_*` had the shape
`(data, x0, y0, width) -> (svg, bottom_y)` and `render_page` threaded `bottom`
forward to stack regions. That is a layout engine missing text measurement,
intrinsic sizing and reflow — and all three absences were visible on the live
screen. It is CSS grid now. **198 absolute `x=` coordinates became 0.**

**Nothing is cut mid-word any more.** Eight hardcoded `[:n]` slices existed only
because SVG `<text>` cannot wrap; they produced `arm-f-filin`, `arm-b-contr`,
and a pipeline row that stopped one character short of "lines". Fitting is CSS's
job now — the card clamps visually and keeps the whole string in a `title`
attribute, of which there are **85 where there were none**.

**One collector change, and it was asked for rather than assumed.** Issue titles
were cut to 22 characters inside `collect()`, so no amount of CSS would have
shown them in full — "Tower: the screen fits its window..." rendered as "the
screen fits its…". That cut existed because the label had to fit inside a
25px-radius circle. aashish agreed to move it to CSS; nothing about what is
*collected* changed, and `truncate_words` is gone with its only caller.

**The 310px void is structurally impossible now, not merely fixed.** It came
from `main_bottom = max(graph_bottom, pipe_bottom)` padding the shorter of two
independently laid out columns. Column heights are a grid concern now. Work
packages also moved under the sessions rather than full-width below both, because
the pipeline column runs ~1.7× the sessions column and a two-column row is only
as short as its taller cell — that left ~600px of empty column. Balanced: 1250 /
1416.

**`tests/test_tower_render.py` is new**, and the guard that matters is not the
happy path: it fails if a `[:n]` ever reappears *inside an f-string
interpolation*, which is the exact shape every old truncation had
(`{e(w["short"][:11])}`). A plain `behind[:3]` choosing how many project names to
list is not that bug, and the first version of the check could not tell the
difference — it flagged it, which is how the distinction got drawn. Verified by
reinjecting the bug: red with it, green without.

**The no-scroll budget did not land here and was never going to.** "Fits
1280×900" was written on #50 where the 615px session grid it depends on belongs
to #52; it has moved there. The page measures **2,283px at 1280 wide**, against
2,241px at 1200 wide before — the same order, because #50 cuts nothing. What it
does is make the screen reflow (single column below 1000px, where the old page
clipped), stop lying about names, and stop reserving empty space.

No behaviour change for any adopted project: this is `bin/tower` and its tests.
## 2026-08-07 · Proposal 09: the Tower is drawing the right data the wrong way

aashish asked for a proposal on the Tower's UI — "the ui is not clean". Measured
against the live tree rather than read off the source: `tower --port 8893`, 23
worktrees across 6 projects, numbers read back out of the rendered DOM.

**Nearly every symptom has one cause.** Every `render_*` function has the shape
`(data, x0, y0, width) -> (svg, bottom_y)` and `render_page` threads `bottom`
forward to stack regions. That is a hand-rolled layout engine missing the three
things a real one gives free — text measurement, intrinsic sizing, reflow — so it
truncates, voids and overflows instead:

- The SVG renders **1200 x 2241** into a window that opens at **1280 x 900**
  (`tools/tower_window/towerwin.swift:168`). About 40% of a glanceable screen is
  visible at a time.
- **310px of empty black** down the left column, because
  `main_bottom = max(graph_bottom, pipe_bottom)` pads two independently laid out
  columns to the taller one.
- Eight hardcoded `[:n]` caps exist only because SVG `<text>` cannot wrap. `[:11]`
  produced `arm-f-filin`, `arm-b-contr`, `m0-stage2-v`; the pipeline's top row cut
  one character short of "lines".
- Of 23 session nodes exactly **two** carried state. The other 21 were identical
  grey circles at identical weight. `IN FLIGHT - 19` counted 18 `worktree - N ahead`
  git counts alongside one real mapped issue.

**The collectors are not the problem and are not touched.** Everything above line
780 of `bin/tower` — the hard part — stays exactly as it is, which is what keeps
this a two-to-three day job rather than a rewrite.

**The graph from concept 07 is retired, not deferred.** aashish decided on
2026-08-07 to compress the session grid to a strip. That is the honest reading of a
measurement this repo already had: `message_edges()` (proposal 08) found handover
edges almost never have both ends on screen, and today exactly one edge renders
across 23 nodes. A graph whose edges do not exist is a grid with extra ceremony.
Retiring his own concept was his call to make, so it was asked rather than assumed.

Cut into a dependency-ordered queue — #50 (the page becomes HTML/CSS), then #51
(needs-you band, in-flight redefinition) and #52 (session strip, de-duplication),
both blocked by #50. One queue rather than three parallel branches because all
three touch the same surface, which is the collision class the worktree rule
exists to prevent.

## 2026-08-07 · The workflow.html stamp is checkable now, not remembered

`docs/workflow.html` claimed **rules version 62** while the rules were at
**102** — forty versions of drift on a page whose own README says a drifted
bird's-eye view is worse than none, because it is trusted at a glance and read
without suspicion. `rulecheck` surfaced it while implementing proposal 08.

The first correction was wrong too: it predicted the count the PR would land at,
two PRs merged, and the stamp landed one behind again. **A stamp defined against
HEAD can never name the commit it is written in** — every correction lands one
short and needs correcting.

So the definition changed rather than the number. **The stamp names the version
at which `CLAUDE-workflow.md` last changed**, not the current HEAD count. A
commit that only touches the page leaves the target still, so the regress
disappears. It now reads 104, which is where the rules actually are.

`tests/test_workflow_stamp.py` enforces three things: the page is not older than
the rules it describes, the stamp is not from the future (one ahead is legal — a
stamp is written for a commit that does not exist yet), and `workflow.png` was
not committed before the last change to `workflow.html`. Verified by running it
against the drift first: it failed with `103 not greater than or equal to 104`
before the fix, and passes after.

## 2026-08-07 · AGENT-LOG.md is generated now, and forced delegation is not adopted

Implements proposal 08 (`docs/proposals/08-proposal-workflow-bakeoff.html`),
accepted after five workflow architectures built one frozen spec and all five
scored 22/22 while cost varied 17×.

**`AGENT-LOG.md` stops being hand-written.** The rule was "append one entry when
the task lands" via `spend log`. Ten entries were written that way in
finance-tracker and **none carried the token figure the report reads**, so
`spend report` answered 0 for every row for a week — a number that is only right
when somebody remembers to type it is not a measurement. `bin/spend report` and
the new `bin/spend agentlog [--write]` now read `~/.claude/projects/*/*.jsonl`
directly, group sessions into tasks by the worktree they ran in, and count agent
dispatches from the actual `Agent` calls. finance-tracker reports 3,004,419
output tokens across 8 tasks and 38 dispatches where it reported nothing.

**`tests/test_spend.py` is the first test in this repo** — the other half of the
lesson, since `spend` shipped without one. It fails if a report over transcripts
carrying real usage ever comes back zero. Writing it immediately found a second
defect: `_task_of` compared paths as strings, and macOS symlinks `/var` to
`/private/var`, so a session's recorded `cwd` and git's toplevel could name one
directory two ways and silently drop the task. Both sides are realpath'd now.

**`AGENT-LOG.md` moves from `merge=union` to `merge=ours`** in
`gitattributes-for-projects`. Union merge is right for an append-only record and
wrong for generated output — it would interleave two generated tables into a
file that is neither side's truth. Take ours, then regenerate.

**Forced delegation is not adopted, and removes nothing.** The six-day review
proposed a driving session holding no `Edit`/`Write`, structurally required to
delegate all code. Two arms ran it; both scored the same 22/22 as a 37-line
control at many times the cost. It was never written into these rules, so the
retraction is a record rather than a deletion. Scope: this does **not** touch
tool grants as applied to the *roles* — `quality-manager` having no write access
is untested here and stays. What failed was extending the mechanism to the
driving session.

**Also fixes the `workflow.png` recipe in `docs/README.md`.** Plain `--headless`
now resolves to Chrome's new headless mode, which ignores `--screenshot` and
never exits — it hangs until killed, writing no file and printing no error. The
documented command had silently stopped working; `--headless=old` restores it.
The crop step, previously a pointer to a changelog entry, is now written out and
was run verbatim to confirm it produces the committed image.

Behaviour change for adopted projects: **regenerate `AGENT-LOG.md`, do not edit
it.** Existing hand-written logs stay valid until regenerated; the first
regeneration replaces the prose narrative with the measured table, so anything
in there worth keeping should move to `LESSONS.md` first.

## 2026-08-06 · The bake-off finished, and it mostly says keep the rules as they are

Five arms built one frozen Swift spec — 22 EARS criteria, a fixed public API —
in isolated worktrees, scored by a sealed suite written before any arm started
and which none of them saw. **All five scored 22/22.** Cost ranged from 5.4
minutes to 122.8, and 66,816 output tokens to 209,355.

The cheapest arm was the *control*: read the spec, build it, run the tests, no
requirements document, no design document, no agent dispatch, no gate. It is
also, near enough, what "Ceremony is opt-in" already prescribes. So the headline
change here is a citation rather than a rule — the default was asserted from 30
sessions of general experience, and now has a controlled result under it.

**The pattern that failed is the one the six-day review proposed**: a driving
session holding no `Edit`/`Write`, structurally forced to delegate all code to
`code-engineer`. Two arms ran it. They cost 2.4–3.1× the tokens and 11–23× the
wall-clock of the control and returned nothing the suite could see. It is not
adopted. Note the scope carefully: this does **not** touch "tool grants, not
instructions" as applied to the *roles*, which the bake-off never tested. What
failed was extending that mechanism to the driving session.

Cost also turned out not to track process weight, which round 1 had concluded
from three arms. The heavier of the two delegating arms was the *cheaper* one,
by 47,928 tokens and 62 minutes — its up-front partition let five branches merge
with zero conflicts, while the lighter arm found its defects late and burned two
serial fix rounds. Round 1's headline is annotated as superseded rather than
rewritten.

**One rule is added, and it replaces the question-asking paragraph rather than
sitting beside it**: ask before code, in one batch, and proceed on documented
defaults. The evidence is that arms doing this did not stall — one logged six
questions, received no answers, and still finished — while the control asked two
and silently resolved nine by judgement. It got all nine right. Whether that
holds when a silent guess is *wrong* is the question no round tested, because
the suite catches wrong guesses before they can reach scoring. That is recorded
as open, and it is the only thing that would overturn any of this.

What the experiment produced that outlasts it: five isolated arms, unable to
read each other, converged on the same three defects in the spec. When several
independent readers ask the same question about a specification, the
specification is wrong — and that costs nothing to exploit.

Full numbers and the proposal are on branch `experiment/results` under
`experiments/pockets-core/`. Nothing is merged to `pockets/main`.

Also corrects a factual error in `README.md`. It claimed agent definitions
"register at session start, so a definition added or changed mid-session doesn't
take effect until a new one." **They register immediately** — measured today,
when an agent dropped into `agents/` became invokable in a running session with
no restart. The wrong sentence cost this experiment a planned restart it never
needed. What *is* fixed at session start is which directories get searched.
## 2026-08-06 · derecord says what to do next, instead of leaving a trap

Installing the union rules is not enough to make the next merge work, and the
failure looks exactly like the rules being broken.

git reads `.gitattributes` **as of the merge's starting state**. A merge that is
itself delivering `.gitattributes` therefore runs without it, so the first merge
after installing still conflicts on `CHANGELOG.md`. Hit on 2026-08-06 bringing a
long-lived branch up to date, immediately after the rules had been fixed and
installed everywhere — the obvious read was that the fix had not worked.

Measured both ways on a scratch repo: with the file riding the merge, 1 conflict
and markers left behind; with the file committed first, 0 conflicts and a clean
union keeping both sides. Same repo, same commits, only the ordering different.

`derecord` now prints the fix when it applies, and only then — if it leaves
`.gitattributes` uncommitted, it says to commit it on its own before merging and
gives the command. A repo where the file is already committed and unmodified
gets nothing, because a standing warning is just something to scroll past.

The trap is one sentence in the script's header too, since the person reading it
later is not necessarily the person who ran it.

## 2026-08-06 · derecord was breaking the merges it existed to protect

Ran `derecord` across every project, as asked, and testing it first found two
defects — one inert, one actively harmful.

**`merge.union.name` made record-file merges fail outright.** The script set it
as a cosmetic label. It is not cosmetic: defining `merge.union.*` declares a
*custom* driver named `union` that shadows git's built-in one, and a custom
driver with no `.driver` command makes git abort with `fatal: custom merge
driver union lacks command line`. So the line meant to help turned every merge
touching CHANGELOG.md into a hard failure. It was live in **finance-tracker** —
the only project that had derecord installed — so the one project with this
"protection" could not merge its own changelog. derecord now unsets it, and
repairs any repo that already carries it.

**`merge=ours` never worked at all.** Unlike `union`, `ours` is not built in and
needs a driver. Without one the attribute silently degrades to a normal merge:
demonstrated on a throwaway repo, two branches each writing
`.common-rules-version` left `<<<<<<< HEAD` in it — the exact failure these
rules exist to prevent, in the file that records which rules you are on. Fixed
with `merge.ours.driver true`.

Both were found by testing the mechanism on a scratch repo rather than trusting
that installing it had worked. The rule has been written down since 2026-08-05;
it has never actually held.

common-rules also carries `.gitattributes` now. The repo that ships derecord had
never run it on itself, which is why its CHANGELOG conflicted during an ordinary
merge earlier today.

## 2026-08-06 · The Tower shows who told what to whom

Issue #22, concept 07's step 3 and the last of the Tower feature. A HANDOVERS
region lists every cross-session message — sender, receiver, when, and the
message's opening line — and each row links to `/session/<id>`, which shows
what that session last said and what was handed to it. A handover can now be
reconstructed from the screen without opening a chat.

**They are a list, not edges on the graph, and that is a measurement.** Concept
07 drew green dashed edges between session nodes. Against the real corpus:
15 messages, every one with a worktree at the *receiving* end, and **not one
with a drawn node at both ends** — senders were either management sessions
running at the apps root (not a worktree, so no node) or sessions whose
transcript is already gone. Edges would have rendered almost never. The drawing
was right about the information and wrong about the shape.

The same measurement decided how a sender is named: **from the message tag, not
by resolving its id.** Only 6 of 15 senders still had a transcript on disk, and
the `name="..."` attribute outlives the session, so a handover stays readable
after the session that sent it no longer exists. Resolving ids would have lost
nine of fifteen — and would have gone on losing more, since transcripts are on
a delete timer.

Two bugs found by looking at real output rather than fixtures:

- The one-line summary stripped `[*_`#>]` everywhere, which ate the characters
  carrying the meaning: "issue #35" became "issue 35" and "nicegui_app" became
  "niceguiapp" — the two things a handover is most likely to be about. Only
  leading markdown markers are stripped now.
- The session panel reconstructed a cwd by replacing "-" with "/", which turned
  `idea-lab` into `idea/lab`. The flattening is lossy and cannot be inverted,
  so the path is matched against directories that actually exist and falls back
  to the raw slug rather than a confident wrong answer.

`/session/<id>` refuses anything that is not an id shape before touching the
filesystem, and reads only the transcript named by it — never a glob over the
corpus.

## 2026-08-05 · An installed Tower reads its own checkout, not whichever branch is parked

Found by installing for the first time, minutes after #27 merged. The bundle is
a wrapper: it `cd`s to a repo and runs `bin/tower` from there. Pointed at the
shared checkout, that repo was on another session's experiment branch — three
commits behind main, with no work-packages region and no `build_towerapp.sh` at
all. The app would have silently served an old screen, and would break outright
on any branch where `bin/tower` does not exist. Nothing was wrong with the
build; the design tied a Dock app to a working directory that sessions
legitimately repoint.

An installed app now gets **its own checkout**, at
`~/Library/Application Support/Tower/repo`, detached at `origin/main` and
refreshed on every `--install`. Detached rather than on the `main` branch, so it
can never collide with `main` being checked out somewhere else. Outside the repo,
so no session's worktree cleanup can remove it.

`bin/tower` skips worktrees outside the project directory, because the pinned
checkout is registered like any other worktree and was drawing itself as a
session node on the very screen it serves — visible as `repo · 1 ahead` in the
first installed run.

The "refused, you are in a worktree" guard added with #27 is gone, and its
reason with it: it existed because the installed app pointed at the build
directory. It no longer does. Building from a worktree and installing is now
safe — the bundle's compiled shim and icon come from wherever you built, and the
code it runs always comes from the pinned checkout.

## 2026-08-05 · The Tower opens from the Dock

Issue #27, his Look-3 ask: "easier for me to track and restart". The one window
he wanted always available was the most fragile thing on his screen — a browser
tab pointed at a port that only existed while some session happened to be
running it. `./build_towerapp.sh` now produces `Tower.app`.

It is a wrapper bundle, not a frozen binary, same tradeoff as
finance-tracker's `build_macapp.sh`: it launches `bin/tower` from this repo, so
the app can never serve a stale screen sealed in at build time.

**The window is Swift, not pywebview.** The precedent in `build_macapp.sh` is
pywebview, but it is not installed here and the Tower is deliberately
stdlib-Python with no dependencies (concept 07). A ~200-line AppKit + WKWebView
shim compiled from source at build time adds a window without adding a
dependency — the same compile-from-source, commit-no-binaries philosophy as
finance-tracker's `docr.swift`.

Each of the issue's guarantees lives in code rather than in a habit:

- **Clean quit** — the shim spawns `bin/tower` as its own child and kills it in
  `applicationWillTerminate`, plus on SIGINT/SIGTERM. There is no path where
  the window closes and the server survives. Measured: quit leaves 0 processes
  and releases the port.
- **Exactly one copy** — it checks `NSRunningApplication` for its own bundle id
  at startup and activates the existing window instead of starting a second
  server. Holds even against `open -n`, which is the case macOS does not
  handle for you.
- **Loopback survives the wrapper** — `bin/tower` binds 127.0.0.1
  unconditionally and takes no host flag; the shim passes only `--port`. The
  wrapper cannot widen the bind by construction, not by policy. ATS is opened
  with `NSAllowsLocalNetworking`, never `NSAllowsArbitraryLoads`.
- **A free port, asked for not guessed** — it binds :0 and reads back what the
  OS assigned, so opening the Dock app while a session runs a Tower on 8890
  does not collide. Verified: they ran side by side, untouched.
- **Its own icon** — `assets/icon-tower.svg`, a tower silhouette in the Tower
  screen's own palette. Reserved for this app, not borrowed: Sangam's gold
  confluence and this green tower are not confusable at Dock size. Rasterised
  by `sips` (macOS 26 reads SVG directly), so no PNG is committed and no
  third-party renderer is needed.

`--install` is refused from a worktree. The bundle runs `bin/tower` from the
repo it was built in, and a worktree disappears when its branch merges — which
would leave a permanently broken app in `/Applications`. Build from the main
checkout to install.

Measured end to end: quit, click, and the window is showing current data in
**2.5 seconds**. `bin/appcheck` reports 43 bundles, every identifier unique.

## 2026-08-05 · The Tower says how much of each app is done

Issue #38, proposal 08 step 1b. The sponsor accepted this step explicitly
without the rule changes that came with the rest of that proposal — so this
adds a region and changes no rule, imposes no checklist shape, and creates no
standing obligation on any other session.

It reads what the projects already write. `CLAUDE-checklist.md` was already a
work-package register — `##` headings are packages, `- [x]`/`- [ ]` is the
completion state — in four of six apps, kept current by hand and read by
nothing. Parsing it as-is gives finance-tracker 17/44 (39%, 7 packages),
pockets 5/14 (36%), pip 3/13 (23%), mac-explorer 1/8 (12%), with the package
split beneath each.

Three things this deliberately does not do:

- **An app with no checklist reports "no declared scope", never 0%.**
  common-rules and idea-lab are that case. No declared scope and none of it
  done are different statements, and the second one would be a lie.
- **A line that looks like an item but does not parse is counted and
  reported**, not dropped. A silently skipped line lowers a denominator and
  moves a bar — proposal 08's own limit about making a prose file
  load-bearing, honoured by the parser that made it load-bearing.
- **No ETA column.** That needs the logbook, which was proposed and not
  accepted; a forecast drawn through four active days is a slope through
  noise.

Also done, and independent of all of the above: `cleanupPeriodDays` is now set
in `~/.claude/settings.json`. It was unset, so the 30-day default applied and
the 31 July transcripts — the start of the whole experiment — were going to be
hard-deleted around 30 August.

## 2026-08-05 · The Tower's pipeline sees every app, not one

The user asked the Tower's own question -- "what's pending in the pipeline" --
and the honest answer was that it could not tell him. `pulse`'s `PROJECTS` was
a hardcoded two-entry list, and the second entry carried `repo: None`, so
exactly one project's issues ever reached the screen: 25 of 38 open issues
shown, 13 invisible across pockets, mac-explorer and common-rules. The four
missing from common-rules were the Tower's own open tickets -- the window on
the autopilot could not see the work being done on itself.

The live graph and the event ticker were already machine-wide, which made the
screen internally inconsistent: a session node for a worktree whose issue the
pipeline beside it did not list.

`PROJECTS` is gone. Projects are discovered from `~/apps` at collect time,
each repo slug read from that checkout's own `origin` remote, so no entry can
drift to `None` again and an eighth app needs no code change. Six projects
found, 39 open issues on screen, common-rules #22/#24/#25/#27 among them.

Three things that fell out of doing it:

- **Issue numbers are only unique within a repo.** `common #27` (launch the
  Tower from the Dock) and `finance #27` (person dossier) were both on screen
  the first time it ran. Everything downstream is keyed on `(project, number)`
  now, never the bare number -- the in-flight match, the node labels, the
  feature hulls -- and every chip carries a project tag. Same class of bug as
  issue #24, one level up: a number that means nothing without its scope.
- **Six projects serially would have overrun the 5s collect.** The per-project
  `gh` calls are independent, so they fan out across a thread pool; collection
  measures 1.2s against all six.
- **common-rules was reporting itself "never aligned"** -- it carries no
  `.common-rules-version` stamp because it *is* the rules. A false alarm the
  old two-project list never got close enough to surface. It is excluded from
  the alignment chips, and the header names at most three behind projects
  before collapsing to a count, since six names overran the line.

## 2026-08-05 · appcheck looks at LaunchServices, not just the disk

The user still saw several Sangam copies after every duplicate bundle had been
removed, while `appcheck` reported "every identifier unique". Both were true:
only one bundle existed on disk, and LaunchServices still listed six, pointing
at worktrees deleted days earlier. Removing a bundle does not unregister it, so
the entries survive in Spotlight and Launchpad -- which is where a person
actually experiences "two copies".

The tool was checking the thing that was fine and not the thing he was looking
at. It now reports GHOST registrations too, scoped to the roots being checked
so another app's leftovers (Spotify's updater cache) don't bury the real ones,
and `--clear-ghosts` unregisters them one at a time rather than forcing a full
`lsregister -kill -r` rebuild of the whole database.

## 2026-08-05 · Install from main at the end of every feature

The user's rule, and it reverses an earlier one: `build_macapp.sh --install`
was previously forbidden outright. The installed app is what he actually
opens, so a feature that is merged but not installed is a feature he cannot
see -- today's app was four days old while three PRs sat merged on main.

Installing is now the closing step of a feature: check out main, pull, run
the suite, install. Never install a red build; an old working app beats a new
broken one.

Two things fixed alongside it, both found by doing it:

- `--install` staged into `dist/` and left the copy there, so every install
  produced two bundles carrying `local.wealthtracker`. With installing now a
  standing step, that duplicate would recur every time rather than once.
  Fixed in finance-tracker (PR #52): the staged copy is removed after a
  successful install. Non-install builds keep `dist/` untouched.
- `bin/land` reported "merge blocked" on a PR that had merged seconds
  earlier. `gh pr merge --delete-branch` exits non-zero when a worktree still
  holds the branch -- the normal case, since every task runs in one -- and
  land treated that as the merge failing. It now asks the remote for the PR's
  actual state instead of trusting an exit code that conflates merging with
  cleanup. A false "not merged" is the worst kind of wrong here: it tells a
  session to retry work that is already done.

## 2026-08-05 · apprun looks, instead of only remembering

The user found two app servers running that `apprun list` could not see: the
installed copy on :8502 and a worktree copy on :8600, both launched directly by
sessions (`python3 -m nicegui_app.main`) rather than through `apprun start`.
The registry only ever knew what it was told, so `stop` and `sweep` were
structurally blind to them and reported a clean machine. A registry that is
silently incomplete is worse than none, because it reads as authoritative.

Every command now also *looks*: any process listening on a local port whose
working directory is under the apps root, and which no open entry covers, is
reported as UNREGISTERED. Having no owning session, those are orphans by
construction — visible to `sweep`, refused by `stop`, closable only with the
user's yes. A copy running from a worktree path is never classified stable,
whatever port it landed on.

Discovered entries are never written to the registry. They are observed on each
run, so they cannot go stale the way a written record can.

New: `apprun adopt --port N` claims a copy started outside apprun for the
current session, making it that session's to stop at the end of its task.
Starting a server by hand is not the problem; leaving it unclaimed is.

## 2026-08-05 · The cut — 1,637 lines to 298, and four rules turned into code

Measured 30 sessions and 29.2M output tokens before changing anything. The
findings, and what each one changed:

- **Two thirds of all spend (68.6%) went to management chats, not to worktrees
  writing code.** Ceremony is now opt-in: the research/requirements/design/
  audit/L2 chain runs only on work the user has flagged as a feature. Everything
  else goes issue → code-engineer → gate → land.
- **Every merge conflict on 2026-08-05 was in a file these rules invented**
  (CHANGELOG, AGENT-LOG, LESSONS, the checklist, the version stamp). Hand-
  resolving them is what put conflict markers into three Python files and broke
  finance-tracker's main. `bin/derecord` now union-merges them, so two branches
  appending both win and neither conflicts.
- **Branches that live for days collide.** Two branches independently created
  the same new file and independently rewrote the same renderer. `bin/land`
  merges a branch as soon as it is green, without waiting to be noticed.
- **1,637 lines went unread.** Cut to 298. What survived is what measurement
  showed was load-bearing: worktree-per-task, tool grants, the pre-merge gate,
  and tests. A rule that can be enforced now lives in `derecord` as a git
  attribute or a hook, not as a paragraph.

Also, from the same day's asks:

- **AGENT-LOG stays, and now carries cost.** `bin/spend log <task>` writes one
  entry per task with the agents invoked, the tokens spent and the commits
  landed; `bin/spend report` and `bin/spend today` total it. The user asked to
  keep it specifically to see where spend goes.
- **Verification moves to the Browser pane.** The old pre-merge step 3 said to
  build and open the `.app` — which opens a real WebKit window and leaves
  another bundle on disk. That is now reserved for packaging changes only.
- **One installed app per project.** `bin/appcheck` finds bundles sharing a
  CFBundleIdentifier; four `Sangam.app` bundles were found claiming
  `local.wealthtracker`.

New in `bin/`: `derecord`, `land`, `spend`, `appcheck`.
Deleted from the rules: the record-file ceremony, proposal numbering/
immutability/traceability, the story section, ceremony tiers as a default,
the rulecheck prose (now a SessionStart hook installed by `derecord`).

Every change to a file in this folder gets an entry here — same convention
as a project's own `CHANGELOG.md`: newest first, one or two lines, why not
just what. This folder is its own git repo (see `README.md`), but `git log`
only records that something changed; this file records what it was for, and
is the thing to read first.

## 2026-08-05

- **A finished session doesn't linger — it offers to close** (his ask). "Leave
  nothing running" covered app instances; nothing covered the sessions
  themselves, and they pile up for the same reason — the work ends, nobody says
  so, and a done session looks exactly like a thinking one. Measured across ten
  worktrees the same day: `issue-27-person-dossier` holding a finished commit,
  idle **50 hours**; `proposals-status-refactor` clean and idle **29 hours**;
  `m0-stage2-v5-decomposed` idle **51 hours**; `proposal-register` on **20
  finished commits** with no live session at all. None abandoned — all *done*,
  none of them saying so.

  So a finished session states it plainly and offers to close, as the last line
  of its final report. **Closing stays his call** (same class as clearing an
  orphan — the session judged finished may be the one he was about to reopen);
  what is mandatory is the offer. A deliberate carve-out from "a question is a
  cost", allowed because he asked and because closing is already reserved to him;
  one line at the end of finished work is not decision spam. On the way out the
  session also exits its worktree, stops what it started, and completes its
  `AGENT-LOG.md` entry. **Paused is not finished** — waiting, blocked or
  mid-review stays open, and a session still holding uncommitted work has
  mistaken "stopped" for "finished".

- **`bin/tower`: live-graph nodes show what he's tracking, not git mechanics**
  (issue #25, from aashish at Look 3: "it's showing branch names, it doesn't
  mean anything to me… I'm tracking features and what features are working,
  which requires my input. And then I can look at, okay, which issue number,
  which chat I need to go to."). Node label order inverted: primary is now
  the issue title (prefix stripped when the node sits inside that feature's
  hull, truncated ~22 chars on a word boundary), secondary is `#<number>`,
  and the worktree name — how he actually finds the chat — moves to a small
  dim third line rather than being replaced. A worktree with no mapped issue
  still shows only its own name, the same honest mapping as #24 rather than
  a guess.

  Feature hulls widened: previously required >=2 mapped nodes, which is why
  none rendered at all despite Desktop Clerk having #41 active alongside
  #32/#33 open. A single mapped node now also draws a hull, labelled
  `FEATURE · <NAME> · <n> tickets, 1 active`, when its feature has other open
  issues not currently in flight — a feature with exactly one ticket and
  nothing else open still renders hull-less, since there's nothing else on
  it to show.

  Added the marking he's actually scanning for: a node gets the purple
  accent stroke (`#A98FD6`) plus a small "needs you" tag when it's a wall
  item, or its mapped issue's branch has an open, non-draft PR (a new
  `open_gate_branches()` collector — "awaiting a merge decision" read
  literally as what an open PR already means, nothing invented beyond that).
  A legend line now sits under the graph heading: green active · grey idle ·
  amber contested · purple needs you.

  Verified on spare port 8895 against live ground truth: all ten node
  primary labels are issue titles or worktree names, zero branch-name
  strings anywhere in the page; the Desktop Clerk hull rendered as `3
  tickets, 1 active`; the one wall item (`proposals-status-refactor`) is the
  one purple-marked, "needs you"-tagged node.

- **`bin/tower`: fixed false IN FLIGHT matches** (issue #24, found by aashish
  on the live screen — #2, #5, #7, #8, #9 shown as in flight when only #27
  actually was). Root cause was matching issue numbers as bare digit
  substrings of branch names: `"stage2"` matched `#2`, `"v5"` matched `#5`,
  hex worktree-name suffixes matched the rest. Deleted that matching
  entirely; `worktree_issue()` (first `"#<digits>"` in
  `git log main..HEAD --pretty=%s`, already used by the feature hulls) is
  now the single mapping for both. A worktree genuinely ahead of main with
  no mapped issue renders as its own dim, worktree-named row in IN FLIGHT,
  never as an invented issue chip; QUEUED is open issues minus the mapped
  in-flight set.

- **Worktree-per-task applies to common-rules too — the old rule said the
  opposite and was wrong.** It read "No worktree needed for this repo… four
  markdown files and a directory of agent definitions have no build and no test
  suite to collide over. A branch is enough." The reasoning mistook *what*
  worktrees protect: not a build, a **working directory**. A branch is a label;
  the checkout is the shared thing, and `git checkout` moves it under everyone
  standing in it.

  Disproven the same day, by this session: the project manager ran
  `git checkout -b` here while a code engineer was mid-edit on another branch in
  the same checkout, silently re-attributing its uncommitted work. The engineer
  recovered — stopped, verified nothing was corrupted, stashed, switched back,
  popped, re-verified — but it recovered **by noticing**, which is not a
  mechanism, and git warned neither party. Worth recording that the session which
  wrote proposal 02 committed the exact collision proposal 02 exists to prevent,
  in the one repo it had exempted.

  The folder is also no longer "four markdown files": four executables, a docs
  tree, and routinely two or more sessions at once. `EnterWorktree` first, here
  as everywhere; read-only exploration stays exempt, because reading cannot move
  anyone's checkout.

- **`bin/tower`, step 2 of concept 07** (issue #21) — the screen itself, not
  just `pulse` behind a port. Four regions on one loopback page: a header
  (rules version, per-project alignment chips, a live "THE WALL" count), a
  live graph — one node per worktree of finance-tracker and pockets, grid
  laid out, green/grey by session freshness from transcript mtimes, amber
  when it holds an uncommitted file another worktree also holds (`whoelse`'s
  logic, one dashed note per contested pair naming one file), dashed feature
  hulls grouping nodes whose ahead-of-main commits name the same issue
  (`git log main..HEAD --pretty=%s`, first `#<digits>` match — no invented
  mapping, ungrouped stays ungrouped), a pipeline built from `gh issue list`
  grouped like `pulse`'s feature groups (in flight / queued / merged today /
  "at the wall — yours"), and an 8-row event ticker merging `git log` across
  all three repos with one event per `AGENT-LOG.md` (its last `##` heading)
  across every main checkout and worktree. Wall items are a heuristic — a
  session's newest transcript tail containing `AskUserQuestion` and stale
  over 5 minutes — and labelled as one on screen, per the concept's own
  honesty rule about what a wall item can and can't prove. `/pulse` serves
  the existing page from memory (`pulse.render(write=False)`, loaded via
  `importlib.machinery.SourceFileLoader`) — a GET writes nothing, `pulse`'s
  CLI behaviour is unchanged. Every region collects independently and
  renders an "unavailable" note in its own place on failure — no region can
  500 the page. Loopback only, same rule as `pulse --serve`: this reads
  private transcripts. Self-registers with `apprun` as a `--demo` proto copy
  when run inside an agent session (`CLAUDE_CODE_SESSION_ID` set), and
  deregisters on shutdown; a plain-terminal run says registration was
  skipped, since apprun refuses an ownerless entry by design. Message edges
  and click-through (step 3) stay out of scope, as the issue says.

  Two real bugs surfaced against live data, both fixed in the same pass that
  found them. First: `run()`'s `.strip()` (copied from `pulse`'s helper)
  strips the whole `git status --porcelain` blob rather than each line,
  eating the leading space off a `" M file"` line and truncating the
  filename by one character — `AGENT-LOG.md` rendered as `GENT-LOG.md`.
  `whoelse`'s own `git()` helper already avoids this with `rstrip("\n")`
  only; `touched_files()` here does the same instead of calling the shared
  `.strip()`-based `run()`. Second, found writing the apprun
  self-registration: the SIGTERM handler was reentrant. `apprun stop`'s
  `terminate()` sends this exact pid a redundant self-targeted SIGTERM as
  its first move, which re-entered the handler *while still blocked inside
  the first call*, spawning a second `apprun stop`, which sent a third
  SIGTERM, recursing without bound — confirmed as an unbounded nested
  subprocess spawn via a 164KB traceback that never let the registry write
  land. Fixed by ignoring SIGTERM the moment shutdown starts
  (`signal.signal(SIGTERM, SIG_IGN)` before the blocking call); apprun's own
  8s SIGTERM-then-SIGKILL timeout still ends the process deterministically,
  since SIGKILL can't be ignored — shutdown is correct but takes that long,
  an artifact of reusing `apprun stop`'s kill-and-close semantics for a
  process closing its own entry, not a defect at this call site.

- **The Tower** (concept 07, accepted same day — all three steps). His ask: "a
  live app that's feeding off of these sessions and showing me how the autopilot
  is handling things." Concept drawn with the day's real sessions: a live graph
  whose message edges are real (cross-session messages verified observable in
  transcripts), holding patterns from contested surfaces, purple edges to the
  wall with wait ages, a per-surface pipeline with an "at the wall" row that is
  exactly his to-do list, an event ticker, and the day's question count in the
  header. Local-only by rule — it reads private transcripts.

  Step 1 built the same hour: `pulse --serve` — the pulse page on a loopback
  port, re-rendered every 10s, auto-refreshing. Steps 2 (the Tower screen) and
  3 (message edges + click-through) cut as vertical issues for the autopilot.

- **A question to the user is a cost — and Autopilot** (enacts proposal 04,
  decided by instruction). aashish: sessions were all asking him whether to
  message the other issue — "this is something that's not my problem"; and:
  "these things should run automatically with minimum input from my side."

  Diagnosed by measurement, not intuition: **52 questions across five
  finance-tracker sessions** (one asked 29). Every category traced to a rule
  that mandated asking or to the absence of any rule pricing a question. The
  worst was our own: proposal 02's resolution required his yes before any
  cross-session message — written the day *before* proposal 05 made issue
  coordination the AI's job. The sessions were obeying the rules exactly.
  **No new agent needed; an agent on top of ask-mandating rules would also ask.**

  Fixes: the approval requirement on cross-session coordination is corrected in
  place (send, log in AGENT-LOG.md, tell him in the digest); a single test now
  gates every question (would the answer change what he sees at a look, or is it
  reserved — else decide, record one line, proceed); the requirements engineer's
  "ask the sponsor rather than assume" is retired for "reason it out" (it was
  the largest single source); the design engineer's route-to-sponsor now stops
  at the requirements engineer; and the quality manager counts unnecessary
  questions at the gate — three across tasks is an instructions-are-wrong
  finding, the same mechanism as recurring lessons. Proposal 04 is marked
  accepted with his words recorded as the decision; the PR carrying this is
  the correction point if that reading is wrong.

  Baseline recorded for re-measurement: 52 questions / 5 sessions on
  2026-08-05. The target is not zero — it is zero *unnecessary*.

- **The Idea Lab** (research 06, accepted same day; direction: the funnel with a
  tournament heart). aashish's ask: "I can just tell the idea. It should run
  multiple iterations to make the idea finer and finer, and then let me know" —
  a v2, kept deliberately separate from these rules. Deep research first, per
  the research-in-management-sessions rule.

  The finding that shapes the design: **an idea polishing itself gets worse, not
  finer.** Models cannot reliably detect their own mistakes without external
  signals (they can correct a flagged one — a different skill); refinement
  plateaus in 3–5 rounds; iteration anchors on the first framing; and generated
  ideas grow more similar over generations, not more diverse. So the design
  question is where the external signal enters each round. Surveyed: critic
  loops (the floor), persona panels (diversity bounded by who is in the room),
  Google's Co-Scientist tournament (pairwise Elo + evolution, Nature-validated —
  the strongest published pattern), and Sakana's AI Scientist as the cautionary
  tale (42% failure rate, novelty checks fooled by keyword search).

  Accepted shape: expand the idea into 8–12 genuinely different interpretations;
  ground each with real fetched-and-read research (the one unskippable stage);
  select pairwise, keeping an archive of interesting losers; evolve winners
  until two rounds change nothing; then one document back — the refined idea,
  its two strongest rivals, and what was killed and why.

  Built the same day as `../idea-lab/` — its own folder and repo, LAB-RULES.md
  as the whole rulebook, no remote yet. One touchpoint with v1: the Lab's
  output is proposal-shaped and enters at L1. It replaces the blank page, not
  the pipeline. First trial waits for a real idea, which is his to bring.

- **The user owns features; the AI owns issues** (proposal 05, accepted same
  day). aashish: "at the end of the day I am worried about the feature, not the
  issue — issues are there to have parallel task, divide and conquer. It's not to
  increase my overhead that I have to trigger each and every issue." He also
  reported refereeing race conditions between finance-tracker's #30 and #31.

  Researched rather than assumed, and the finding is that **the collision was
  created at decomposition time, months before either session started.** #30 is
  "Desktop Clerk: Ask **backend**" and #31 is "Desktop Clerk: Ticket Rail + seam
  + Ask **dock layout**" — the server side and the screen side of one capability,
  labelled `backend` and `ui`. Four of the 25 open issues are one feature, cut
  backend/ui/backend/ui. That is **horizontal slicing**, and the literature is
  unambiguous about it: such slices "can't deliver value without interaction or
  integration with other layers" and make dependency management intricate by
  construction. Vertical slices — end to end, screen through to store — stay
  independent and testable.

  The overhead is also arithmetic, not temperament: coordination paths grow as
  **n(n−1)/2**, so six issues in flight is fifteen possible collisions, and he
  was the only node that could see all six. Every one resolved through him. The
  counter-intuitive half is that limiting work in progress *raises* throughput.

  So: **this narrows the whole 2026-08-02 issue-lifecycle section from issues to
  features** — a deliberate reversal, flagged rather than slipped in. Creating,
  sequencing, handing off and closing issues moves to the AI; proposing,
  approving, seeing and closing *features* stays his. Issues are cut vertically,
  one in flight per surface, with dependencies recorded at decomposition rather
  than discovered on collision.

  **He asked whether this needs a ninth agent. It doesn't** — decomposition and
  sequencing are already the project manager's job by definition; it had no
  authority because the rules gave every issue decision to him. Adding an agent
  to do work the project manager is defined to do but forbidden from doing would
  treat the symptom. What is genuinely missing is a *view*: nothing shows a
  feature and its issues together, which is why #30 and #31 were invisible.

  Also, separately: **stop labelling rules with codes.** "if you're telling me
  this d one, d two, some jargons need to be figured out, I cannot figure them
  out." Proposal 05 is written entirely as sentences; codes belong in the files,
  not in what reaches him.

## 2026-08-04

- **Loops, research triggers, and where parallel is safe** (proposal 03, accepted
  same day). aashish asked what loops back, when research fires, and where
  parallel work is possible. Reading the rules for *return* paths rather than
  forward ones found the workflow documented as almost one-directional: **three
  loops stated here, four buried in agent definitions the project manager never
  reads, six that should exist and didn't.**

  The worst: **every failure routed to the code engineer.** "This approach is
  wrong" and "this line is wrong" were procedurally identical, both landing with
  the person whose job is to make the code pass — which is how a wrong approach
  gets patched until it passes. The gate now names its destination (`code`,
  `design`, `research`), recommends rather than authorises, and every loop is
  bounded at two returns.

  **Research had no trigger at all** — "optional and run only when the task needs
  them", with the tier and the agent each citing the other. Four checkable
  triggers now. But the real finding is structural: **a task session is created
  *from* an accepted proposal**, so by the time one exists the direction is
  already chosen and the only honest thing left is writing down what was decided.
  That is why requirements work is visible and research isn't. Measured:
  management sessions had made **three specialist agent calls in their entire
  history, against thirty in task sessions**. Research now belongs to the
  management session, before a proposal exists.

  **Parallelism needed no new principle** — the tool grants already answered it.
  Read-only roles fan out freely; writing roles run one per *artifact*, not per
  task; sequence is set by dependency, not ceremony.

  Stepping back on aashish's review added the class that the first pass missed
  entirely: **learning loops**, which correct the system rather than the work.
  A recurring lesson escalates on the third occurrence (the quality manager
  counts, it cannot fix — agent definitions are his); promotion is a return to
  requirements, not a checklist; the outermost loop from shipped software to a
  finding is drawn at last; and — found by checking pockets, whose register held
  **3 accepted, 11 proposed, 0 built** — an accepted proposal that was never
  built now resurfaces, because `accepted` looks like *done* and means *owed*.

  Thirteen loops are drawn in `docs/workflow.html`, coloured by class, with a key.
  The page no longer shows a straight line, which was a picture of a workflow
  nobody has.

- **Working alongside other sessions** (proposal 02, accepted same day) — plus
  `bin/whoelse`. aashish asked how to stop parallel sessions reaching different
  conclusions and conflicting later. Measuring finance-tracker before answering
  changed the answer: **43 uncommitted files across seven parallel worktrees,
  none of them ahead of `main`**, and **seven files held by more than one
  session** — `nicegui_app/pages/ledger.py` by four. Four different uncommitted
  rewrites of one screen. The collision is already built; it just hasn't landed.

  Nobody did anything wrong. The worktree rule worked exactly as designed and
  stopped them overwriting each other live — **it was never designed to stop them
  diverging**, and no step anywhere asked *who else is working here*.

  Six rules. Look before you start; **overlap is a stop, not a warning** (a file
  another session holds is not yours to edit, same principle as a port you didn't
  start); inform the owning session rather than duplicating it; **commit or it
  doesn't exist**; parallelism granted **per surface, not per issue** — four
  issues touching `ledger.py` were never four parallel tasks, they were one queue
  nobody drew; and R6, added when aashish reviewed the draft and caught that
  *informing is not handover*: a finding landing on another task's surface gets
  responsibility assigned explicitly — finder keeps it, owner takes it, or
  neither — recorded against both issues. That closes silent absorption and
  mutual drop, which were both wide open.

  `bin/whoelse` reads the three places that already knew and nobody consulted:
  `git worktree list`, a `git status` in each, and whether any of it is ahead of
  `main`. Three of the four capabilities this needed already existed — listing
  sessions, messaging a session, per-worktree status — and had never been run.
  The gap was a step in the workflow that says *look*.

  Four open questions were not answered separately, so the document's stated
  positions were applied and recorded in it: overlap **blocks**; the handover
  message is **drafted for him to approve**, since it arrives in his name
  elsewhere; R5 compares surfaces **per batch**, before sessions are opened; and
  **he assigns** an R6 handover, since it is a scope change and those escalate.

  The 43 files were left untouched on his instruction. `whoelse --contested` now
  reports that state on demand rather than requiring someone to go looking.

- **`docs/workflow.html` — the whole workflow on one page, and a rule that keeps
  it true.** aashish asked for a bird's-eye view. `CLAUDE-workflow.md` is now
  long and reads in the order it was *written*, not the order work *happens* —
  which is fine as an authority and useless as a map. The page walks idea →
  merged in actual sequence, colour-coded by who acts (you / project manager /
  gate), then: who decides what, the eight agents with their real tool grants,
  the ceremony tiers, the run-identity ports, where every record gets written and
  by whom, and the two tools' commands. A full-page PNG sits beside it, per the
  existing report rule.

  The maintenance half is the part that matters, and it is now a rule rather than
  an intention: **the page is derived from `CLAUDE-workflow.md`** — where they
  disagree that file wins — and **any PR that changes the shared rules updates
  this page and its version stamp in the same PR.** Not as a follow-up. A
  bird's-eye view that has quietly drifted is worse than none, because it is
  trusted at a glance and read without suspicion; a stale map is the version that
  gets believed.

  Every tool-grant row was checked against the agent files' frontmatter rather
  than written from memory. PNG: headless Chrome at 2× into a 20000px-tall
  window, then a PIL crop that scans upward for the last row differing from the
  page background — the window height is a ceiling, not a measurement, so
  cropping is what makes it a page rather than a page plus a mile of empty.

- **How a proposal is delivered — artifact, then buttons** (proposal 01,
  accepted same day; `docs/proposals/` starts here). aashish's report: in pockets
  he had to ask for the rendered view and the decision buttons **every single
  time**; in finance-tracker he never did. Checking the two explained it, and it
  wasn't care or effort — finance-tracker has `docs/proposals/`, 13 numbered
  committed HTML files with statuses and an index. **Pockets has none.** Its
  three key proposals are `claude.ai` artifact URLs pasted into `CLAUDE.md`, and
  **two of the three have no local copy at all** — so the app's entire product
  direction depends on links that can rot, and the repo would not notice. With no
  convention, delivery had to be negotiated each time, and being the convention
  himself is what made it feel like work.

  Four rules now: a proposal is a rendered HTML artifact, never chat prose; the
  **committed copy exists before the artifact is shown** (the artifact is the
  view, the repo is the record — rule 1 without this just makes prettier things
  that still vanish); delivery is followed immediately by a decision prompt with
  buttons; and one decision per prompt, since a bundled question gets a bundled
  answer. A default button set is fixed — Accept / Amend / Reject / Show me
  first — so the options aren't reinvented vague each time.

  Two of his three answers refined or overrode the recommendation. **Buttons
  appear even when there is nothing to decide yet**, option "noted" if need be —
  and his reasoning is better than mine was: an absent prompt is ambiguous, and
  he should never have to work out whether he is being asked something.
  **Reports, findings and gate results get the artifact but not the prompt** —
  that restraint is what keeps buttons meaningful rather than something to click
  past. And **pockets backfills all three** existing proposals rather than
  applying the convention only to new work, which is the only thing that protects
  what is already there. That backfill is pockets' work, raised as a draft issue,
  not done from here.

- **Cleanup is now scoped by ownership**, in `CLAUDE-workflow.md`'s "Leave
  nothing running" section (retitled "— and stop only what you started").
  Two halves. The first restates the existing rule at **session** scope rather
  than per-agent: agents within a task can share a running copy, but the task
  does not end with it still up, and the project manager is accountable for
  that. The second is the new half and the reason aashish asked: **an agent
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

- **`bin/rulecheck` — a session checks it is on the current rules before doing
  anything.** aashish's ask, and the reason is in the ask: he kept having to say
  "check common rules" again. These rules changed **five times today alone**, so
  a session working from what it read earlier is following a version that no
  longer exists, and nothing told it so.

  The version is `<commit-count>-<short-sha>` — the count orders it, the sha
  identifies it exactly. A project records the one it last aligned with in
  `.common-rules-version` at its root, **committed**, so a worktree checkout
  carries it automatically and needs no stamp of its own. Exit 0 aligned, 1
  behind, 2 cannot tell — and "cannot tell" means re-read in full, not "probably
  fine".

  The part that makes it worth running rather than just informative: it prints
  **what changed**, by diffing `CHANGELOG.md` between the two commits, not merely
  that something did. A session then reads the sections those touch. `--align`
  is deliberately a separate act after reading — it is a claim that this session
  knows the current rules, and a false claim there is worse than no stamp, since
  the next session inherits it and skips the check.

  Documented with a `SessionStart` hook per project (`rulecheck --quiet`),
  because the rule as written still relies on a session remembering — which is
  the exact weakness it exists to remove. Adding that hook is per-project work
  and hasn't been done. Neither project has ever recorded a version, so both read
  as never-aligned until they do.

- **`proposal-auditor`, an eighth agent — so L2 isn't the project manager's own
  opinion.** aashish's question, and it went straight at the weakness flagged in
  the L2 rule below: the project manager would be approving output from a
  pipeline it commissioned itself. So the comparison is done by someone else.

  The auditor reads the accepted proposal, `REQUIREMENTS.md` and the design spec,
  and classifies **every** divergence: `faithful`, `elaboration` (detail the
  proposal implied — what this work is *for*, and L2's to approve), `drift`
  (something the proposal decided, now changed — the sponsor's), `silent
  decision` (a decision the proposal never made — also the sponsor's), and `gap`
  (a proposal decision the requirements don't cover — back to requirements, and
  not ready for L2 at all). Two of those map onto two of the four escalation
  triggers below, which turns L2 from a judgment call into something acted on
  evidence.

  **Deliberately not the quality manager**, which was the tempting answer. That
  agent would approve the criteria at L2 and then gate the built work against
  those same criteria — marking its own homework where independence matters most.
  The principle already written for agent definitions carries over: an agent that
  approved the specs it reviews against is no longer an independent check. The
  two questions also differ in kind — the gate runs the thing and checks the
  outcome; this compares two documents against a third and judges fidelity of
  intent.

  Read-only (`Read`, `Grep`, `Glob` — no `Bash`, no `Write`), decides nothing,
  approves nothing. Its definition names the three quiet ways it fails:
  summarising instead of quoting both sides, looking only at what was *added*
  rather than what was silently dropped, and inventing a reading where the
  proposal was ambiguous — when the ambiguity is itself the finding.

  Costs, stated: an eighth agent against this file's own warning that
  full-ceremony pipelines can reduce correctness — mitigated by scoping it to
  post-acceptance work only, so a small fix pays nothing. And it cannot catch a
  proposal that was vague to begin with; it can only report that it was.

- **After acceptance: requirements, then design, then L2 — never straight to
  code.** aashish's rule, and it **corrects the paragraph merged a few hours
  earlier** which said a complete brief meant the upstream roles could be skipped
  and the tier was small-fix. Wrong, and the correction is stated in place rather
  than quietly edited: **an accepted proposal is not settled requirements.** It
  is a decision about direction, argued in prose — the input to requirements
  work, not a replacement for it.

  So acceptance now starts a fixed sequence: `requirements-engineer` →
  `design-engineer` → **L2** → code, test, gate. **L1 is aashish accepting the
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
  aashish intervened; the session replied *"You're right, I broke the rule that
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
  aashish asked why finance-tracker's issue sessions weren't using the agents.
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
  second one this investigation produced: `~/.claude/projects/` directories start
  with `-`, so a glob'd `grep` reads them as flags, finds nothing, and does not
  error — it briefly produced a confident and completely wrong conclusion about
  which sessions had read this file.

  **Not fixed here, because it isn't this repo's file**: finance-tracker's own
  `CLAUDE.md` says "aashish is project manager here, **the AI is the developer**"
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
  yet, and its job is to put aashish in front of the real screen so he decides
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

- **`bin/apprun`, a run registry — and the reason it exists.** aashish reported
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
  with aashish's explicit yes, because one of those windows may be the one he is
  looking at. `stop` declines a live stranger's copy, an orphan, and the stable
  copy, each with the reason.

  Judgment call worth flagging: this is the first executable in a folder that has
  only ever held rules. Written because "each agent hand-rolls the bookkeeping"
  is precisely how the drift returns — but it is a widening of what this repo is,
  and reversible if aashish would rather it lived in a project.

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
