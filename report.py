#!/usr/bin/env python3
"""Turn eval.py's results/*.jsonl into a markdown report on stdout.

usage: report.py [results_dir] [--floors 0.25,0.4,0.5,0.6] > report.md
"""
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

OUTCOMES = ["success", "false_done", "wrong_answer", "uncertain", "stuck", "unsafe_blocked", "max_steps", "error"]


def pct(n, d):
    return f"{100 * n / d:.0f}%" if d else "-"


def at_floor(r, f):
    """Outcome had the run used floor f (>= its own): the gate checks done first, then confidence."""
    if f < r.get("floor", 0.6):
        return None
    for s in r["step_log"]:
        if s["done"] >= 0.8:
            return r["outcome"]
        if s["conf"] < f:
            return "uncertain"
    return r["outcome"]


def pattern(r):
    """Outcome, where it ended and what the model last wanted to do."""
    if r["outcome"] == "error":
        return f"error: {r.get('error', '')[:80]}"
    s = r["step_log"][-1]
    what = s["chosen"].rsplit(" at (", 1)[0] if s["chosen"] else s["action"]
    why = " (repeat)" if r.get("stuck_reason") == "repeat" else " (anti-undo)" if r.get("anti_undo") else ""
    return f"{r['outcome']}{why} @ '{s['window']}' ({what})"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("results", nargs="?", default=str(Path(__file__).parent / "results"))
    p.add_argument("--floors", default="0.25,0.4,0.5,0.6", help="floors to re-score the episodes at")
    args = p.parse_args()
    last = {}  # a resumed run appends a retry after an error; the last record per episode wins
    for f in sorted(Path(args.results).glob("*.jsonl")):
        for r in map(json.loads, filter(None, f.read_text().splitlines())):
            last[r["model"], r["task"], r["run"]] = r
    recs = list(last.values())
    by_model = defaultdict(list)
    for r in recs:
        by_model[r["model"]].append(r)
    floors = sorted({r.get("floor", 0.6) for r in recs})
    out = [f"# Android navigation eval: {len(recs)} episodes, {len(by_model)} models, run floor "
           + ", ".join(map(str, floors)), "", "## Per model (at the run floor)", "",
           "| model | n | success | reached | false_done | mean steps (success) | median model ms | "
           + " | ".join(OUTCOMES) + " |", "|---" * (7 + len(OUTCOMES)) + "|"]
    for m, rs in by_model.items():
        c = Counter(r["outcome"] for r in rs)
        ok = [r["steps"] for r in rs if r["outcome"] == "success"]
        lat = [s["ms"]["model"] for r in rs for s in r["step_log"]]
        out.append(f"| {m} | {len(rs)} | {pct(c['success'], len(rs))} | {pct(sum(r['reached'] for r in rs), len(rs))} "
                   f"| {pct(c['false_done'], len(rs))} | {f'{mean(ok):.1f}' if ok else '-'} "
                   f"| {f'{median(lat):.0f}' if lat else '-'} | " + " | ".join(str(c[o]) for o in OUTCOMES) + " |")

    fl = [float(x) for x in args.floors.split(",")]
    out += ["", "## Success at other floors (re-scored from the recorded steps; - = below the run floor)", "",
            "| model | " + " | ".join(f"floor {f}" for f in fl) + " |", "|---" * (len(fl) + 1) + "|"]
    for m, rs in by_model.items():
        cells = []
        for f in fl:
            got = [at_floor(r, f) for r in rs]
            cells.append("-" if None in got else pct(got.count("success"), len(got)))
        out.append(f"| {m} | " + " | ".join(cells) + " |")

    out += ["", "## Median time per step (ms; settle after each action comes on top)", "",
            "| model | steps | layout | screenshot | model | act | verify | mean s / episode |", "|---" * 8 + "|"]
    for m, rs in by_model.items():
        steps = [s["ms"] for r in rs for s in r["step_log"]]
        med = lambda k: f"{median(v):.0f}" if (v := [s[k] for s in steps if k in s]) else "-"
        out.append(f"| {m} | {len(steps)} | {med('layout')} | {med('shot')} | {med('model')} | {med('act')} "
                   f"| {med('verify')} | {mean(r.get('secs', 0) for r in rs):.1f} |")

    tasks = list(dict.fromkeys(r["task"] for r in recs))
    models = list(by_model)
    out += ["", "## Success by task (successes / runs)", "", "| task | " + " | ".join(models) + " |",
            "|---" * (len(models) + 1) + "|"]
    for t in tasks:
        cells = []
        for m in models:
            rs = [r for r in by_model[m] if r["task"] == t]
            cells.append(f"{sum(r['outcome'] == 'success' for r in rs)}/{len(rs)}" if rs else "")
        out.append(f"| {t} | " + " | ".join(cells) + " |")

    fails = defaultdict(Counter)
    for r in recs:
        if r["outcome"] != "success":
            fails[pattern(r)][r["model"]] += 1
    out += ["", "## Most common failure patterns", "", "| count | pattern | models |", "|---|---|---|"]
    for p, c in sorted(fails.items(), key=lambda kv: -sum(kv[1].values()))[:15]:
        out.append(f"| {sum(c.values())} | {p} | " + ", ".join(f"{m} {n}" for m, n in c.most_common()) + " |")
    print("\n".join(out))


if __name__ == "__main__":
    main()
