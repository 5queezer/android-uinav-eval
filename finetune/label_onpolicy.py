#!/usr/bin/env python3
"""Label on-policy rollout states (rollout.py) with the right action, from the crawl graph.

Each recorded screen is matched to a crawled screen (same title, best overlap of control names; of equally good
matches, the first, or with --labels distance the one nearest the target). On the target page, whatever the history:
open goals are done; info goals are done with the row as the answer once it is visible; set goals tap the switch, and
are done once it was flipped (under any name of that switch: a row and its own switch are both recorded). Held-out
pages get no label. Elsewhere:

--labels path (the default, rounds 1-3): on the target's path the next step, or a later one when visible, is tapped;
otherwise a scroll toward its scroll position. Off the path (a wrong page) the label is back.

--labels distance (an ablation): the crawl is a tree (a screen's parent is its path minus the last step, where the
back key returns to), and the label is the offered action that leaves the fewest taps and scrolls to the target: the
path's next step or a later one when visible, a scroll toward the needed scroll position, or back, which is labelled
only when it strictly shortens the way and no visible tap does better. When no offered action shortens it, the state
stays unlabelled. The target page is never left with back.

In both, unknown screens (a popup, another app) are labelled back unless they could be an uncrawled page.

--swap N adds, per recorded state, up to N copies relabelled for other training targets whose path passes through the
same screen: the request is rebuilt for that target's goal, the recorded history kept. Then the window alone no
longer tells the model to leave. A copy is dropped when its history names a candidate id (c5) that the new goal might
number differently on that earlier screen. Targets on the dev pages (--skip-pages-of, by default data/v1/dev.jsonl;
"" for none) are never drawn.

usage: label_onpolicy.py data/onpolicy.jsonl data/v2/onpolicy-train.jsonl [--swap 2] [--labels distance]
       [--skip-pages-of data/v1/dev.jsonl]
"""
import argparse, builtins, collections, json, random, re, sys
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


def remaining(path, k, t, tpath):
    """Taps, scrolls and backs from the screen at `path`, scroll position k, to the end of target t (path tpath): up
    the crawl tree to the lowest common ancestor (back returns to the scroll position the tap was made at), then down
    the target's path, then to the row or switch on the target page and the switch's tap."""
    n = 0
    while path != tpath[:len(path)]:
        path, k, n = path[:-1], path[-1]["scroll"], n + 1
    for step in tpath[len(path):]:
        n += abs(step["scroll"] - k) + 1
        k = 0  # a page opens at the top
    return n if t["kind"] == "open" else n + abs(t.get("scroll", 0) - k) + (t["kind"] == "set")


def match(title, bases, screens, target=None):
    """-> (screen, scroll index) of the crawled screen this one is, or (None, None). A page crawled under two paths
    matches both equally; then the one nearest to `target` wins."""
    best, key = (None, None), None
    for s in screens:
        if s["title"] != title:
            continue
        for k, b in enumerate(s["bases"]):
            j = len(bases & b) / max(1, len(bases | b))
            kk = (-j, remaining(s["path"], k, target, screens[target["screen"]]["path"]) if target else 0)
            if j >= 0.5 and (key is None or kk < key):
                best, key = (s, k), kk
    return best


def switch(layout, base):
    """Where the checkable that bd.flip(layout, base) toggles sits: (window, index, ...) or None."""
    def walk(n, at, row):
        texts = []
        ev.gather(n, texts, set(), [])
        name = ev.own(n) or (texts[0] + (": " + ", ".join(texts[1:]) if texts[1:] else "") if texts else "")
        mine = row or name[:120] == base
        if "CHECKABLE" in ev.flags(n) and mine:
            return at
        for i, c in enumerate(n.get("children", [])):
            if (hit := walk(c, at + (i,), mine)) is not None:
                return hit

    for w, win in enumerate(layout):
        for i, n in enumerate(win.get("content", [])):
            if (hit := walk(n, (w, i), False)) is not None:
                return hit


def switched(t, flipped, screens):
    """True when the episode flipped set target t's switch, under its label or another name of the same switch (the row
    around it with or without its summary, the switch itself) on any crawled layout of the target page."""
    return t["label"] in flipped or any(
        (n := switch(lay, t["label"])) is not None and any(switch(lay, b) == n for b in flipped)
        for lay in screens[t["screen"]]["layouts"])


