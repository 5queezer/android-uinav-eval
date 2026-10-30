#!/usr/bin/env python3
"""Turn crawled screens into labelled kev training records, in exactly the requests eval.py sends.

Targets come from the crawl: every page (open), every switch (set, flipped), every "label: value" row (info).
Goals targeting the 30 eval tasks are held out (HOLDOUT). A local LLM writes the user goals (cached in goals.json).
For each goal the path from the home screen gives one record per step: the screen as eval.py builds it for that goal,
the history so far, and labels for done / action (/ answer for info goals). Each record is rendered in one of the two
loop variants eval.py runs: the experiment loop (switch states, no stuck option, scroll_up) or the original one.

usage: build_data.py SCREENS.jsonl OUT_DIR [--goals-per-target 2] [--model gemma4:12b-it-q8_0]
"""
import argparse, copy, json, random, re, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import eval as ev  # noqa: E402

HOLDOUT = re.compile(r"android version|build number|\bmodel\b|battery|security update|kernel|wi.?fi|internet|"
                     r"ip address|screen timeout|time zone|dark theme|airplane|do not disturb|color inversion|"
                     r"extra dim|bold text|24-hour|location|bluetooth|connected devices|high contrast|font size|"
                     r"stopwatch|notification history|all apps|see all", re.I)
# pages where the eval's tasks end (from the successful episodes, plus the unsolved tasks' pages): no target at all
HOLDOUT_PAGES = {"About emulated device", "Android version", "Battery", "Battery Saver", "Bluetooth", "Date & time",
                 "Display size and text", "Do Not Disturb", "Internet", "Network details", "Screen timeout",
                 "Stopwatch", "All apps", "Color and motion", "Location", "Notification history", "Extra dim",
                 "Color inversion", "Notifications"}
OLLAMA = "http://localhost:11434"


