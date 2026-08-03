# The story so far

How working with Claude Code on these projects actually went — written as it
happened, for a presentation to fellow managers later.

**The through-line:** it started as one chat window doing everything, became a
team of specialists with separation of duties, and is now being measured and
trimmed. The interesting parts are where it went wrong, not where it went right.

Snapshots with the raw numbers live in `snapshots/`. This file is the narrative
that ties them together.

---

## Chapter 1 — One chat, doing everything

**Roughly to 2026-08-02.**

A single session planned, wrote, tested and signed off its own work. It worked
well enough to build real things — a finance tracker with 400+ tests, a photo
vault, a menubar app.

Two problems showed up on their own, neither anticipated:

- **Two sessions editing the same folder overwrote each other.** The fix was one
  git worktree per chat, so each has a private copy and a private branch.
- **`main` breaking meant the installed app broke**, not just a red CI light. So
  a pre-merge checklist became mandatory: merge from main, tests pass, actually
  build and run it, write a changelog entry.

**The lesson worth presenting:** the rules weren't designed up front. They were
scar tissue. Every one of them exists because something went wrong first.

## Chapter 2 — Rules that outgrew one project

**2026-08-02.**

The same rules were being copy-pasted into each project's instructions file. A
change meant hunting down every copy. So they moved to one shared folder that
sits outside every project, with each project pointing at it.

A rule was added that the AI must never edit that folder on its own initiative —
because a change there silently changes behaviour in every project at once.

**The lesson:** shared rules need a higher bar for change than local ones, in
exact proportion to how many things they touch.

## Chapter 3 — Reading the evidence before building

**2026-08-03.**

Before building an agent team, the published research got read properly — a
multi-agent research pass over academic papers and practitioner write-ups
(MetaGPT, ChatDev, AutoGen, and a peer-reviewed failure taxonomy built from
1,600+ real multi-agent traces).

It cost **3.15M tokens across 106 agents in 20 minutes** and changed the design
in ways intuition would not have:

- A separate reviewer measurably catches what a self-certifying implementer
  misses — and helps *more* when the implementer is a weaker model.
- **Verification is the weakest link in every system studied.** Most verifier
  agents check that code compiles, not that it does what was asked.
- **Full ceremony pipelines reduced correctness for most models tested.** More
  process is not better process. Light ceremony became the default.
- Adding more roles helps less than sharpening the roles you have.

**The lesson:** the research contradicted the obvious design. Without it we'd
have built a heavier system that performed worse.

## Chapter 4 — The team, and its first real job

**2026-08-03.**

Seven specialists were defined, each with one job and hard limits enforced by
which tools they're given, not just by instructions: only the builder can edit
files; the tester and inspector can run things but not fix them.

The first real task: make the app show which running copy you're looking at, so
a half-built version can't be mistaken for the real one.

**What happened is the whole case for the approach.** The builder reported all
eight requirements passing. Independent validation found that a branch name
containing a quote mark would execute arbitrary commands every time the app was
opened. Not exotic — an ordinary apostrophe would have triggered it.

It took **8 passes, 957k tokens, 81 minutes**. A single session would have
finished in roughly half that and handed over the security hole with a confident
"all done."

**Two failures were the manager's, not the workers':** nobody committed their
work because no instruction said to, and one requirement was written wrongly.
Those are cheap to fix. The checking cost is not, and shouldn't be.

## Chapter 5 — Measuring it, and trimming

**2026-08-03, ongoing.**

Every task now records which agents ran, in what order, what each returned, and
what it cost in tokens and minutes — because "was this worth it" is not
answerable from memory.

Early optimisations, all evidence-driven:

- **Ceremony scales to the job.** A typo fix goes builder → inspector. The full
  chain is for real features.
- **Cheaper models for the builder, never for the reviewers** — the research
  showed a strong reviewer compensates for a weaker writer, which makes that
  trade safe in one direction only.
- **A rule that a re-check is only required when behaviour changed**, so a
  docstring fix doesn't trigger a full re-verification.

**What to watch, stated in advance so it can't be rationalised later:** if
validation stops finding real problems across several tasks, the checking is too
heavy and should be cut — with the log as evidence rather than a hunch. If
repair passes keep costing as much as the original build, the instructions are
too thin, and that's a management problem, not a worker problem.

---

## Where this is heading

Open questions worth answering before presenting any of it as settled:

- Does the separation keep paying, or was the injection catch a lucky first
  result? One data point is one data point.
- Does the cost per task fall as the instructions improve?
- Which of the seven roles actually earn their place?
