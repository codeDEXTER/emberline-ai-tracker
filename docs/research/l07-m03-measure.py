#!/usr/bin/env python3
"""L-07 / M-03 measurement script. Reuses tools/worklog.py parsing helpers
(dedupe_messages, iter_records, usage_tokens, _parse_ts).

Kept 2026-09-16 so the L-07 re-measure (from 2026-09-23) reruns the same
cluster definitions: python3 docs/research/l07-m03-measure.py; move the
AFTER window first."""
import sys, os, json, re, glob, datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
import worklog as W

PROJECTS = os.path.expanduser("~/.claude/projects")

BEFORE_START = datetime.datetime.fromisoformat("2026-09-08T00:00:00+00:00")
BEFORE_END   = datetime.datetime.fromisoformat("2026-09-15T00:00:00+00:00")  # exclusive, covers 08..14
AFTER_START  = datetime.datetime.fromisoformat("2026-09-16T00:00:00+00:00")
AFTER_END    = datetime.datetime.fromisoformat("2026-09-30T00:00:00+00:00")  # generous upper bound

M03_LANDED = datetime.datetime.fromisoformat("2026-09-15T19:46:02+02:00")


def ts_of(rec):
    return W._parse_ts(rec.get("timestamp"))


def in_window(dt, start, end):
    return dt is not None and start <= dt < end


def relevant_projects():
    for name in sorted(os.listdir(PROJECTS)):
        if name.startswith("-Users-aashish-apps"):
            yield name


def iter_project_transcripts():
    """Yield (project, session, path, kind) restricted to -Users-aashish-apps* slugs."""
    for path in glob.glob(os.path.join(PROJECTS, "-Users-aashish-apps*", "*.jsonl")):
        session = os.path.splitext(os.path.basename(path))[0]
        proj = os.path.basename(os.path.dirname(path))
        yield proj, session, path, "main"
    for path in glob.glob(os.path.join(PROJECTS, "-Users-aashish-apps*", "*", "subagents", "*.jsonl")):
        parts = path.split(os.sep)
        proj, session = parts[-4], parts[-3]
        yield proj, session, path, "subagent"


# ---------------------------------------------------------------------------
# L-07: three tool-call clusters
#
# (a) `cat`/`sed -n` used to READ a file's contents from Bash, instead of the
#     Read tool. Excludes `cat > file` / `cat >> file` / `cat <<EOF` (writes,
#     not reads) and bare `| cat` (pager suppression on e.g. `git log`, not a
#     file read).
# (b) HANDOFF.md / AGENT-LOG.md hand-appended via Bash (heredoc/echo >>) or
#     via the Edit/Write tool, instead of `bin/spend agentlog` / `bin/remember`.
# (c) raw `flutter test` instead of `gate.sh` (Flutter-project only).
# ---------------------------------------------------------------------------

CAT_READ_RE = re.compile(
    r"(^|[;&|]\s*)cat(\s+-[A-Za-z]+)?\s+(?!>|>>|<<)(?!-)[^\s;&|<>][^\s;&|]*")
SED_READ_RE = re.compile(r"(^|[;&|]\s*)sed\s+-n\s+\S+\s+(?!>|>>)[^\s;&|<>]+")
FLUTTER_TEST_RE = re.compile(r"(^|[;&|]\s*)flutter\s+test\b")
GATE_SH_RE = re.compile(r"gate\.sh\b")
HANDOFF_RE = re.compile(r"\b(HANDOFF|AGENT-LOG)\.md\b")
APPEND_RE = re.compile(r">>")
HEREDOC_APPEND_HINT_RE = re.compile(r"\b(echo|printf|cat)\b.*>>|>>\s*.*\.md")


def classify_bash_command(cmd):
    """Return set of cluster tags a single Bash `command` string triggers."""
    tags = set()
    if not cmd:
        return tags
    if CAT_READ_RE.search(cmd) or SED_READ_RE.search(cmd):
        tags.add("a_sed_cat")
    if HANDOFF_RE.search(cmd) and APPEND_RE.search(cmd):
        tags.add("b_handoff_append")
    if FLUTTER_TEST_RE.search(cmd) and not GATE_SH_RE.search(cmd):
        tags.add("c_flutter_test")
    return tags


