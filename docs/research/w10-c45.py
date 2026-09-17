#!/usr/bin/env python3
"""W-10 measurement: proposal 19 exit conditions 4 and 5, pilot week.

(4) "Every sponsor message in the pilot week has an ask row or is an
    answer -- measured from the transcript, not claimed."
(5) "Every agent brief in the pilot week carries the five headings --
    measured the same way."

Reuses tools/worklog.py's iter_records / list_transcripts (the one place
that knows the on-disk transcript shape) -- this script adds nothing to
that module, it only reads with it.

Never prints or stores message/brief text -- counts, ids, timestamps only.

Rerunnable unchanged: --end defaults to "now" at run time, so running this
again after the pilot week ends (about 2026-09-20) with no arguments
measures the full week.

Usage (exact command used for the interim reading in this report):
    python3 w10_c45.py \\
        --start 2026-09-14T00:00:00+02:00 \\
        --out report.json

Kept 2026-09-17 for the scheduled W-10 final measurement (2026-09-21):
python3 docs/research/w10-c45.py --start 2026-09-14T00:00:00+02:00 --end 2026-09-21T00:00:00+02:00 --out <scratch>/report.json
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re
import sys

COMMON_RULES = "/Users/aashish/apps/common-rules"
sys.path.insert(0, os.path.join(COMMON_RULES, "tools"))
import worklog  # noqa: E402  (iter_records, list_transcripts)

PROJECTS_ROOT = os.path.expanduser("~/.claude/projects")

# ---------------------------------------------------------------------------
# Project definitions, verbatim from the brief.
# ---------------------------------------------------------------------------

PROJECTS = {
    "photovault-engine": {
        "slug_prefixes": ["-Users-aashish-apps-PhotoVault-engine"],
        "ledger_globs": [
            "/Users/aashish/apps/PhotoVault/engine/docs/proposals/*.json",
        ],
    },
    "photovault-app": {
        "slug_prefixes": ["-Users-aashish-apps-PhotoVault-app"],
        "ledger_globs": [
            "/Users/aashish/apps/PhotoVault/app/docs/proposals/*.json",
        ],
    },
    "common-rules": {
        # Lead sessions for common-rules started in /Users/aashish/apps
        # (slug -Users-aashish-apps, exact -- that cwd is shared with
        # every other project run from the apps root) and in
        # -Users-aashish-apps-common-rules (no main sessions found there
        # as of this run, only worktree-suffixed slugs, kept for when one
        # exists).
        "slug_exact": ["-Users-aashish-apps"],
        "slug_prefixes": ["-Users-aashish-apps-common-rules"],
        "ledger_globs": [
            os.path.join(COMMON_RULES, "docs/proposals/*.json"),
        ],
    },
}

# ---------------------------------------------------------------------------
# Exclusion markers for "sponsor message" -- brief's definition.
# ---------------------------------------------------------------------------

_EXCLUDE_MARKERS = (
    "<command-name>",
    "<local-command-stdout>",
    "<command-message>",
    "<system-reminder",
    "<task-notification",
    "<cross-session-message",
    "This session is being continued from a previous conversation",
)

_HEADINGS = ["CONTEXT", "OWNS", "MUST", "MUST NOT", "OUTPUT"]

_STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "or", "is",
    "it", "this", "that", "with", "as", "be", "at", "we", "you", "i",
    "can", "do", "does", "if", "not", "no", "yes", "but", "so", "are",
    "was", "were", "will", "would", "should", "could", "have", "has",
    "had", "its", "by", "from", "your", "my", "me", "us", "our",
}


def _parse_ts(ts):
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(ts)
    except ValueError:
        return None


def _words(text):
    return {
        w for w in re.findall(r"[a-z0-9']+", (text or "").lower())
        if len(w) >= 3 and w not in _STOPWORDS
    }


def _text_of(content):
    """Plain text of a user message's content, or None if it is not
    ('plain string or text blocks') -- e.g. tool_result-bearing."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if not isinstance(block, dict):
                return None
            btype = block.get("type")
            if btype == "text":
                texts.append(block.get("text") or "")
            elif btype == "tool_result":
                return None
            # other block types (e.g. image) are ignored, not disqualifying
        if texts:
            return "\n".join(texts)
        return None
    return None


