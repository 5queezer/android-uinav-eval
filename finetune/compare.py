#!/usr/bin/env python3
"""Success per task for several result files side by side (last record per task and run wins, as in report.py).

usage: compare.py --tasks ../tasks.json NAME=results-dir/model.jsonl [NAME=...]
"""
import argparse, json
from collections import defaultdict


def load(path):
    last = {}
    for line in open(path):
        r = json.loads(line)
        last[(r["task"], r["run"])] = r
    ok, runs = defaultdict(int), defaultdict(int)
    for (task, _), r in last.items():
        runs[task] += 1
        ok[task] += r["outcome"] == "success"
    return ok, runs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", required=True)
    p.add_argument("cols", nargs="+")
    a = p.parse_args()
    tasks = [t["id"] for t in json.load(open(a.tasks))]
    cols = [(c.split("=", 1)[0], load(c.split("=", 1)[1])) for c in a.cols]
    print("| task | " + " | ".join(n for n, _ in cols) + " |")
    print("|---|" + "---|" * len(cols))
    for t in tasks:
        print(f"| {t} | " + " | ".join(f"{ok[t]}/{runs[t]}" if runs[t] else "-" for _, (ok, runs) in cols) + " |")
    solved = [sum(1 for t in tasks if ok[t]) for _, (ok, _) in cols]
    rate = [sum(ok[t] for t in tasks) / max(1, sum(runs[t] for t in tasks)) for _, (ok, runs) in cols]
    print("| **tasks solved** | " + " | ".join(f"**{s}/{len(tasks)}**" for s in solved) + " |")
    print("| **success rate** | " + " | ".join(f"**{r:.0%}**" for r in rate) + " |")


if __name__ == "__main__":
    main()
