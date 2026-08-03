# Snapshot — 2026-08-03

**The first real task through the agent team.**

A point-in-time record. Numbers are as measured, not estimated.

---

## Where things stood

- **Projects:** finance-tracker and pockets follow the shared rules; four others
  don't yet.
- **Team:** seven agent definitions, one day old, never used on a real task
  before today.
- **Rules:** worktree per task, mandatory pre-merge checklist, the user alone
  creates and closes issues and approves merges.

## The task

Make the app show which running copy you're looking at. Several copies end up
open at once — the real one plus builds an agent made — and nothing on screen
said which was which. Also stop a test build installing itself over the real app.

Nine requirements, agreed before work started.

## What it cost

| Pass | Who | Result | Tokens | Tools | Time |
|---|---|---|---:|---:|---:|
| 1 | builder | claimed all 8 requirements pass | 194k | 115 | 18m |
| 2 | tester | 3 bugs — 1 critical | 116k | 56 | 11m |
| 3 | builder | 4 fixed, 1 disputed with reason | 173k | 99 | 17m |
| 4 | inspector | blocked — 2 problems | 111k | 52 | 12m |
| 5 | builder | both cleared | 74k | 22 | 2m |
| 6 | builder | naming consistency (light tier) | 93k | 55 | 6m |
| 7 | inspector | passed, found 1 more defect | 94k | 35 | 10m |
| 8 | builder | fixed it properly | 102k | 35 | 5m |
| | | **total** | **957k** | **469** | **81m** |

For scale: the research pass that designed the team cost **3.15M tokens** —
about six times the entire build.

The 81 minutes ran in the background. Actual time blocked: none.

## What was caught that a single session would have shipped

**A command-injection hole.** The run label was written unquoted into the
generated app launcher, which the shell re-evaluates on every launch. A label of
`$(...)` executed. Reachable through an ordinary git branch name containing an
apostrophe — no malice needed.

The builder had reported all eight requirements passing and believed it.

**A silent disagreement between two implementations of one rule.** The build
script and the app resolved a setting differently for a value containing a
newline — one said "test mode", the other said "stable". It fed the guard that
stops a test build installing over the real app.

The first fix for it was wrong in an instructive way: deleting the duplicate and
calling one shared implementation was claimed to make disagreement *impossible
by construction*. The inspector proved otherwise — the way it was invoked let a
different copy of that code be substituted. **Merging would have activated it.**

## What went wrong that was management's fault

1. **Nobody committed their work.** An entire verification pass ran against files
   that existed only in a working folder, verifying something that wasn't really
   there. No instruction had said to commit.
2. **One requirement was written wrongly** — it specified behaviour the
   implementation deliberately did the other way, and the more sensible way. The
   inspector surfaced the contradiction instead of quietly picking a side.
3. **A cost figure was recorded from memory** rather than when the agent
   reported, which is exactly what the rule warns against.

Two of four failures were in the instructions, not the work. Worth saying plainly
in any presentation: the workers were not the weak link.

## Interruptions that were nothing to do with the team

- **Another session moved `main` mid-task**, so the branch had to merge before it
  could land. The rule requiring merge-from-main existed for this reason and
  earned itself.
- **An Xcode update reset a licence agreement and broke `git` machine-wide.** Work
  continued via a different toolchain already on the machine.

Both are ordinary working conditions, not exotic. Worth including — a
presentation where nothing mundane goes wrong isn't believable.

## Corrections made to the team as a result

Written from evidence, same day:

- Builders must commit before reporting.
- Any value reaching generated code is untrusted — branch names included.
- Inspectors check the cheap things first; a whole pass was wasted not doing so.
- A re-check is required only when behaviour changed.

## Honest read

The separation of duties caught something real and expensive on its first
outing. That is one data point, not proof. The costs are real and measurable, and
about a fifth of this task's cost was avoidable overhead from poor instructions.

The right conclusion today is "promising, keep measuring" — not "adopt
everywhere."
