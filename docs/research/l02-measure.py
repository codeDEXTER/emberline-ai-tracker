#!/usr/bin/env python3
"""L-02 rerun (interim reading, 2026-09-16). Reuses tools/worklog.py's
list_transcripts/iter_records/dedupe_messages/usage_tokens.

Difference from the prior run (/tmp/agent-session/-Users-the sponsor-apps/
3cff917f-aeff-41f8-9753-cac90d63512e/scratchpad/measure-L01-L02-L06-H02.py):
that run excluded the parent session 3cff917f-aeff-41f8-9753-cac90d63512e
entirely because its measurement briefs contained the classifier keywords.
This run does NOT exclude any session. Instead every subagent transcript
(in every -Users-the sponsor-apps* project, including 3cff917f's own subagents
and the new lead session 26c10928-63bb-4b8d-993b-4ad09a3f6653) is classified
by its brief's first line (tag + title):
  - first line contains "measure"/"scout"/"size" (case-insensitive, word
    boundary)                                   -> class "measure_scout"
  - else first line contains "review"/"verify"/"audit"/"fix"
    (case-insensitive, word boundary)           -> class "review_fix"
  - else                                         -> class "build"
Only the FIRST LINE of the brief is used for classification (not the full
brief body), per the rerun instruction.

Window: AFTER only, from 2026-09-16T00:00:00Z (open-ended).
Tokens are deduped by message.id via worklog.dedupe_messages.

Rerunnable unchanged later: python3 measure-L02-rerun.py
"""
import sys, os, re, json

sys.path.insert(0, "common-rules/tools")
import worklog as W

AFTER_START = "2026-09-16"

MEASURE_RE = re.compile(r"\b(measure|scout|size)\b", re.I)
REVIEW_FIX_RE = re.compile(r"\b(review|verify|audit|fix)\b", re.I)


def day_of(ts):
    return ts[:10] if ts else None


def in_after(day):
    return day is not None and day >= AFTER_START


def first_line_of_brief(records):
    for rec in records:
        msg = rec.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = msg.get("content")
        text = None
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text") or ""
                    break
        if text is None:
            return None
        return text.split("\n", 1)[0]
    return None


def classify(first_line):
    if not first_line:
        return "build"
    if MEASURE_RE.search(first_line):
        return "measure_scout"
    if REVIEW_FIX_RE.search(first_line):
        return "review_fix"
    return "build"


def is_subagent_path(path):
    return (os.sep + "subagents" + os.sep) in path


def window_tokens_and_days(records):
    """Return list of (day, total_tokens) per deduped message."""
    out = []
    for rec, msg, usage in W.dedupe_messages(records):
        i, cw, cr, o = W.usage_tokens(usage)
        total = i + cw + cr + o
        ts = rec.get("timestamp") or ""
        out.append((day_of(ts), total))
    return out


def main():
    class_totals = {"measure_scout": 0, "review_fix": 0, "build": 0}
    class_n = {"measure_scout": 0, "review_fix": 0, "build": 0}
    class_sessions = {"measure_scout": set(), "review_fix": set(), "build": set()}
    all_total = 0
    n_all_with_tokens = 0
    per_transcript = []

    for proj, sess, path in W.list_transcripts():
        if not proj.startswith("-Users-the sponsor-apps"):
            continue
        if not is_subagent_path(path):
            continue
        records = list(W.iter_records(path))
        if not records:
            continue
        fl = first_line_of_brief(records)
        cls = classify(fl)
        toks = window_tokens_and_days(records)
        after_tok = sum(t for d, t in toks if in_after(d))
        if after_tok == 0:
            continue
        n_all_with_tokens += 1
        all_total += after_tok
        class_totals[cls] += after_tok
        class_n[cls] += 1
        class_sessions[cls].add((proj, sess))
        per_transcript.append({
            "project": proj, "session": sess, "class": cls,
            "first_line": fl, "after_tokens": after_tok,
        })

    review_fix_share = (class_totals["review_fix"] / all_total) if all_total else None

    result = {
        "window": f"{AFTER_START}..",
        "note": "no session excluded; 3cff917f-* and 26c10928-* subagents classified and included",
        "n_subagent_transcripts_total_with_tokens": n_all_with_tokens,
        "all_subagent_tokens": all_total,
        "by_class": {
            cls: {
                "n_transcripts": class_n[cls],
                "n_parent_sessions": len(class_sessions[cls]),
                "tokens": class_totals[cls],
                "share_of_all_subagent_tokens": (class_totals[cls] / all_total) if all_total else None,
            }
            for cls in ("measure_scout", "review_fix", "build")
        },
        "review_fix_share_of_subagent_tokens": review_fix_share,
        "verdict_review_fix_below_10pct": (
            "NOT MEASURABLE (no subagent tokens in AFTER window)" if all_total == 0
            else ("PASS" if review_fix_share < 0.10 else "FAIL")
        ),
        "sample_size_note": (
            f"thin sample: {n_all_with_tokens} subagent transcript(s) with tokens in window"
            if n_all_with_tokens < 5 else None
        ),
        "per_transcript": per_transcript,
        "command": "python3 measure-L02-rerun.py",
    }
    print(json.dumps(result, indent=2, default=str))

    # Written to the temp dir, never beside this committed script.
    import tempfile
    outpath = os.path.join(tempfile.gettempdir(), "measure-L02-rerun-out.json")
    with open(outpath, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    return result


if __name__ == "__main__":
    main()