def _is_excluded(text):
    for marker in _EXCLUDE_MARKERS:
        if marker in text:
            return True
    return False


def _assistant_text_and_askq(msg):
    """(text, saw_ask_user_question) for one assistant message."""
    content = msg.get("content")
    text_parts = []
    saw_askq = False
    if isinstance(content, str):
        text_parts.append(content)
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text_parts.append(block.get("text") or "")
            elif block.get("type") == "tool_use" and block.get("name") == "AskUserQuestion":
                saw_askq = True
    return "\n".join(text_parts), saw_askq


def _load_ledgers(globs):
    """[(source_path, [ask dicts with parsed 'at'])]"""
    out = []
    for pattern in globs:
        for path in sorted(glob.glob(pattern)):
            try:
                with open(path) as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            asks = data.get("asks")
            if not isinstance(asks, list):
                continue
            parsed = []
            for a in asks:
                if not isinstance(a, dict):
                    continue
                at = _parse_ts(a.get("at"))
                parsed.append({
                    "id": a.get("id"),
                    "at": at,
                    "quote": a.get("quote") or "",
                    "state": a.get("state"),
                })
            out.append((path, parsed))
    return out


def _project_transcripts(project_key, cfg):
    """(project_dir_name, session, path) for MAIN transcripts of one
    project, per the brief's slug rules."""
    exact = set(cfg.get("slug_exact", []))
    prefixes = tuple(cfg.get("slug_prefixes", []))
    for project_dir, session, path in worklog.list_transcripts(PROJECTS_ROOT):
        if (os.sep + "subagents" + os.sep) in path:
            continue  # main sessions only -- sponsor turns and Agent
                      # dispatches happen there, never inside a subagent
                      # transcript
        if project_dir in exact or project_dir.startswith(prefixes):
            yield project_dir, session, path


