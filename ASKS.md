# ASKS.md — what the-sponsor has asked for, and the patterns in it

Append-only, one entry per instruction, newest last. See `CLAUDE-workflow.md`,
"Notice the repeats". Log instructions about **how work is done**, not what to
build. Log corrections too, especially reversals. Never infer — record what he
said, not what he'd probably want.

```markdown
## YYYY-MM-DD · One line stating the ask
Said in: <project or topic>

What he said, and what it constrains. Concrete enough to recognise the next
instance of the same thing.
```

Entries below were backfilled on 2026-08-04 from `CHANGELOG.md` and the
common-rules session, which is why the early ones are summaries rather than
quotes. Anything logged from here on is written when it is said.

---

## 2026-08-02 · No direct-to-main, and no two chats sharing a working directory
Said in: finance-tracker

Became the worktree-per-task rule. The trigger was two sessions colliding over
one checkout, not a preference for git ceremony.

## 2026-08-02 · Changing the shared rules is reserved for him
Said in: common-rules

Not just issues — the rules file itself. The AI surfaces and asks; it does not
edit on its own initiative, however small the fix.

## 2026-08-03 · Mockups early, so he can think visually
Said in: common-rules (agent org)

"For my design thinking, it is very important I get mock ups early on in the
project, so I can visually think." Drove the split of design into an explorer
and an engineer.

## 2026-08-03 · Every new finding or open topic needs to be a good issue
Said in: common-rules

Findings must not evaporate at session end. Became the five-field issue draft.

## 2026-08-03 · A diagnostic log of which agents ran, in what sequence
Said in: common-rules

"just for me to look at and analyze it later." Later extended to per-agent
tokens and duration, and to naming the project in every entry. He wants to be
able to reconstruct a run without having been in it.

## 2026-08-03 · A visual indication of which running copy is which
Said in: common-rules

"there are multiple windows open of the software, and I don't know which one I
need to look at." Became the badge/port scheme and the one-stable-copy rule.

## 2026-08-03 · At the end of a test, close all app instances
Said in: common-rules

Became "Leave nothing running".

## 2026-08-03 · One proposal per topic, however many agents run
Said in: common-rules

A correction, twice sharpened: first "one per task, not one per role", then
"one for any number of agents that may run for a topic" after the first wording
left a per-session loophole. He does not want to approve the same work in
stages.

## 2026-08-03 · Also create an image of the doc page, for easy sharing
Said in: common-rules (docs)

A written report was not the deliverable he wanted on its own.

## 2026-08-03 · Let him approve a PR from the chat, without opening git
Said in: common-rules

"additional to pr give me an option to locally approve the pr here so i dont
have to look at git if it dont want to."

## 2026-08-04 · Close the app instances a session opened, but not another session's
Said in: common-rules

The ask that exposed the cleanup rule's missing half.

## 2026-08-04 · He was still seeing a lot of windows; there must always be a clean copy
Said in: common-rules

A correction of the fix given an hour earlier — the rule was right and had not
solved his actual problem, because the windows outlive the servers.

## 2026-08-04 · A reserved icon for the final app; the current one doesn't sit well
Said in: common-rules / finance-tracker

Badges and titles only help once a window is open and being read.

## 2026-08-04 · Offer a demo, with navigation, before asking for approval
Said in: common-rules

"so user gets an ideas before approval." Approving from a paragraph of text
means deciding about a screen he has not looked at.

## 2026-08-04 · Track what he asks for; propose a rule when it forms a pattern
Said in: common-rules

The ask that created this file.

## 2026-08-04 · After a proposal is approved, requirements then design, then an L2 approval
Said in: common-rules

"this should not be skipped as the code agent will not properly expand req and
design." Pointed at issue #31 as the reference case. A correction of a rule
merged hours earlier that had allowed the upstream roles to be skipped when a
brief looked complete.

## 2026-08-04 · Check the rules version automatically, so he doesn't have to say it
Said in: common-rules

"so I don't have to tell it again to check common rules." Note the shape of the
ask: not "follow the rules" but "stop making me be the mechanism".

## 2026-08-04 · Show the proposal as an HTML artifact, then ask with buttons
Said in: pockets → common-rules

"in pocket management, I was having a really bad experience where I had to tell
it every time." Named finance-tracker as the project that does this well. Third
clear instance of the show-don't-describe pattern below, and the first where he
named the *cost* of its absence.

## 2026-08-04 · Parallel sessions must see each other, not just avoid each other
Said in: common-rules

"different AIs come to different conclusions, and then there are conflict later
on… maybe have an idea about what other issues are working on and inform them
instead of working on it themselves." Became proposal 02.

