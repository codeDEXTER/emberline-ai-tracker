# docs — the workflow map, reports, proposals, and the running story

Everything here is cross-project by nature. Anything specific to one project
belongs in that project's own `docs/`, not here.

## `workflow.html` — the bird's-eye view

The whole workflow on one page: idea to merged in the order it actually happens,
who decides what, the eight agents with their tool grants, where things get
written down, and the two tools. `workflow.png` sits beside it for sharing.

**It is derived from `CLAUDE-workflow.md`, not a second source of truth** —
where they disagree, that file wins. Per its own rule there, **any PR that
changes the shared rules updates this page and its version stamp in the same
PR**. A bird's-eye view that has drifted is worse than none: it is trusted at a
glance and read without suspicion.

Regenerate the PNG after any edit:

```
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
  --screenshot=/tmp/wf.png --window-size=1180,20000 --force-device-scale-factor=2 \
  --hide-scrollbars "file://$PWD/docs/workflow.html"
```

then crop the trailing blank with PIL (see `CHANGELOG.md`, 2026-08-04).

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

The audience is aashish's fellow managers, some weeks from now. He is a project
manager by profession and wants to be able to explain this experience with
evidence rather than impressions: what was tried, what it cost, what broke, and
what the numbers actually showed.

See `story/README.md` for the chapters and `story/snapshots/` for the
point-in-time records that feed them.