def llm(model, prompt):
    body = {"model": model, "think": False, "stream": False, "options": {"temperature": 0.8}, "prompt": prompt}
    req = urllib.request.Request(OLLAMA + "/api/generate", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["response"]


def describe_target(t):
    where = f"the Android settings page \"{t['page']}\" (reached via {' > '.join(t['crumbs'])})"
    if t["kind"] == "open":
        return f"open {where}"
    if t["kind"] == "set":
        return f"turn {'OFF' if t['on'] else 'ON'} the switch \"{t['label']}\" on {where}"
    return f"find out the value shown as \"{t['row']}\" on {where}; the user asks for the {t['label']}"


def flip(layout, base):
    """The layout after tapping the switch named `base`: its CHECKED state toggled (synthetic done screen)."""
    lay = copy.deepcopy(layout)
    hit = []

    def walk(n, row):
        texts = []
        ev.gather(n, texts, set(), [])
        name = ev.own(n) or (texts[0] + (": " + ", ".join(texts[1:]) if texts[1:] else "") if texts else "")
        mine = row or (name[:120] == base)
        if "CHECKABLE" in ev.flags(n) and mine and not hit:
            st = n.setdefault("state", [])
            st.remove("CHECKED") if "CHECKED" in st else st.append("CHECKED")
            hit.append(n)
        for c in n.get("children", []):
            walk(c, mine)

    for w in lay:
        for n in w.get("content", []):
            walk(n, False)
    return lay if hit else None


DIALOGS = {"", "Popup Window", "Pop-Up Window"}  # not pages a user would ask to open


def on_held_out_path(path, screens, by_path):
    """True when a screen on the way to `path` (excluding the home screen and the Settings list) is a held-out page."""
    for d in range(2, len(path)):
        i = by_path.get(json.dumps(path[:d]))
        if i is not None and screens[i]["title"] in HOLDOUT_PAGES:
            return True
    return False


def pages_of(dev_path):
    """The held-out pages of an existing dev.jsonl: the screens its goals finish on (done=True)."""
    return {r["state"]["window_title"] for r in map(json.loads, open(dev_path)) if r["questions"]["done"]["label"]}


def held_pages(tgts, frac, seed=0):
    """The pages kept out of training for kev.benchmark (dev.jsonl); rollout.py must skip them too."""
    rng = random.Random(seed)
    pages = sorted({t["page"] for t in tgts})
    rng.shuffle(pages)
    return set(pages[:max(1, int(len(pages) * frac))])


def targets(screens):
    by_path = {json.dumps(s["path"]): i for i, s in enumerate(screens)}
    out = []
    for i, s in enumerate(screens):
        if not s["path"]:
            continue
        crumbs = [p["base"].split(":")[0] for p in s["path"]]
        page = s["title"]
        if page in HOLDOUT_PAGES or page in DIALOGS or on_held_out_path(s["path"], screens, by_path):
            continue
        if len(s["path"]) >= 2 and not HOLDOUT.search(page + " " + crumbs[-1]):
            out.append({"kind": "open", "screen": i, "page": page, "crumbs": crumbs, "label": page})
        for k, lay in enumerate(s["layouts"]):
            title, cands, rows = ev.parse_layout(lay, "", toggle=True, limit=999)
            for c in cands:
                if c["on"] is not None and c["base"] and c["role"] != "radio button" and \
                        not HOLDOUT.search(c["base"] + " " + page):
                    out.append({"kind": "set", "screen": i, "scroll": k, "page": page, "crumbs": crumbs,
                                "label": c["base"], "on": c["on"]})
            for r in rows if len(s["path"]) >= 2 else []:  # the Settings list's summaries are not values
                if ": " in r and len(r) < 90 and not HOLDOUT.search(r + " " + page) and \
                        not any(c["base"] == r and c["on"] is not None for c in cands):
                    label = r.split(": ")[0]
                    out.append({"kind": "info", "screen": i, "scroll": k, "page": page, "crumbs": crumbs,
                                "label": label, "row": r})
    seen, uniq, per_page = set(), [], {}
    for t in out:  # one target per (kind, label) and page, at most 6 of a kind per page (app lists repeat)
        k, pk = (t["kind"], t["label"], t["page"]), (t["kind"], t["page"])
        if k not in seen and per_page.get(pk, 0) < 6:
            seen.add(k)
            per_page[pk] = per_page.get(pk, 0) + 1
            uniq.append(t)
    return uniq, by_path


def make_goals(tgts, model, n, cache, path):
    for i, t in enumerate(tgts):
        if i % 20 == 0:
            path.write_text(json.dumps(cache, indent=1))
        key = describe_target(t)
        if key in cache:
            continue
        txt = llm(model, f"A phone user asks an assistant for help. Write {n} different short requests (one per line, "
                         f"no numbering, no quotes) a user would type whose answer is: {key}. Do not mention the "
                         f"menu path. Vary the wording; some may be questions.")
        cache[key] = [l.strip(" -•\"'") for l in txt.splitlines() if l.strip()][:n]
        print(f"goal: {key[:90]} -> {cache[key]}", flush=True)
    return cache


class Args:  # what eval.options() reads
    def __init__(self, exp):
        self.scroll_end = self.toggle_state = exp
        self.stuck_option = exp  # True = no stuck choice (the experiment loop)


def records_for(goal, t, screens, by_path, exp, rng):
    """One record per step of the path to target t; exp selects the loop variant."""
    args = Args(exp)
    path = screens[t["screen"]]["path"]
    chain = [screens[by_path[json.dumps(path[:d])]] for d in range(len(path) + 1)]
    steps = [(p["scroll"], p["base"]) for p in path]  # the tap that leaves each ancestor
    final_k = t.get("scroll", 0)
    if t["kind"] == "set":
        steps.append((final_k, t["label"]))
    history, recs, scrolled = [], [], set()
    info = t["kind"] == "info"

    def emit(scr, lay, done, action=None, answer_row=None):
        title, cands, rows = ev.parse_layout(lay, goal, args.toggle_state)
        fixed = ev.options(args, title, scrolled, set())
        if len(cands) + len(fixed) > ev.MAX_OPTIONS:
            cands = ev.parse_layout(lay, goal, args.toggle_state, ev.MAX_OPTIONS - len(fixed))[1]
        answers = rows[:ev.MAX_ANSWERS] if info else []
        state = {"goal": goal, "step": len(history) + 1, "app": scr["app"], "window_title": title,
                 "history": history[-5:],
                 "candidates": [{k: c[k] for k in ("id", "role", "name", "states", "x", "y", "w", "h")} for c in cands]}
        body = ev.request("kev", state, cands, None, answers, fixed)
        body["questions"]["done"]["label"] = done
        chosen = None
        if action is not None:
            if action in ("scroll_down", "scroll_up", "back"):
                body["questions"]["action"]["label"] = action
            else:
                chosen = next((c for c in cands if c["base"] == action), None)
                if not chosen:
                    return None  # the target fell outside the ranked candidates
                body["questions"]["action"]["label"] = chosen["id"]
        else:
            del body["questions"]["action"]
        if info:
            idx = next((j for j, r in enumerate(answers) if r == answer_row), None)
            if idx is None and answer_row is not None:
                return None  # the row is past the answer list's cap: eval would score any answer as wrong
            body["questions"]["answer"]["label"] = f"t{idx + 1}" if idx is not None else "none"
        recs.append({"state": body["state"], "questions": body["questions"]})
        return chosen

    for d, scr in enumerate(chain):
        last = d == len(chain) - 1
        if last and t["kind"] != "set":  # the goal screen: done (info: at the row's scroll position)
            for k in range(final_k):
                emit(scr, scr["layouts"][k], False, "scroll_down", None)
                history.append(f"step {len(history) + 1}: scroll_down (swipe up)")
                scrolled.add(scr["title"])
            emit(scr, scr["layouts"][final_k], True, None, t.get("row"))
            return recs
        k, base = steps[d]
        for j in range(k):
            emit(scr, scr["layouts"][j], False, "scroll_down")
            history.append(f"step {len(history) + 1}: scroll_down (swipe up)")
            scrolled.add(scr["title"])
        chosen = emit(scr, scr["layouts"][k], False, base)
        if chosen is None:
            return recs if len(recs) > 1 else []
        label = f" {chosen['role']} '{chosen['name']}'"
        history.append(f"step {len(history) + 1}: {chosen['id']}{label} (tap)")
        if last:  # set: the screen after the tap, switch flipped
            after = flip(scr["layouts"][k], base)
            if after is None:
                return recs
            if exp:
                effect = "on→off" if t["on"] else "off→on"
                history[-1] = f"step {len(history)}: tapped {chosen['role']} '{base}' ({effect})"
            emit(scr, after, True)
            return recs
        if rng.random() < 0.15:  # a wrong turn: a sibling page whose right action is back
            sib = [s for s in screens if len(s["path"]) == d + 1 and s["path"][:d] == path[:d]
                   and s["path"] != path[:d + 1] and s["title"] not in HOLDOUT_PAGES
                   and not HOLDOUT.search(s["title"] + " " + s["path"][-1]["base"])]
            if sib:
                s2 = rng.choice(sib)
                wrong = s2["path"][-1]
                pc = ev.parse_layout(scr["layouts"][wrong["scroll"]], goal, args.toggle_state)[1]
                c2 = next((c for c in pc if c["base"] == wrong["base"]), None)
                if c2:
                    hist_save = list(history)
                    history[-1] = f"step {len(history)}: {c2['id']} {c2['role']} '{c2['name']}' (tap)"
                    emit(s2, s2["layouts"][0], False, "back")
                    history[:] = hist_save
    return recs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("screens")
    p.add_argument("out")
    p.add_argument("--goals-per-target", type=int, default=2)
    p.add_argument("--model", default="gemma4:12b-it-q8_0")
    p.add_argument("--exp-frac", type=float, default=0.7, help="share of goals rendered in the experiment loop's format")
    p.add_argument("--heldout-frac", type=float, default=0.1)
    p.add_argument("--held-from", help="reuse the held-out pages of this dev.jsonl (comparable dev scores across rounds)")
    a = p.parse_args()
    screens, paths = [], set()
    for line in open(a.screens):  # a resumed crawl writes Home, Settings and the categories again
        s = json.loads(line)
        if (k := json.dumps(s["path"])) not in paths:
            paths.add(k)
            screens.append(s)
    tgts, by_path = targets(screens)
    print(f"{len(screens)} screens, {len(tgts)} targets: " +
          ", ".join(f"{k} {sum(t['kind'] == k for t in tgts)}" for k in ("open", "set", "info")), flush=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cache_path = out / "goals.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    try:
        make_goals(tgts, a.model, a.goals_per_target, cache, cache_path)
    finally:
        cache_path.write_text(json.dumps(cache, indent=1))
    held = pages_of(a.held_from) if a.held_from else held_pages(tgts, a.heldout_frac)  # whole pages, for kev.benchmark
    rng = random.Random(0)
    train, dev = [], []
    for t in tgts:
        for goal in cache.get(describe_target(t), []):
            if HOLDOUT.search(goal):  # the LLM may name a held-out feature (e.g. "high contrast")
                continue
            recs = records_for(goal, t, screens, by_path, rng.random() < a.exp_frac, rng)
            (dev if t["page"] in held else train).extend(recs)
    rng.shuffle(train)
    for name, recs in (("train", train), ("dev", dev)):
        with open(out / f"{name}.jsonl", "w") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"train {len(train)} records, dev {len(dev)} records (held-out pages: {len(held)})")


if __name__ == "__main__":
    main()