## 2026-08-04 · A finding on another task's surface needs a handover of responsibility
Said in: common-rules

Caught reviewing proposal 02's draft: "there should be a handover of
responsibility by the original issue or the other issue. is this handled" — it
wasn't. Informing is not handover. Became R6.

## 2026-08-04 · What loops back, when research fires, and where parallel is safe
Said in: common-rules

Then, on review: "what about the missing one, take a step back and think about
it. also additionally give me a full diagram." The step back found the class the
first pass had missed entirely — loops that improve the system rather than the
work. Second time in one day that his review caught a whole category, not a
detail.

## 2026-08-04 · Check whether the workflow actually fixes the pockets problems
Said in: pockets → common-rules

Asked for the rules to be tested against a real chat rather than accepted on
their own terms. Two of four issues fixed, one on paper only, one not at all —
which became the unbuilt-proposal rule.

## 2026-08-04 · Don't label rules with codes he has to decode
Said in: common-rules

"if you're telling me this d one, d two, some jargons need to be figured out, I
cannot figure them out." Feedback on how proposals are written, not on their
content. Rules are sentences he can read once and act on; codes are for the
files, not for him.

## 2026-08-04 · He owns features; issues exist for parallelism, not for his attention
Said in: finance-tracker → common-rules

"at the end of the day I am worried about the feature, not the issue… issues are
there to have parallel task, divide and conquer. It's not to increase my overhead
that I have to trigger each and every issue." Became proposal 05.

## 2026-08-05 · Cross-issue coordination is not his problem; sessions must stop asking him
Said in: finance-tracker → common-rules

"All of them are asking me whether to communicate this to the other issue or
not. But this is something that's not my problem." Diagnosis found our own rule
mandated the asking. Fourth entry in the stop-making-me-the-mechanism pattern.

## 2026-08-05 · Autopilot: one chat runs the sessions, he dips in by interest only
Said in: common-rules

"It's creating all these sessions for all issues automatically and just telling
me how the progress is going… these things should run automatically with
minimum input from my side." The end state, stated plainly. Also: "a more
scientific approach where you are taking more responsibility" — measure first,
then fix, then re-measure.

## 2026-08-05 · Tell an idea, let iterations refine it, then come back — a v2, kept separate
Said in: common-rules

"I can just tell the idea. It should run multiple iterations to make the idea
finer and finer, and then let me know." Explicitly a separate system from the
current rules for now. Asked for deep research on architectures first. Became
research proposal 06.

## 2026-08-05 · Keep looking for ideas — don't wait to be handed one
Said in: common-rules / idea-lab

Said right after the Lab's first run produced Pip. The Lab's intake model was
"he supplies an idea"; this makes scouting a standing job — the Lab (and
management sessions generally) should hunt for idea seeds proactively and keep
a shelf he can pick from.

## 2026-08-05 · A live app showing sessions, their communication, blocks, and the pipeline
Said in: common-rules

"a live app that's feeding off of these sessions and showing me how the
autopilot is handling things." Fifth entry in the state-visible-at-a-glance
pattern — and the first asking for *live* rather than on-demand. Became
concept 07, the Tower.

## 2026-08-05 · A finished session should ask to be closed
Said in: common-rules

"once the session is done. It should ask me to close the session." The session
analogue of leave-nothing-running — and an explicit exception he asked for to
the question-is-a-cost rule.

## 2026-08-05 · Show the work, not the address — features and issue names, not branches
Said in: common-rules (Tower)

"it's showing branch names, it doesn't mean anything to me… I'm tracking
features and what features are working, which requires my input. And then I can
look at, okay, which issue number, which chat I need to go to." Became issue #25.
Sixth entry in the show-the-state pattern, and the sharpest statement yet of the
hierarchy he works in: feature → needs-input → issue → chat.

## 2026-08-05 · Commercial analysis belongs inside idea generation
Said in: pip / idea-lab

"Can we do some commercial analysis as part of this idea generation? What is
commercially more relevant? What do people like?" The Lab's Ground stage checks
precedent, competitors and feasibility — never market size or willingness to
pay. He wants the commercial lens applied while ideas are still cheap, not
after.

## 2026-08-05 · He keeps the clash check himself
Said in: pip / idea-lab

"I'll still check if it's clashing with some existing ideas." A division of
labour, not a correction: the Lab reports what exists (fetched and read, per
its own rule — never novelty-from-search), and *he* judges whether a new idea
sits too close to something already out there. Agents supply the evidence; the
resemblance call is taste and stays his.

## 2026-08-06 · Formal, descriptive issues for every planned task, maintained with the work
Said in: pip