def scan_window(start, end, label):
    total_tool_calls = 0
    cluster_counts = {"a_sed_cat": 0, "b_handoff_append": 0, "c_flutter_test": 0}
    flutter_tool_calls_seen = 0
    sessions = set()

    for proj, session, path, kind in iter_project_transcripts():
        try:
            records = list(W.iter_records(path))
        except OSError:
            continue
        if not records:
            continue
        touches = any(in_window(ts_of(rec), start, end) for rec in records)
        if not touches:
            continue

        is_flutter_project = "photo-vault" in proj.lower() or "photovault" in proj.lower()

        for rec, msg, usage in W.dedupe_messages(records):
            dt = ts_of(rec)
            if not in_window(dt, start, end):
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                total_tool_calls += 1
                sessions.add((proj, session))
                name = block.get("name") or ""
                inp = block.get("input") or {}
                if is_flutter_project:
                    flutter_tool_calls_seen += 1
                if name == "Bash":
                    cmd = inp.get("command") or ""
                    for tag in classify_bash_command(cmd):
                        cluster_counts[tag] += 1
                elif name in ("Edit", "Write"):
                    fp = inp.get("file_path") or ""
                    if re.search(r"(HANDOFF|AGENT-LOG)\.md$", fp):
                        cluster_counts["b_handoff_append"] += 1

    return {
        "label": label,
        "total_tool_calls": total_tool_calls,
        "cluster_counts": cluster_counts,
        "sessions": len(sessions),
        "flutter_tool_calls_seen": flutter_tool_calls_seen,
    }


def per100(count, total):
    if total == 0:
        return None
    return round(count / total * 100, 3)


def l07():
    before = scan_window(BEFORE_START, BEFORE_END, "BEFORE 2026-09-08..09-14")
    after = scan_window(AFTER_START, AFTER_END, "AFTER 2026-09-16+")

    out = {"before": before, "after": after, "clusters": {}}
    original_magnitudes = {"a_sed_cat": 295, "b_handoff_append": 158, "c_flutter_test": 138}
    for tag in ("a_sed_cat", "b_handoff_append", "c_flutter_test"):
        b_raw = before["cluster_counts"][tag]
        a_raw = after["cluster_counts"][tag]
        b_rate = per100(b_raw, before["total_tool_calls"])
        a_rate = per100(a_raw, after["total_tool_calls"])
        measurable = True
        note = ""
        if tag == "c_flutter_test" and after["flutter_tool_calls_seen"] == 0:
            measurable = False
            note = "AFTER window has no Flutter-project tool calls at all"
        verdict = None
        if measurable:
            if b_rate in (None, 0):
                verdict = "baseline rate is 0/undefined -- halving is not a meaningful test"
            elif a_rate is None:
                verdict = "no AFTER tool calls at all in this corpus"
            else:
                verdict = "halved" if a_rate <= b_rate / 2 else "not halved"
        else:
            verdict = "NOT MEASURABLE"
        out["clusters"][tag] = {
            "original_magnitude_2026_09_15_mining": original_magnitudes[tag],
            "before_raw": b_raw,
            "before_per_100_tool_calls": b_rate,
            "after_raw": a_raw,
            "after_per_100_tool_calls": a_rate,
            "measurable": measurable,
            "note": note,
            "verdict": verdict,
        }
    return out


# ---------------------------------------------------------------------------
# M-03: tool-definition tokens per session, first request only, ruflo-config
# projects (those with a claude-flow/ruflo entry in .mcp.json)
# ---------------------------------------------------------------------------

def first_request_tokens(path):
    records = list(W.iter_records(path))
    for rec, msg, usage in W.dedupe_messages(records):
        i, cw, cr, o = W.usage_tokens(usage)
        return i + cw + cr, rec.get("timestamp")
    return None, None


def m03():
    ruflo_projects = [p for p in relevant_projects() if "ruflo" in p.lower()
                      and "photo-vault-ruflo--claude-worktrees" not in p]
    all_points = []
    for proj in ruflo_projects:
        for path in sorted(glob.glob(os.path.join(PROJECTS, proj, "*.jsonl"))):
            session = os.path.splitext(os.path.basename(path))[0]
            tok, ts = first_request_tokens(path)
            if tok is None or tok == 0:
                continue
            dt = W._parse_ts(ts)
            all_points.append({"project": proj, "session": session,
                                "timestamp": ts, "tokens": tok,
                                "before_m03": dt is not None and dt < M03_LANDED})

    before_vals = [p["tokens"] for p in all_points if p["before_m03"]]
    after_vals = [p["tokens"] for p in all_points if not p["before_m03"]]

    def median(xs):
        if not xs:
            return None
        s = sorted(xs)
        n = len(s)
        mid = n // 2
        return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2

    return {
        "ruflo_projects_considered": ruflo_projects,
        "all_points": all_points,
        "before_m03_landing": {"n": len(before_vals), "median": median(before_vals), "values": before_vals},
        "after_m03_landing": {"n": len(after_vals), "median": median(after_vals), "values": after_vals},
    }


if __name__ == "__main__":
    result = {"L-07_raw": l07(), "M-03_raw": m03()}
    outpath = os.path.join(os.path.dirname(__file__), "measure-raw.json")
    with open(outpath, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    print("wrote", outpath)
