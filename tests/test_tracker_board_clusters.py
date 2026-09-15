"""The tracker board's Z-06 addition: not-yet-taken items and findings,
clustered by shared `files`, shown as a "Not taken, clustered by files
touched" section (proposal 25, Z-06; A-02/A-08).

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import json
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


if __name__ == "__main__":
    unittest.main()
