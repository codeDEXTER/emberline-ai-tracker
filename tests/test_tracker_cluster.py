"""File-overlap clustering for not-yet-taken items and findings (proposal 25,
Z-06): two not-started items sharing a file end up in the same cluster, a
third with no overlap doesn't, and two items merely sharing a folder (not an
exact file) do not cluster on that basis alone (the "same-folder pitfall").

Run:  python3 -m unittest discover -s tests -q
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.tracker import cluster as C  # noqa: E402


def item(id_, files, status="not started", **extra):
    row = {"id": id_, "phase": "Z", "cx": "C2", "title": id_, "status": status, "files": files}
    row.update(extra)
    return row


def finding(id_, file_, state="catalogued", **extra):
    row = {"id": id_, "source": "review", "file": file_, "severity": "low", "state": state}
    row.update(extra)
    return row


def ledger(proposal=25, items=None, findings=None):
    return {"proposal": proposal, "title": "t", "status": "accepted",
            "phases": [{"id": "Z", "name": "build"}],
            "items": items or [], "findings": findings or [], "asks": []}


class TestNotTakenRows(unittest.TestCase):
    def test_not_started_items_and_catalogued_findings_are_included(self):
        d = ledger(items=[item("Z-10", ["a.py"]), item("Z-11", ["b.py"], status="done")],
                   findings=[finding("F-01", "c.py"), finding("F-02", "d.py", state="decided")])
        rows = C.not_taken_rows(d)
        ids = {r["id"] for r in rows}
        # A finding's id is proposal-qualified ("25/F-01"), so board.py's
        # cluster_state() can union rows from more than one ledger without
        # two different ledgers' plain "F-01" colliding as one key. An
        # item's id is left as-is.
        self.assertEqual(ids, {"Z-10", "25/F-01"})

    def test_declined_and_deferred_findings_are_excluded(self):
        d = ledger(findings=[finding("F-01", "c.py", state="declined"),
                             finding("F-02", "d.py", state="deferred")])
        self.assertEqual(C.not_taken_rows(d), [])

    def test_two_ledgers_each_with_their_own_f01_do_not_collide(self):
        # board.py's cluster_state() combines not_taken_rows() from every
        # ledger and unions them by id -- two different ledgers' plain
        # "F-01" would otherwise collapse onto one _UnionFind key (a dict
        # comprehension over duplicate keys keeps only the last one) and
        # silently merge two findings that share no file.
        left = ledger(25, findings=[finding("F-01", "a.py")])
        right = ledger(30, findings=[finding("F-01", "b.py")])
        rows = C.not_taken_rows(left) + C.not_taken_rows(right)
        ids = {r["id"] for r in rows}
        self.assertEqual(len(rows), 2)
        self.assertEqual(ids, {"25/F-01", "30/F-01"})
        result = C.file_overlap_clusters(rows)
        self.assertEqual(result["clusters"], [])
        self.assertEqual({s["id"] for s in result["singles"]}, {"25/F-01", "30/F-01"})


class TestFileOverlapClusters(unittest.TestCase):
    def test_two_items_sharing_a_file_cluster_together(self):
        rows = [
            {"id": "Z-10", "title": "a", "files": ["tools/tracker/board.py"]},
            {"id": "Z-11", "title": "b", "files": ["tools/tracker/board.py", "tools/tracker/lanes.py"]},
        ]
        result = C.file_overlap_clusters(rows)
        self.assertEqual(len(result["clusters"]), 1)
        self.assertEqual({m["id"] for m in result["clusters"][0]["items"]}, {"Z-10", "Z-11"})
        self.assertEqual(result["clusters"][0]["files"], ["tools/tracker/board.py"])
        self.assertEqual(result["singles"], [])

    def test_a_third_item_with_no_overlap_does_not_join(self):
        rows = [
            {"id": "Z-10", "title": "a", "files": ["tools/tracker/board.py"]},
            {"id": "Z-11", "title": "b", "files": ["tools/tracker/board.py"]},
            {"id": "Z-12", "title": "c", "files": ["tools/tracker/risk.py"]},
        ]
        result = C.file_overlap_clusters(rows)
        self.assertEqual(len(result["clusters"]), 1)
        self.assertEqual({m["id"] for m in result["clusters"][0]["items"]}, {"Z-10", "Z-11"})
        self.assertEqual([s["id"] for s in result["singles"]], ["Z-12"])

    def test_same_folder_different_file_does_not_cluster(self):
        """The same-folder pitfall: two items touching different files that
        merely live in the same directory must not be treated as overlapping."""
        rows = [
            {"id": "Z-10", "title": "a", "files": ["tools/tracker/board.py"]},
            {"id": "Z-11", "title": "b", "files": ["tools/tracker/lanes.py"]},
        ]
        result = C.file_overlap_clusters(rows)
        self.assertEqual(result["clusters"], [])
        self.assertEqual({s["id"] for s in result["singles"]}, {"Z-10", "Z-11"})

    def test_transitive_clustering_across_a_chain(self):
        rows = [
            {"id": "Z-10", "title": "a", "files": ["x.py"]},
            {"id": "Z-11", "title": "b", "files": ["x.py", "y.py"]},
            {"id": "Z-12", "title": "c", "files": ["y.py"]},
        ]
        result = C.file_overlap_clusters(rows)
        self.assertEqual(len(result["clusters"]), 1)
        self.assertEqual({m["id"] for m in result["clusters"][0]["items"]}, {"Z-10", "Z-11", "Z-12"})

    def test_rows_with_no_files_are_singles(self):
        rows = [{"id": "Z-10", "title": "a", "files": []}]
        result = C.file_overlap_clusters(rows)
        self.assertEqual(result["clusters"], [])
        self.assertEqual([s["id"] for s in result["singles"]], ["Z-10"])

    def test_empty_input(self):
        self.assertEqual(C.file_overlap_clusters([]), {"clusters": [], "singles": []})


if __name__ == "__main__":
    unittest.main()