def parse(lay, goal, limit=ev.MAX_CANDIDATES):
    """ev.parse_layout(lay, goal, True, limit) with text rows at the same position in layout order: parse_layout breaks
    those ties by id(n), a memory address, so the answers (and an info label) would change from run to run."""
    first = {}
    ev.id = lambda n: first.setdefault(builtins.id(n), len(first))  # shadows the builtin in eval.py's globals only
    try:
        return ev.parse_layout(lay, goal, True, limit)
    finally:
        del ev.id


def goal_free(rec):
    """True when the recorded request's candidate ids do not depend on its goal: none was ranked out (fewer than the
    limit) and no two share a position (parse_layout numbers by position; a tie keeps the goal's ranking)."""
    cands = rec["body"]["state"]["candidates"]
    limit = min(ev.MAX_CANDIDATES, ev.MAX_OPTIONS - (len(rec["body"]["questions"]["action"]["criteria"]) - len(cands)))
    return len(cands) < limit and len({(c["x"], c["y"]) for c in cands}) == len(cands)


def label(rec, screens, labels="path"):
    t, st = rec["target"], rec["body"]["state"]
    bases = {c["base"] for c in rec["cands"]}
    ids = {c["base"]: c["id"] for c in rec["cands"]}
    scr, k = match(st["window_title"], bases, screens, t if labels == "distance" else None)  # path: as before v4
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

    def done():
        lab["done"]["label"] = True
        lab.pop("action", None)
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
    on_target = path == target_path  # whatever the history: wrong turns, scrolls, another way in
    if on_target and t["kind"] == "open":
        return done()
    if on_target and t["kind"] == "info":
        row = next((i for i, a in enumerate(rec["answers"]) if a == t["row"]), None)
        if row is not None:
            lab["answer"]["label"] = f"t{row + 1}"
            return done()
    if on_target and t["kind"] == "set" and switched(t, rec["flipped"], screens):
        return done()
    on_path = path == target_path[:len(path)]
    crit = q["action"]["criteria"]
    if labels == "path":
        # a later step of the path already visible here (a tab bar, a shortcut row): take it directly; crawl paths are
        # depth-first, so some take a detour (Clock > Alarm > ... > Timer while the Timer tab is on the first screen)
        for step in reversed(target_path[len(path) + 1:] if on_path else target_path[1:]):
            if step["base"] in ids:
                return act(ids[step["base"]])
        if on_target:
            if t["kind"] == "set" and t["label"] in ids:
                return act(ids[t["label"]])
            want_k = t.get("scroll", 0)
        elif on_path:  # an ancestor: the next step of the path
            step = target_path[len(path)]
            if step["base"] in ids:
                return act(ids[step["base"]])
            want_k = step["scroll"]
        else:
            return act("back")  # a wrong turn
        if want_k > k and "scroll_down" in crit:
            return act("scroll_down")
        if want_k < k and "scroll_up" in crit:
            return act("scroll_up")
        return None
    # moves: (taps and scrolls left after the action, preference on a tie: tap, scroll, back, action).
    # The next step, or a later step of the path already visible here (a tab bar, a shortcut row); crawl paths are
    # depth-first, so some take a detour (Clock > Alarm > ... > Timer while the Timer tab is on the first screen)
    moves = [(remaining(target_path[:j + 1], 0, t, target_path), 0, ids[step["base"]])
             for j, step in enumerate(target_path) if j >= (len(path) if on_path else 1) and step["base"] in ids]
    if on_target and t["kind"] == "set" and t["label"] in ids:
        moves.append((0, 0, ids[t["label"]]))
    moves += [(remaining(path, k + d, t, target_path), 1, a) for a, d in (("scroll_down", 1), ("scroll_up", -1))
              if a in crit]
    if "back" in crit and path and not on_target:
        moves.append((remaining(path[:-1], path[-1]["scroll"], t, target_path), 2, "back"))
    best = min(moves, default=None)
    if best is None or best[0] >= remaining(path, k, t, target_path):
        return None  # nothing offered gets closer (the step fell outside the ranked candidates, or is not crawled)
    return act(best[2])


