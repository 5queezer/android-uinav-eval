#!/usr/bin/env python3
"""Success per task for several result files side by side (last record per task and run wins, as in report.py).

usage: compare.py --tasks ../tasks.json [--metrics] NAME=results-dir/model.jsonl [NAME=...]
"""
import argparse, json
from collections import Counter, defaultdict


def latest(path):
    last = {}
    for line in open(path):
        r = json.loads(line)
        last[(r["task"], r["run"])] = r
    return last


def load(path):
    ok, runs = defaultdict(int), defaultdict(int)
    for (task, _), r in latest(path).items():
        runs[task] += 1
        ok[task] += r["outcome"] == "success"
    return ok, runs


def metrics(recs, kinds=None):
    """Episode counts for checkpoint selection. A reached episode that did not succeed (wrong_answer aside) "left"
    if a logged step after reaching is off the goal, else it "did not stop" (stayed but never declared done); a
    max_steps or stuck episode whose last logged step is on the goal did not stop either. first_reached_step can
    come from an observation eval.episode never logs (the final one after max_steps, or the repeat-stuck one);
    reached only there counts as "reached at the end". `kinds` maps a task id to its kind: set tasks are left out of
    these three, since their reached is device state, not the page."""
    m = Counter(n=len(recs))
    for r in recs:
        m[r["outcome"]] += 1
        first = r.get("first_reached_step")
        if first is None:
            continue
        m["reached"] += 1
        if r["outcome"] in ("success", "wrong_answer") or (kinds or {}).get(r.get("task")) == "set":
            continue
        log = r["step_log"]
        if not log or first > log[-1]["step"]:
            m["reached_end"] += 1
        elif r["outcome"] in ("max_steps", "stuck") and log[-1]["reached"]:
            m["no_stop"] += 1
        else:
            m["left" if any(not s["reached"] for s in log if s["step"] > first) else "no_stop"] += 1
    return m


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", required=True)
    p.add_argument("--metrics", action="store_true", help="also print episode-level diagnostics per file")
    p.add_argument("cols", nargs="+")
    a = p.parse_args()
    spec = json.load(open(a.tasks))
    tasks = [t["id"] for t in spec]
    kinds = {t["id"]: t["kind"] for t in spec}
    cols = [(c.split("=", 1)[0], load(c.split("=", 1)[1])) for c in a.cols]
    print("| task | " + " | ".join(n for n, _ in cols) + " |")
    print("|---|" + "---|" * len(cols))
    for t in tasks:
        print(f"| {t} | " + " | ".join(f"{ok[t]}/{runs[t]}" if runs[t] else "-" for _, (ok, runs) in cols) + " |")
    solved = [sum(1 for t in tasks if ok[t]) for _, (ok, _) in cols]
    rate = [sum(ok[t] for t in tasks) / max(1, sum(runs[t] for t in tasks)) for _, (ok, runs) in cols]
    print("| **tasks solved** | " + " | ".join(f"**{s}/{len(tasks)}**" for s in solved) + " |")
    print("| **success rate** | " + " | ".join(f"**{r:.0%}**" for r in rate) + " |")
    if a.metrics:
        pct = lambda n, d: f"{n / d:.0%}" if d else "-"
        print("\n| name | n | success | reached | success / reached | left after reaching (open/info) "
              "| did not stop (open/info) | reached at the end (open/info) | wrong_answer | false_done |\n"
              + "|---" * 10 + "|")
        for c in a.cols:
            name, path = c.split("=", 1)
            m = metrics([r for (t, _), r in latest(path).items() if t in kinds], kinds)
            print(f"| {name} | {m['n']} | {pct(m['success'], m['n'])} | {pct(m['reached'], m['n'])} "
                  f"| {pct(m['success'], m['reached'])} | {m['left']} | {m['no_stop']} | {m['reached_end']} "
                  f"| {pct(m['wrong_answer'], m['n'])} | {pct(m['false_done'], m['n'])} |")


if __name__ == "__main__":
    main()