"i would like you to document formal and discriptive issues for all the
planned task… issues need to be maintaind along with the trasks." Pip had a
checklist file but zero issues on its repo; every planned task got one
(#2–#15), and the checklist became an index that points at them. The second
sentence is the durable part: an issue is updated in the same breath as the
task that moves — not batched later. Note the overlap with proposal 05's
"issues exist for parallelism": these issues are for *record and handover*,
which is a second job he wants them doing.

---

# Patterns

A pattern is proposable when it can be stated in one sentence and pointed at two
or more distinct entries. Anything less is logged and left alone.

## Identified 2026-08-04 · He wants the state of things visible at a glance, without asking

**One sentence:** whatever the system knows about its own state, he wants
readable on sight rather than reconstructable on request.

Covers: the diagnostic log (2026-08-03), badges on running copies (08-03), one
stable copy (08-03), closing instances (08-03 and 08-04), a clean copy always
available (08-04), a reserved icon (08-04), and approving a PR without opening
git (08-03). Seven entries, two days, four different surfaces.

**Status:** each was ruled individually as it came up. The general form has
never been written down, which is why each new surface needed its own ask.
Worth proposing as an amendment rather than a new section — probably to
"Telling running copies apart", generalised past running copies.

## Identified 2026-08-04 · Show him the thing; don't describe the thing

**One sentence:** when there is something to look at, he wants to look at it
before deciding, not read a summary of it.

Covers: mockups early (2026-08-03), an image of the doc page (08-03), a demo
before issue approval (08-04), and the surviving half of the deprecated PR #6
rule ("relaying means showing, not summarising").

**Status:** partly ruled, in three places that don't reference each other. The
honest read is one rule that keeps being rediscovered in a new context, which
by the guidance above makes it an amendment candidate rather than a fourth
independent statement of it.

## 2026-08-07 · If there is a bug, create an issue, but continue
Said in: mac-explorer (phase 1 build)

"and in parallel continue the implementation if there is a bug, create an
issue, but continue." Bugs found during a build must not stall the pipeline:
each becomes a formal issue at once (per the 2026-08-06 issues ask) and the
implementation keeps moving. Said while phase 1 was mid-build, the same day
issue #5's bug rounds had consumed most of a working day — read against that
backdrop. Note what it does not say: it does not say broken work should land;
it says finding a bug is not a reason to stop building.

## 2026-08-07 · The Simulator window goes on the Mac's built-in screen
Said in: pip (M1)

"please open iphone simulator on macs screen only, i have a multi screen
setup." A machine-level placement rule, not a one-off: when a session opens
Simulator.app for him to watch, the window goes on the built-in display
(currently origin (1920,0), 1728×1117 — verify via CGDisplayBounds, don't
hard-code), not whichever external Chrome/Tower lives on. Backdrop: the same
day, a gate's cliclick tap aimed at a remembered Simulator position landed in
his live Tower window after Stage Manager swapped it — window placement on
this machine is load-bearing, not cosmetic. Ninth entry in the
state-visible-at-a-glance family: he shouldn't have to hunt across three
screens for the thing he was asked to look at.

## 2026-08-07 · Use the in-app simulator panel, not Simulator.app
Said in: pip (M1)

"use the inbuilt sim" — minutes after asking for Simulator.app on the built-in
screen. A reversal that supersedes the placement rule when the panel works:
the built-in simulator panel (`attach`) is the preferred viewing surface, and
Simulator.app-on-the-Mac-screen is the fallback for when the panel's tooling
errors (it did all day yesterday; it works today). Two cautions learned on
first use: the panel attaches to whatever is booted, and `screenshot` without
an explicit udid can target a different booted device than the panel shows —
always pass the udid. Another session's booted device (Pockets' Pro Max here)
is its surface; attach Pip to its own device rather than borrowing.

## 2026-08-07 · Screen work goes on "LG HDR 4K (2)"
Said in: mac-explorer (phase 1 validation)

Asked which of his three displays was ours to use, he answered "use LG HDR 4K
(2)". That display is the agent surface: take screenshots there, put any app
window we launch there, stay off "LG HDR 4K (1)" and the built-in Retina
display. `switch_display` accepts the name verbatim.

Why it matters beyond tidiness: he runs ~16 Spaces across three displays with
live work open, and a gate the same day logged a Stage Manager gotcha where a
click aimed at remembered window bounds plausibly landed in his live Tower
window. Partitioning the machine removes that whole class of accident.

Capturing by window id (`screencapture -l <id>`) is still preferred where it
works — it sidesteps both the display and the Space question. Note we can only
ever see the *currently active* Space on a display and cannot switch Spaces.
