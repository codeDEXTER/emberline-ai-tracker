"""tracker cluster -- file-overlap clustering for not-yet-taken items and
findings (proposal 25, Z-06; A-02/A-08: "the issues need to be catalogued and
clustered together for later ... cluster by files touched, on the tracker
page").

Not-yet-taken work -- an item with `status: "not started"`, or a finding with
`state: "catalogued"` (proposal 26, C-05's catalogue -> decided lifecycle) --
carries no cluster of its own choosing here; instead, rows that share at
least one exact `files` entry are grouped into one cluster, transitively (A
shares a file with B, B shares a different file with C: all three cluster
together), so a lead picking the next bundle sees which not-started items
would make a natural bundle -- the same file-ownership grouping this session's
own wave dispatch already uses by hand.

Grouping is by *exact* file-path equality, never by folder prefix: two items
touching different files that merely live in the same directory
(`tools/tracker/lanes.py` and `tools/tracker/board.py`, say) do not cluster
together on that basis alone -- only a truly shared path does. This is the
"same-folder pitfall" the item's `done` text names.

  file_overlap_clusters(rows) -> {"clusters": [...], "singles": [...]}

    rows     [{"id", "title", "files": [...]}, ...] -- already filtered to
             not-yet-taken items/findings by not_taken_rows()
    clusters groups of 2+ rows transitively sharing a file, each
             {"id": "cluster-N", "files": [shared files, sorted],
              "items": [{"id", "title"}, ...]}, ordered by first-seen row
    singles  [{"id", "title"}, ...] for rows sharing no file with any other
             not-yet-taken row -- still visible, just not a cluster of two
"""
from __future__ import annotations

from tools.tracker import ledger as L


def not_taken_rows(ledger: dict) -> list[dict]:
    """Not-yet-taken items and findings, shaped for file_overlap_clusters():
    an item with status "not started", or a finding with state "catalogued"
    (proposal 26 C-05's still-open state, distinct from decided/deferred/
    declined). A `declined` finding is never included -- not real work.

    A finding's id is proposal-qualified (`26/F-01`) since board.py's
    cluster_state() calls this once per ledger and unions the rows from
    every ledger by id -- two different ledgers' plain `F-01` would
    otherwise collapse onto the same union-find key and silently cluster
    findings that share nothing. An item's id is left as-is; it already
    avoids the collision."""
    rows: list[dict] = []
    for item in L.items(ledger):
        if item.get("status") == "not started":
            rows.append({"id": item.get("id"), "title": item.get("title"),
                         "files": L.as_list(item.get("files"))})
    for finding in L.findings(ledger):
        if finding.get("state") == "catalogued" and finding.get("file"):
            title = finding.get("title") or f"{finding.get('source', 'finding')}: {finding['file']}"
            rows.append({"id": L.qualify_finding_id(ledger, finding.get("id")), "title": title,
                         "files": [finding["file"]]})
    return rows


class _UnionFind:
    def __init__(self, keys):
        self.parent = {k: k for k in keys}

    def find(self, k):
        while self.parent[k] != k:
            self.parent[k] = self.parent[self.parent[k]]
            k = self.parent[k]
        return k

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def file_overlap_clusters(rows: list[dict]) -> dict:
    """Connected components of `rows` over exact-file-path sharing. A row with
    no `id` is skipped -- there is nothing to bundle by. Order is stable:
    clusters and their members appear in the order their rows were first
    seen, so the output does not depend on dict/set iteration order."""
    ided = [r for r in rows if r.get("id")]
    uf = _UnionFind(r["id"] for r in ided)
    by_file: dict[str, list[str]] = {}
    for r in ided:
        for f in r.get("files") or []:
            by_file.setdefault(f, []).append(r["id"])
    for ids in by_file.values():
        for other in ids[1:]:
            uf.union(ids[0], other)

    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for r in ided:
        root = uf.find(r["id"])
        if root not in groups:
            groups[root] = []
            order.append(root)
        groups[root].append(r)

    clusters, singles = [], []
    n = 0
    for root in order:
        members = groups[root]
        if len(members) < 2:
            singles.append({"id": members[0]["id"], "title": members[0]["title"]})
            continue
        n += 1
        shared = sorted({f for m in members for f in (m.get("files") or [])
                         if len(by_file.get(f, [])) > 1})
        clusters.append({
            "id": f"cluster-{n}",
            "files": shared,
            "items": [{"id": m["id"], "title": m["title"]} for m in members],
        })
    return {"clusters": clusters, "singles": singles}
