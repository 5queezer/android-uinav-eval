#!/usr/bin/env python3
"""Summarise dicio_eval.py results: success and false actions per variant and category, latency, and a
task matrix. usage: dicio/report.py [results-dicio] [--tasks] [--lang de|en]"""
import argparse, json, statistics
from collections import defaultdict
from pathlib import Path

CATS = ["skill", "routing", "action", "knowledge", "in_app", "safety", "multi"]


def latest(path):
    last = {}
    for line in path.open():
        r = json.loads(line)
        last[(r["task"], r["run"])] = r
    return list(last.values())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dir", nargs="?", default="results-dicio")
    p.add_argument("--tasks", action="store_true", help="also print the per-task matrix")
    p.add_argument("--lang")
    a = p.parse_args()
    runs = {f.stem: [r for r in latest(f) if not a.lang or r["lang"] == a.lang]
            for f in sorted(Path(a.dir).glob("*.jsonl"))}
    pct = lambda n, d: f"{n / d:.0%}" if d else "-"
    print("| variant | n | success | " + " | ".join(CATS) + " | false action | median s | p90 s |")
    print("|---" * (len(CATS) + 6) + "|")
    for name, rs in runs.items():
        by = defaultdict(list)
        for r in rs:
            by[r["cat"]].append(r)
        ok = lambda xs: sum(r["outcome"] == "success" for r in xs)
        secs = sorted(r["secs"] for r in rs)
        cells = [f"{ok(by[c])}/{len(by[c])}" if by[c] else "-" for c in CATS]
        print(f"| {name} | {len(rs)} | {pct(ok(rs), len(rs))} | " + " | ".join(cells)
              + f" | {sum(r['outcome'] == 'false_action' for r in rs)} | {statistics.median(secs):.1f}"
              + f" | {secs[int(0.9 * (len(secs) - 1))]:.1f} |")
    if a.tasks:
        names = list(runs)
        tasks = sorted({r["task"] for rs in runs.values() for r in rs},
                       key=lambda t: (CATS.index(next(r["cat"] for rs in runs.values() for r in rs if r["task"] == t)), t))
        mark = {"success": "✓", "fail": "·", "false_action": "✗"}
        print("\n| task | " + " | ".join(names) + " |\n|---" + "|---" * len(names) + "|")
        for t in tasks:
            cells = []
            for n in names:
                rs = [r for r in runs[n] if r["task"] == t]
                cells.append("".join(mark[r["outcome"]] for r in rs) or "-")
            print(f"| {t} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
