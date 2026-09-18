"""The tracker board's Z-06 addition: not-yet-taken items and findings,
clustered by shared `files`, shown as a "Not taken, clustered by files
touched" section (proposal 25, Z-06; A-02/A-08).

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import project as P  # noqa: E402
from tools.tracker import board  # noqa: E402


def item(iid, status="not started", files=None, **more):
    d = {"id": iid, "phase": "Q", "cx": "C2", "title": iid.lower(), "status": status}
    if files is not None:
        d["files"] = files
    d.update(more)
    return d


def ledger(number, items):
    return {"proposal": number, "title": f"proposal {number}", "status": "accepted",
            "phases": [{"id": "Q", "name": "q"}], "items": items, "asks": []}


def write(root: Path, number, data) -> Path:
    """render() hashes the ledger file for its digest meta tag -- a real file
    on disk, not just a dict, is needed to call it directly in a test."""
    path = root / f"{number}-x.json"
    path.write_text(json.dumps(data))
    return path


class ClusterSectionCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / P.FILE).write_text(json.dumps({}))

    def test_two_items_sharing_a_file_appear_in_one_cluster_card(self):
        led = ledger(1, [item("Q-01", files=["tools/tracker/board.py"]),
                         item("Q-02", files=["tools/tracker/board.py", "tools/tracker/lanes.py"]),
                         item("Q-03", status="done", files=["tools/tracker/board.py"])])
        path = write(self.root, 1, led)
        text = board.render([(path, led)], "demo", None, self.root)
        self.assertIn('id="clusters"', text)
        self.assertIn("Not taken, clustered by files touched", text)
        self.assertIn("Q-01", text)
        self.assertIn("Q-02", text)
        self.assertIn("tools/tracker/board.py", text)
        # Q-03 is done, not "not yet taken" -- it must not appear in a cluster.
        cluster_section = text[text.index('id="clusters"'):]
        self.assertNotIn("Q-03", cluster_section.split("</section>", 1)[0])

    def test_a_lone_item_shows_up_as_not_clustered(self):
        led = ledger(1, [item("Q-01", files=["a.py"])])
        path = write(self.root, 1, led)
        text = board.render([(path, led)], "demo", None, self.root)
        self.assertIn("Not clustered", text)
        self.assertIn("Q-01", text)

    def test_no_not_taken_work_omits_the_section(self):
        led = ledger(1, [item("Q-01", status="done", files=["a.py"])])
        path = write(self.root, 1, led)
        text = board.render([(path, led)], "demo", None, self.root)
        self.assertNotIn('id="clusters"', text)

    def test_without_a_project_the_section_is_omitted(self):
        led = ledger(1, [item("Q-01", files=["a.py"])])
        path = write(self.root, 1, led)
        text = board.render([(path, led)], "demo", None)
        self.assertNotIn('id="clusters"', text)

    def test_the_clusters_heading_count_is_separated_from_the_word(self):
        # P-14: on a one-proposal project (PhotoVault/engine's own page) the
        # clusters heading rendered "TOUCHED0" -- board.py's shared
        # `.chip .n,.col h2 .n,.attention h2 .n` rule (the margin-left that
        # gives every other heading's count its gap) never named the
        # clusters heading's own `.n`, so `<h2>...touched <span class="n">`
        # had no gap. Assert on the markup: the count still sits in its own
        # `<span class="n">`, and the shared CSS rule now names
        # `.clusters h2 .n` alongside the others, not just this one class
        # fixed in isolation.
        led = ledger(1, [item("Q-01", files=["a.py"])])
        path = write(self.root, 1, led)
        text = board.render([(path, led)], "demo", None, self.root)
        self.assertIn(
            'Not taken, clustered by files touched <span class="n">0</span></h2>', text)
        css = text.split("<style>", 1)[-1].split("</style>", 1)[0] if "<style>" in text else text
        self.assertIn(
            '.chip .n,.col h2 .n,.attention h2 .n,.clusters h2 .n{', css)

    def test_no_other_h2_count_is_missing_from_the_shared_margin_rule(self):
        # P-14: the sponsor asked to check whether any other `h2 .n` is
        # missing from the rule too, not just the one he happened to see.
        # Every `<h2>` in the template that carries a `<span class="n">`
        # falls into one of three kinds -- a status column (one per
        # status, `.col h2 .n`), "Waiting for an answer" (`.attention h2
        # .n`), or the clusters heading (`.clusters h2 .n`); Completion,
        # Proposals and Kanban's own `<h2>` carry no count. All three kinds
        # must be named in the one shared rule -- checked here by kind,
        # not by a fixed count, since the number of status columns is
        # fixed by tools.tracker.ledger.STATUSES, not by this test.
        led = ledger(1, [item("Q-01", files=["a.py"], value="high", points=1, impact=1, likelihood=1)])
        path = write(self.root, 1, led)
        text = board.render([(path, led)], "demo", None, self.root)
        headings_with_a_count = re.findall(r'<h2\b[^>]*>(?:(?!</h2>).)*?<span class="n"', text, re.S)
        self.assertTrue(headings_with_a_count, "no h2 in the page carries a count -- fixture is wrong")
        known_kinds = (
            re.compile(r'^<h2>Not taken, clustered by files touched'),  # .clusters h2 .n
            re.compile(r'^<h2><span class="dot '),                      # .col h2 .n (one per status)
            re.compile(r'^<h2>Waiting for an answer'),                  # .attention h2 .n
        )
        for heading in headings_with_a_count:
            self.assertTrue(any(p.match(heading) for p in known_kinds),
                            f"an h2 count of an unrecognized kind: {heading!r} -- "
                            "check whether the shared margin-left rule covers it")
        rule = re.search(r'([.\w, >]+)\{font:500 12px var\(--mono\);color:var\(--dim\);'
                         r'margin-left:6px;font-variant-numeric:tabular-nums\}', text)
        self.assertIsNotNone(rule, "the shared h2/h3 count margin rule is missing entirely")
        selectors = {s.strip() for s in rule.group(1).split(",")}
        self.assertEqual(selectors, {".chip .n", ".col h2 .n", ".attention h2 .n", ".clusters h2 .n"})


if __name__ == "__main__":
    unittest.main()