def relabel_for(rec, target, goal, screens, labels="path", earlier=None):
    """The recorded state relabelled for another target and goal: the request is rebuilt from the matched crawled
    layout (with the episode's switch flips) for the new goal, so candidates are ranked and numbered as eval.py would
    send them; the recorded step, history and fixed options are kept. None when the state gets no label, or when a
    history line names a candidate id (eval.py's tap lines always do) on an earlier screen whose ids could depend on
    the goal: `earlier` maps the episode's steps to their records; without it every such line drops the copy."""
    st = rec["body"]["state"]
    for line in st["history"]:
        m = re.match(r"step (\d+): c\d+ ", line)
        if m and not (earlier and int(m[1]) in earlier and goal_free(earlier[int(m[1])])):
            return None
    scr, k = match(st["window_title"], {c["base"] for c in rec["cands"]}, screens,
                   target if labels == "distance" else None)
    if scr is None:
        return None
    lay = scr["layouts"][k]
    for b in {switch(lay, b): b for b in sorted(rec["flipped"])}.values():  # each switch once, under whichever name
        lay = bd.flip(lay, b) or lay
    fixed = {n: d for n, d in ev.FIXED.items() if n in rec["body"]["questions"]["action"]["criteria"]}
    title, cands, rows = parse(lay, goal)
    if len(cands) + len(fixed) > ev.MAX_OPTIONS:
        cands = ev.parse_layout(lay, goal, True, ev.MAX_OPTIONS - len(fixed))[1]
    answers = rows[:ev.MAX_ANSWERS] if target["kind"] == "info" else []
    state = st | {"goal": goal, "window_title": title,
                  "candidates": [{f: c[f] for f in ("id", "role", "name", "states", "x", "y", "w", "h")} for c in cands]}
    body = ev.request("kev", state, cands, None, answers, fixed)
    return label({"target": target, "goal": goal, "body": body, "answers": answers, "flipped": rec["flipped"],
                  "cands": [{f: c[f] for f in ("id", "base", "name", "on")} for c in cands]}, screens, labels)


def kind(out):
    if out is None:
        return "unlabelled"
    lab = out["questions"]
    return "done" if lab["done"]["label"] else (
        "back" if lab["action"]["label"] == "back" else "scroll" if "scroll" in lab["action"]["label"] else "tap")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("rollouts")
    p.add_argument("out")
    p.add_argument("--screens", default=str(Path(__file__).parent / "data/screens.jsonl"))
    p.add_argument("--skip-pages-of", default=str(Path(__file__).parent / "data/v1/dev.jsonl"),
                   help="drop rollouts whose goal is on a page of this dev.jsonl, never swap to them (\"\" for none)")
    p.add_argument("--labels", choices=("path", "distance"), default="path", help="the oracle (module docstring)")
    p.add_argument("--swap", type=int, default=0, help="per state, up to this many copies for other training targets")
    p.add_argument("--goals", default=str(Path(__file__).parent / "data/v1/goals.json"), help="goal cache for --swap")
    a = p.parse_args()
    screens = load_screens(a.screens)
    # targets refer to screens by index in build_data's deduplicated order, which load_screens reproduces
    stats, recs = collections.Counter(), []
    held = bd.pages_of(a.skip_pages_of) if a.skip_pages_of else set()
    swaps = []  # (training target, its goals) for --swap, held out as the rollouts are
    if a.swap:
        cache = json.loads(Path(a.goals).read_text())
        for t in bd.targets(screens)[0]:
            goals = [g for g in cache.get(bd.describe_target(t), []) if not bd.HOLDOUT.search(g)]
            if t["page"] not in held and goals:
                swaps.append((t, goals))
    rng = random.Random(0)
    earlier = {}  # the current episode's records by step, for --swap's history check
    for line in open(a.rollouts):
        r = json.loads(line)
        step = r["body"]["state"]["step"]
        earlier = {n: e for n, e in earlier.items() if n < step and e["goal"] == r["goal"]} | {step: r}
        if r["target"]["page"] in held or bd.HOLDOUT.search(r["goal"]):
            stats["dev page or held-out goal"] += 1
            continue
        outs = [("", label(r, screens, a.labels))]
        scr = match(r["body"]["state"]["window_title"], {c["base"] for c in r["cands"]}, screens)[0] if a.swap else None
        if scr is not None:
            n = len(scr["path"])
            pool = [(t, g) for t, g in swaps if t != r["target"] and screens[t["screen"]]["path"][:n] == scr["path"]]
            outs += [("swap ", relabel_for(r, t, rng.choice(g), screens, a.labels, earlier))
                     for t, g in rng.sample(pool, min(a.swap, len(pool)))]
        for prefix, out in outs:
            if out is not None and out["state"]["window_title"] in held:  # a wrong turn into a dev page
                stats[prefix + "on a dev page"] += 1
                continue
            stats[prefix + kind(out)] += 1
            if out is not None:
                recs.append(out)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(recs)} labelled records: {dict(stats)}")


if __name__ == "__main__":
    main()
