# docs — the workflow map, reports, proposals, and the running story

Everything here is cross-project by nature. Anything specific to one project
belongs in that project's own `docs/`, not here.

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
were at 102**.

Regenerate the PNG after any edit:

```
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=old \
  --screenshot=/tmp/wf.png --window-size=1180,20000 --force-device-scale-factor=2 \
  --hide-scrollbars --no-sandbox --disable-gpu "file://$PWD/docs/workflow.html"
```

**`--headless=old` is load-bearing.** Plain `--headless` now resolves to Chrome's
new headless mode, which ignores `--screenshot` and never exits — it hangs
until killed, writing no file and printing no error. Found 2026-08-07, after ten
minutes of waiting on a command that looked like it was working.

Then crop the trailing blank — the window is 20,000px at 2× scale, so the raw
capture is 40,000px tall and mostly empty:

```
python3 - <<'EOF'
from PIL import Image
Image.MAX_IMAGE_PIXELS = None            # 40,000px trips the decompression-bomb guard
im = Image.open("/tmp/wf.png").convert("RGB")
px, (w, h) = im.load(), im.size
bg, last = px[5, 5], h - 1
while last > 0 and all(px[x, last] == bg for x in range(0, w, 7)):
    last -= 1
im.crop((0, 0, w, min(h, last + 60))).save("docs/workflow.png")
EOF
```

Sample every 7th pixel rather than every one, or the scan takes longer than the
render. Check the result opens and is not blank before committing it: a stale or
empty diagram is worse than none, because it gets shared without a second look.

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

The audience is the-sponsor's fellow managers, some weeks from now. He is a project
manager by profession and wants to be able to explain this experience with
evidence rather than impressions: what was tried, what it cost, what broke, and
what the numbers actually showed.

See `story/README.md` for the chapters and `story/snapshots/` for the
point-in-time records that feed them.
