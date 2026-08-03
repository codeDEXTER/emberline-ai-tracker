# docs — reports and the running story

Two things live here, both cross-project by nature. Anything specific to one
project belongs in that project's own `docs/`, not here.

## `docs/*.md` — reports

Plain-language write-ups of how the system works or what changed, aimed at
someone who wasn't in the room. Written to be read on their own, without the
conversation that produced them.

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
