"""L-06: builder read/inspect spend, scout-fed vs no scout. Counts Read/Grep/Glob
and read-only Bash (cat, sed -n, grep, rg, ls, head, tail, find, git log/show/diff)
tool calls, and the size of their tool_result text (chars/4 ~ tokens), in total
and before the builder's first Edit/Write."""
import json, sys, glob, os, re
READ_BASH = re.compile(r"^\s*(cd [^&;]+(&&|;)\s*)?(cat|sed -n|grep|rg|ls|head|tail|find|wc|git (log|show|diff|grep))\b")
def measure(path):
    uses = {}; out = {"calls": 0, "chars": 0, "calls_pre_edit": 0, "chars_pre_edit": 0}
    edited = False
    for line in open(path):
        r = json.loads(line); m = r.get("message") or {}
        c = m.get("content")
        if not isinstance(c, list): continue
        for b in c:
            if b.get("type") == "tool_use":
                n = b["name"]; inp = b.get("input") or {}
                if n in ("Edit", "Write", "MultiEdit"): edited = True
                is_read = n in ("Read", "Grep", "Glob") or (n == "Bash" and READ_BASH.match(inp.get("command", "")))
                uses[b["id"]] = (is_read, edited)
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in uses:
                is_read, was_edited = uses[b["tool_use_id"]]
                if not is_read: continue
                t = b.get("content"); t = t if isinstance(t, str) else json.dumps(t)
                out["calls"] += 1; out["chars"] += len(t)
                if not was_edited:
                    out["calls_pre_edit"] += 1; out["chars_pre_edit"] += len(t)
    out["approx_tokens"] = out["chars"] // 4; out["approx_tokens_pre_edit"] = out["chars_pre_edit"] // 4
    return out
base = os.path.expanduser("~/.agent-data/projects/-Users-the-sponsor-apps/3cff917f-aeff-41f8-9753-cac90d63512e/subagents")
for label, aid in (("scout-fed 21/F-01", "ad4958655e084ffd3"), ("no scout 26/F-01", "aea3279f5674b3c87"), ("scout itself (haiku)", "ade7b40107946a2c2")):
    fs = glob.glob(f"{base}/agent-{aid}*.jsonl")
    print(label, fs and measure(fs[0]))
