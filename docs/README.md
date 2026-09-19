# docs — the workflow map, reports, proposals, and the running story

Everything here is cross-project by nature. Anything specific to one project
belongs in that project's own `docs/`, not here.

## Start here

The documentation has four clear surfaces:

- **Public story:** [`../README.md`](../README.md), [`public-review.html`](public-review.html), and [`warmup-reheat.html`](warmup-reheat.html)
- **Getting started:** [`GETTING-STARTED.md`](GETTING-STARTED.md) and [`OPERATING-RULES.md`](OPERATING-RULES.md)
- **Live evidence:** [`proposals/tracker/index.html`](proposals/tracker/index.html), [`proposals/`](proposals/), and [`handovers/`](handovers/)
- **Reports and reference:** the workflow pages, release notes, research, and the running story listed below

The paths under `proposals/`, `handovers/`, and `OPERATING-RULES.md` are
workflow contracts. Keep those locations stable; use this index to make the
structure discoverable instead of duplicating or moving the sources of truth.

## `workflow.html` — the bird's-eye view

The whole workflow on one page: idea to merged in the order it actually happens,
who decides what, the eight agents with their tool grants, where things get
written down, and the three tools. `workflow.png` sits beside it for sharing.

**It is derived from `CLAUDE-workflow.md`, not a second source of truth** —
where they disagree, that file wins. Per its own rule there, **any PR that
changes the shared rules updates this page and its version stamp in the same
PR**. A bird's-eye view that has drifted is worse than none: it is trusted at a
glance and read without suspicion.

**The stamp names the version at which `CLAUDE-workflow.md` last changed** —
not the current HEAD count. That distinction is what keeps it fixable: a stamp
defined against HEAD can never name the commit it is written in, so every
correction lands one behind and needs correcting again. Defined against the
rules file, a commit that only touches this page leaves the target still.

`tests/test_workflow_stamp.py` enforces it, because this rule was maintained by
memory until 2026-08-07 and the page had drifted to **version 62 while the rules
were at 102**, and again on 17 Sep 2026, when three merges in one evening left
it hand-stamped twice.

**Run `bin/workflow-stamp` after any edit to the rules.** It writes the stamp
from git (the same `rules_version()` `tests/test_workflow_stamp.py` checks
against — see that function's docstring for why it counts commits touching
`CLAUDE-workflow.md` rather than `HEAD`) and regenerates `docs/workflow.png`
with the headless-Chrome recipe below, baked into the script so nobody types
it by hand again. It fails loudly — writing nothing — when Chrome can't be
found or the capture comes back blank, rather than committing a broken png.
`bin/workflow-stamp --check` reports whether the stamp and the png are
current without writing anything; that's what `gates.merge` runs before the
test suite (`.common-rules.json`), so a stale stamp fails fast rather than
sixty seconds into the full suite.

`bin/workflow-stamp` does **not** write the sentence describing what
changed — a rules change still needs a human paragraph on this page, same as
always. It only removes the bookkeeping around it: the number, and the
picture. What it automates, for the record: headless Chrome with
`--headless=old` (plain `--headless` now resolves to Chrome's new headless
mode, which ignores `--screenshot` and never exits — it hangs until killed,
writing no file and printing no error; found 2026-08-07 after ten minutes of
waiting on a command that looked like it was working), then a crop of the
trailing blank — the window is 20,000px at 2× scale, so the raw capture is
40,000px tall and mostly empty, and the crop samples every 7th pixel rather
than every one, or the scan takes longer than the render. Still worth doing
by hand once: open the regenerated png and look at it before committing — a
stale or empty diagram is worse than none, because it gets shared without a
second look, and no script can tell "blank" from "correct but boring" for
certain.

## `proposals/` — decisions about the shared rules themselves

Numbered HTML, status in the document, index derived from the documents. Project
proposals live in that project's own `docs/proposals/`.

## `docs/*.md` — reports

Plain-language write-ups of how the system works or what changed, aimed at
someone who wasn't in the room. Written to be read on their own, without the
conversation that produced them.

Each report should also ship a **full-page PNG** beside it (same basename), so it
can be dropped into a slide or a message without sending a link or asking anyone
to render markdown. Regenerate it whenever the report changes — a stale image is
worse than none, because it will be the version that gets shared.

The standard to match is `ai-working-team.md`: short sentences, concrete
examples, a diagram where one helps, and the awkward parts left in. A report
that only describes what went well is marketing, and useless six weeks later
when you're trying to remember why a decision was made.

## `docs/story/` — the running story

A chronological record of how working with Claude Code on these projects has
actually gone — starting from a single chat window doing everything, through
building a team of agents, to trying to make that team cheaper and sharper.

The audience is the sponsor's fellow managers, some weeks from now. He is a project
manager by profession and wants to be able to explain this experience with
evidence rather than impressions: what was tried, what it cost, what broke, and
what the numbers actually showed.

See `story/README.md` for the chapters and `story/snapshots/` for the
point-in-time records that feed them.
