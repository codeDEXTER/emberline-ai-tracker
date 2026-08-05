# ASKS.md — what aashish has asked for, and the patterns in it

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

## 2026-08-05 · Tell an idea, let iterations refine it, then come back — a v2, kept separate
Said in: common-rules

"I can just tell the idea. It should run multiple iterations to make the idea
finer and finer, and then let me know." Explicitly a separate system from the
current rules for now. Asked for deep research on architectures first. Became
research proposal 06.

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
