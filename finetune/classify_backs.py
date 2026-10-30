#!/usr/bin/env python3
"""Classify the model's back presses in on-policy rollouts (rollout.py) with the crawl graph, so later data builds can
upweight the corrections for the states where back cost the model its goal.

A recorded state is a back when the next record of the episode logs "step N: back (back key)" for it. rollout.py does
not record the action of an episode's last state, so a back that ended an episode (the third visit of a screen, the step
limit) cannot be seen. Each back state is matched to a crawled screen as label_onpolicy.py does (of equally good
matches, the one nearest the target) and classed:

- left_goal: the state was the target page, showed the info goal's row, or the episode had flipped the target switch
- progress_loss: the state was on the target's path (an ancestor of the target page), so back climbs away from it
- recovery: the state was off the path, so back climbs toward the common ancestor, one step closer
- unmatched: no crawled screen matches (a popup, another app, an uncrawled page)

usage: classify_backs.py data/onpolicy.jsonl backs.jsonl [--screens data/screens.jsonl]
"""
import argparse, collections, json
from pathlib import Path

import label_onpolicy as lo


def backs(recs):
    """The recorded states where the model chose back, from records in rollout order."""
    for r, nxt in zip(recs, recs[1:]):
        if nxt["goal"] == r["goal"] and \
                nxt["body"]["state"]["history"][-1:] == [f"step {r['body']['state']['step']}: back (back key)"]:
            yield r


def classify(rec, screens):
    t, st = rec["target"], rec["body"]["state"]
    scr, _ = lo.match(st["window_title"], {c["base"] for c in rec["cands"]}, screens, t)
    tpath = screens[t["screen"]]["path"]
    if (scr is not None and scr["path"] == tpath) or (t["kind"] == "info" and t["row"] in rec["answers"]) or \
            (t["kind"] == "set" and lo.switched(t, rec["flipped"], screens)):
        return "left_goal"
    if scr is None:
        return "unmatched"
    return "progress_loss" if scr["path"] == tpath[:len(scr["path"])] else "recovery"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("rollouts")
    p.add_argument("out", help="the back states, each with its class under 'back'")
    p.add_argument("--screens", default=str(Path(__file__).parent / "data/screens.jsonl"))
    a = p.parse_args()
    screens = lo.load_screens(a.screens)
    with open(a.rollouts) as f:
        recs = [json.loads(line) for line in f]
    total, per_page, out = collections.Counter(), collections.defaultdict(collections.Counter), []
    for r in backs(recs):
        cls = classify(r, screens)
        total[cls] += 1
        per_page[r["target"]["page"]][cls] += 1
        out.append(r | {"back": cls})
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(out)} backs in {len(recs)} states: {dict(total)}")
    for page, c in sorted(per_page.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"  {page[:40]:40} {dict(c)}")


if __name__ == "__main__":
    main()
