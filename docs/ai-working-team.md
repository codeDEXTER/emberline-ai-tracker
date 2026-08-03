# Your AI working team

*Report, 2026-08-03. Plain language, for someone who wasn't in the room.*
Rendered version: https://claude.ai/code/artifact/ce745104-b7fd-466a-8aa4-16bd43659cbf

---

## The problem, in one line

One assistant doing everything also marks its own homework — so nobody ever
catches what it got wrong.

Until now, a single chat planned the work, wrote the code, tested it, and then
said it was finished. Every step done by the same thing, with the same blind
spots. A misunderstanding at the start travelled all the way through and still
came out as "done."

The fix is the one any workshop uses: **whoever builds a thing never signs it
off.**

## Who's on the team

You sit above all of them. The manager is just the chat window — it never writes
code, it hands work out and tells you what needs deciding.

| Role | Job | Cannot |
|---|---|---|
| **You** | Decide what gets built, approve what ships | — |
| **Manager** | Pick who works, pass messages, escalate | Write code |
| **Researcher** | Find the options before anything's decided | Choose between them |
| **Designers** (two) | Ideas first, then buildable detail | Write production code |
| **Rule writer** | Define what "done" means, testably | Design the solution |
| **Builder** | Write the code | Approve its own work |
| **Breaker** | Try to make it fail | Fix what it finds |
| **Inspector** | Final check before anything ships | Fix, or approve the merge |

The point isn't the headcount. It's that the builder can't sign off, the breaker
can't fix, and the inspector can't do either. The limits are enforced by which
tools each one is given, not just by instructions.

## How a job moves

```
You agree      →  Builder    →  Breaker      →  Inspector  →  You approve
what & done       builds        tries to        does it
                                break it        really work
                     ↑               |
                     └───────────────┘
                    found a problem — back to the builder
                    (twice, then it comes to you)
```

Small jobs skip most of this. A typo fix goes builder → inspector. The full chain
is for real features — putting a one-line change through seven people is theatre.

## What happened on the first real job

We asked for the app to show which copy you're looking at, so a half-built
version can't be mistaken for the real one.

> **Builder:** "Done. All eight things you asked for, working."
>
> **Breaker:** "No. Name a branch with a quote mark in it and this app runs
> whatever's in that name — every time you open it."
>
> **Builder:** "You're right. Fixed." *(Also disagreed with one other complaint,
> and was right to.)*
>
> **Inspector:** "Not so fast — nothing was actually saved to the project."
>
> **Inspector, later:** "Now it's good. And here's one more thing nobody spotted."

That second line is the whole argument. The builder genuinely believed it was
finished. On its own, that hole ships — and it wasn't exotic; an ordinary
apostrophe in a branch name would have set it off.

## What it cost

| | |
|---|---|
| Helpers used | 7 |
| Their time | 81 minutes |
| Your time blocked | none — it ran in the background |
| Real bugs caught | 2 |
| Tokens | 957,000 |

One assistant alone would have finished in roughly half the time, and handed over
the security hole with a confident "all done."

Being straight about the rest: some of that 81 minutes was wasted on *management*
mistakes, not the team's — the builder was never told to save its work, and one
requirement was written wrongly. Those should shrink. The checking time shouldn't.

## The rules that hold it together

- **You decide what gets built and what ships.** Nobody starts or finishes
  without you.
- **Nobody checks their own work.**
- **Arguments end.** Two rounds, then it comes to you. Same if a helper keeps
  retrying something that keeps failing.
- **Every helper cleans up** what it started — except your real copy, which always
  stays running.
- **Mistakes get written down** in a notes file the helpers read before starting.
- **Nobody changes the rules but you.** Not even to fix a typo.

## What I'd do next

Run three or four more real jobs and watch two numbers:

- **Does the breaker keep finding real problems?** If yes, this earns its cost. If
  it finds nothing across several jobs, lighten it — with evidence, not a hunch.
- **Is repair time creeping towards build time?** If so, the instructions are too
  thin, which is a management problem, not a worker problem.

One job is one job. It caught something real and expensive, which is a good sign
— not proof.