def measure_project(project_key, cfg, start, end):
    ledgers = _load_ledgers(cfg["ledger_globs"])
    all_asks = []
    for source, asks in ledgers:
        for a in asks:
            a2 = dict(a)
            a2["source"] = os.path.basename(source)
            all_asks.append(a2)

    sponsor_total = 0
    matched = 0
    answer = 0
    unmatched = 0
    unmatched_list = []

    brief_total = 0
    brief_all_five = 0
    missing_heading_counts = {h: 0 for h in _HEADINGS}

    transcripts_seen = 0
    sessions_seen = set()

    for project_dir, session, path in _project_transcripts(project_key, cfg):
        transcripts_seen += 1
        records = list(worklog.iter_records(path))

        last_assistant_text = ""
        last_assistant_askq = False

        for rec in records:
            rtype = rec.get("type")
            msg = rec.get("message")
            ts = _parse_ts(rec.get("timestamp"))

            if rtype == "assistant" and isinstance(msg, dict):
                text, askq = _assistant_text_and_askq(msg)
                last_assistant_text = text
                last_assistant_askq = askq

                # agent briefs: Agent tool_use blocks in this assistant turn
                content = msg.get("content")
                if isinstance(content, list):
                    for block in content:
                        if not (isinstance(block, dict)
                                and block.get("type") == "tool_use"
                                and block.get("name") == "Agent"):
                            continue
                        if ts is None or not (start <= ts < end):
                            continue
                        prompt = (block.get("input") or {}).get("prompt")
                        if not isinstance(prompt, str) or not prompt:
                            continue
                        brief_total += 1
                        sessions_seen.add(session)
                        lines = {ln.strip() for ln in prompt.splitlines()}
                        missing = [h for h in _HEADINGS if h not in lines]
                        if not missing:
                            brief_all_five += 1
                        for h in missing:
                            missing_heading_counts[h] += 1
                continue

            if rtype != "user" or not isinstance(msg, dict):
                continue
            if rec.get("isMeta"):
                last_assistant_text, last_assistant_askq = "", False
                continue
            if rec.get("isCompactSummary"):
                continue

            text = _text_of(msg.get("content"))
            if text is None:
                continue
            if _is_excluded(text):
                continue
            if ts is None or not (start <= ts < end):
                continue

            sponsor_total += 1
            sessions_seen.add(session)

            is_answer = (
                last_assistant_askq
                or last_assistant_text.rstrip().rstrip('"”').endswith("?")
            )

            msg_words = _words(text)
            best = None
            for a in all_asks:
                if a["at"] is None or ts is None:
                    continue
                if abs((ts - a["at"]).total_seconds()) > 2 * 3600:
                    continue
                qwords = _words(a["quote"])
                if not qwords:
                    continue
                overlap = len(msg_words & qwords)
                threshold = max(2, round(0.3 * len(qwords)))
                if overlap >= threshold:
                    score = overlap / len(qwords)
                    if best is None or score > best[0]:
                        best = (score, a["id"])

            if best is not None:
                matched += 1
            elif is_answer:
                answer += 1
            else:
                unmatched += 1
                unmatched_list.append({
                    "session": session,
                    "timestamp": rec.get("timestamp"),
                })

    condition4 = {
        "sponsor_messages": sponsor_total,
        "matched": matched,
        "answer": answer,
        "unmatched": unmatched,
        "unmatched_messages": unmatched_list,
        "verdict": (
            "NOT MEASURABLE" if sponsor_total == 0
            else "MET" if unmatched == 0
            else "NOT MET"
        ),
    }
    condition5 = {
        "briefs_total": brief_total,
        "briefs_with_all_five": brief_all_five,
        "missing_heading_counts": missing_heading_counts,
        "verdict": (
            "NOT MEASURABLE" if brief_total == 0
            else "MET" if brief_all_five == brief_total
            else "NOT MET"
        ),
    }

    return {
        "transcripts_seen": transcripts_seen,
        "sessions_seen": sorted(sessions_seen),
        "ask_rows_in_ledgers": len(all_asks),
        "ledger_files": [os.path.basename(p) for p, _ in ledgers],
        "condition4": condition4,
        "condition5": condition5,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2026-09-14T00:00:00+02:00",
                     help="pilot-week window start (ISO 8601)")
    ap.add_argument("--end", default=None,
                     help="pilot-week window end (ISO 8601); default is "
                          "now, at run time")
    ap.add_argument("--out", default=os.path.join(__import__("tempfile").gettempdir(), "w10-c45-report.json"))
    args = ap.parse_args()

    start = _parse_ts(args.start)
    end = _parse_ts(args.end) if args.end else datetime.datetime.now(
        datetime.timezone.utc)
    if start.tzinfo is None:
        start = start.replace(tzinfo=datetime.timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=datetime.timezone.utc)

    report = {
        "measured_at": datetime.datetime.now(datetime.timezone.utc)
                        .isoformat(),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "command": "python3 w10_c45.py --start " + args.start
                    + (f" --end {args.end}" if args.end else "")
                    + f" --out {args.out}",
        "projects": {},
    }

    overall_ok = True
    any_measurable = False
    for key, cfg in PROJECTS.items():
        result = measure_project(key, cfg, start, end)
        report["projects"][key] = result
        for cond in ("condition4", "condition5"):
            v = result[cond]["verdict"]
            if v == "NOT MET":
                overall_ok = False
            if v != "NOT MEASURABLE":
                any_measurable = True

    report["overall_interim_verdict"] = (
        "NOT MEASURABLE" if not any_measurable
        else "MET" if overall_ok
        else "NOT MET"
    )

    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
