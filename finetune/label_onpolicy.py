#!/usr/bin/env python3
"""Label on-policy rollout states (rollout.py) with the right action, from the crawl graph.

Each recorded screen is matched to a crawled screen (same title, best overlap of control names). On the target's path
the label is the path's next step: tap it when it is visible, otherwise scroll toward its scroll position. Off the path
(a wrong page, an unknown screen, a popup) the label is back. On the target page: open goals are done; info goals are
done with the row as the answer once it is visible; set goals tap the switch, and are done once it was flipped.

usage: label_onpolicy.py data/onpolicy.jsonl data/v2/onpolicy-train.jsonl
"""
import argparse, collections, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import eval as ev  # noqa: E402
import build_data as bd  # noqa: E402


def load_screens(path):
    screens, paths = [], set()
    for line in open(path):
        s = json.loads(line)
        if (k := json.dumps(s["path"])) not in paths:
            paths.add(k)
            s["bases"] = [{c["base"] for c in ev.parse_layout(l, "", toggle=True, limit=999)[1]} for l in s["layouts"]]
            screens.append(s)
    return screens


def match(title, bases, screens):
    """-> (screen, scroll index) of the crawled screen this one is, or (None, None)."""
    best, score = (None, None), 0.0
    for s in screens:
        if s["title"] != title:
            continue
        for k, b in enumerate(s["bases"]):
            j = len(bases & b) / max(1, len(bases | b))
            if j > score:
                best, score = (s, k), j
    return best if score >= 0.5 else (None, None)


def label(rec, screens):
    t, st = rec["target"], rec["body"]["state"]
    bases = {c["base"] for c in rec["cands"]}
    ids = {c["base"]: c["id"] for c in rec["cands"]}
    scr, k = match(st["window_title"], bases, screens)
    target_path = screens[t["screen"]]["path"]
    q = rec["body"]["questions"]
    out = {"state": st, "questions": {name: dict(v) for name, v in q.items()}}
    lab = out["questions"]

    def act(a):
        lab["done"]["label"] = False
        lab["action"]["label"] = a
        if "answer" in lab:
            lab["answer"]["label"] = "none"
        return out

    if scr is None:
        # an unknown page: a popup or another app is a wrong turn, but an uncrawled Settings page may be exactly where
        # a held-out goal ends, and labelling it back teaches "unfamiliar page -> leave" (round 2 did that). Skip it.
        if st["app"] == screens[t["screen"]]["app"] and st["window_title"] not in ("", "Popup Window"):
            return None
        return act("back") if "back" in q["action"]["criteria"] else None
    path = scr["path"]
    if scr["title"] in bd.HOLDOUT_PAGES or bd.HOLDOUT.search(scr["title"]):
        return None  # a held-out page: no label at all (round 2 taught "back" on the eval's own pages)
    on_path = path == target_path[:len(path)]
    # a later step of the path already visible here (a tab bar, a shortcut row): take it directly; crawl paths are
    # depth-first, so some take a detour (Clock > Alarm > ... > Timer while the Timer tab is on the first screen)
    later = target_path[len(path) + 1:] if on_path else target_path[1:]
    for step in reversed(later):
        if step["base"] in ids:
            return act(ids[step["base"]])
    if path == target_path:  # on the target page
        want_k = t.get("scroll", 0)
        if t["kind"] == "open":
            lab["done"]["label"] = True
            lab.pop("action", None)
            return out
        if t["kind"] == "info":
            row = next((i for i, a in enumerate(rec["answers"]) if a == t["row"]), None)
            if row is not None:
                lab["done"]["label"] = True
                lab["answer"]["label"] = f"t{row + 1}"
                lab.pop("action", None)
                return out
        if t["kind"] == "set":
            if t["label"] in rec["flipped"]:
                lab["done"]["label"] = True
                lab.pop("action", None)
                return out
            if t["label"] in ids:
                return act(ids[t["label"]])
        if want_k > k and "scroll_down" in q["action"]["criteria"]:
            return act("scroll_down")
        if want_k < k and "scroll_up" in q["action"]["criteria"]:
            return act("scroll_up")
        return None
    if on_path:  # an ancestor: the next step of the path
        step = target_path[len(path)]
        if step["base"] in ids:
            return act(ids[step["base"]])
        if step["scroll"] > k and "scroll_down" in q["action"]["criteria"]:
            return act("scroll_down")
        if step["scroll"] < k and "scroll_up" in q["action"]["criteria"]:
            return act("scroll_up")
        return None
    return act("back")  # a wrong turn


def main():
    p = argparse.ArgumentParser()
    p.add_argument("rollouts")
    p.add_argument("out")
    p.add_argument("--screens", default=str(Path(__file__).parent / "data/screens.jsonl"))
    p.add_argument("--skip-pages-of", help="drop rollouts whose goal is on a page of this dev.jsonl")
    a = p.parse_args()
    screens = load_screens(a.screens)
    # targets refer to screens by index in build_data's deduplicated order, which load_screens reproduces
    stats, recs = collections.Counter(), []
    held = bd.pages_of(a.skip_pages_of) if a.skip_pages_of else set()
    for line in open(a.rollouts):
        r = json.loads(line)
        if r["target"]["page"] in held or bd.HOLDOUT.search(r["goal"]):
            stats["dev page or held-out goal"] += 1
            continue
        out = label(r, screens)
        if out is None:
            stats["unlabelled"] += 1
            continue
        lab = out["questions"]
        kind = "done" if lab["done"]["label"] else (
            "back" if lab["action"]["label"] == "back" else "scroll" if "scroll" in lab["action"]["label"] else "tap")
        stats[kind] += 1
        recs.append(out)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(recs)} labelled records: {dict(stats)}")


if __name__ == "__main__":
    main()
