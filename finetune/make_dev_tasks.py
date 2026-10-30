#!/usr/bin/env python3
"""A live dev suite for checkpoint selection: eval.py tasks on the 12 dev pages, which training never sees.

Neither training data nor the 30 test tasks: targets (build_data.targets) whose page is one of dev.jsonl's held-out
pages, with the first cached LLM goal (goals.json) that neither names a held-out feature nor gives the answer away.
Open targets check the window title and package; info targets expect the crawled row's value (the whole row when
the value repeats on the page), echoed on the device (eval.py runs expected_cmd there). eval.py checks neither the
page of an info task nor more than the title of an open one, so a value shown on any other crawled screen, or a title
another screen of the app shares, makes no task: it could finish elsewhere. Set targets are left out:
eval.py checks set tasks with adb settings commands, and arbitrary switches have none.

usage: make_dev_tasks.py [--screens data/screens.jsonl] [--data data/v1] [--out ../tasks-dev.json]
"""
import argparse, collections, json, re, sys
from pathlib import Path

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent))
import eval as ev  # noqa: E402
import build_data as bd  # noqa: E402
import label_onpolicy as lo  # noqa: E402

SAFE = re.compile(r"^[A-Za-z0-9%.:/][A-Za-z0-9 %.:/-]*$")  # passes `adb shell echo` unchanged
TIMELY = re.compile(r"\d:\d\d|\b(ago|past|today|yesterday|seconds?|minutes?|hours?|days?|weeks?|am|pm|"
                    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", re.I)
MAX_INFO = 3  # info tasks per page, so the app lists (Aspect ratio, App languages) do not dominate


def value(t):
    return t["row"][len(t["label"]) + 2:]


def expected(t, s):
    """The row's value, or the whole row when another row of the page shows the same value (an answer naming the
    wrong row would pass)."""
    others = {r for lay in s["layouts"] for r in ev.parse_layout(lay, "")[2] if r != t["row"]}
    return t["row"] if any(ev.contains(r, value(t)) for r in others) else value(t)


def screen_texts(screens):
    """Each screen's rows over all its scroll positions, joined as eval.verify joins them."""
    return ["\n".join(r for lay in s["layouts"] for r in ev.parse_layout(lay, "")[2]) for s in screens]


def usable(t, screens, texts=None):
    """Why target t makes no dev task, or None. Info values must be timeless, shell-safe, among the rows the
    model is offered and on no other crawled screen; open titles unique among the app's screens.
    texts: screen_texts(screens), precomputed."""
    s = screens[t["screen"]]
    if t["kind"] == "set":
        return "set"
    if t["page"].endswith("?"):  # a confirmation dialog, not a page
        return "dialog"
    ancestors = {x["title"] for x in screens if x["path"] == s["path"][:len(x["path"])] and x is not s}
    if t["page"] in ancestors:  # the title check would pass before the page is reached
        return "title on the way"
    if t["kind"] == "open" and sum(x["app"] == s["app"] and x["title"] == t["page"] for x in screens) > 1:
        return "title not unique"
    if t["kind"] == "info":
        if TIMELY.search(value(t)):
            return "time-dependent"
        if not SAFE.match(expected(t, s)):
            return "not shell-safe"
        if t["row"] not in ev.parse_layout(s["layouts"][t["scroll"]], "")[2][:ev.MAX_ANSWERS]:
            return "past the answer cap"
        texts = texts or screen_texts(screens)
        if any(ev.contains(x, expected(t, s)) for i, x in enumerate(texts) if i != t["screen"]):
            return "on another screen"
    return None


def goal_for(t, cache, taken=frozenset()):
    """taken: goals training uses for other targets (the LLM wrote the same goal for Screen saver and its settings)."""
    for g in cache.get(bd.describe_target(t), []):
        if g not in taken and not bd.HOLDOUT.search(g) and not (t["kind"] == "info" and ev.contains(g, value(t))):
            return g
    return None


def task(t, tid, goal, s):
    out = {"id": tid, "kind": t["kind"], "goal": goal, "page": t["page"]}
    if t["kind"] == "open":
        return out | {"package": f"^{re.escape(s['app'])}$", "layout_re": f"^window: {re.escape(t['page'])}$"}
    return out | {"expected_cmd": f"echo {expected(t, s)}", "note": f"crawled row: {t['row']}"}


def make(screens, dev, cache):
    tgts, _ = bd.targets(screens)
    tasks, skipped, n = [], collections.Counter(), collections.Counter()
    taken = {g for t in tgts if t["page"] not in dev for g in cache.get(bd.describe_target(t), [])}
    texts = screen_texts(screens)
    for t in tgts:
        if t["page"] not in dev:
            continue
        why = usable(t, screens, texts) or (None if (goal := goal_for(t, cache, taken)) else "no goal")
        if not why and t["kind"] == "info" and n[t["page"], "info"] >= MAX_INFO:
            why = "info cap"
        if why:
            skipped[why] += 1
            continue
        n[t["page"]] += 1
        n[t["page"], t["kind"]] += 1
        tid = "dev_" + re.sub(r"[^a-z0-9]+", "_", t["page"].lower()).strip("_") + f"_{n[t['page']]}"
        tasks.append(task(t, tid, goal, screens[t["screen"]]))
    return tasks, skipped


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--screens", default=str(here / "data/screens.jsonl"))
    p.add_argument("--data", default=str(here / "data/v1"), help="holds dev.jsonl (the dev pages) and goals.json")
    p.add_argument("--out", default=str(here.parent / "tasks-dev.json"))
    a = p.parse_args()
    data = Path(a.data)
    tasks, skipped = make(lo.load_screens(a.screens), bd.pages_of(data / "dev.jsonl"),
                          json.loads((data / "goals.json").read_text()))
    Path(a.out).write_text("[\n" + ",\n".join(" " + json.dumps(t, ensure_ascii=False) for t in tasks) + "\n]\n")
    print(f"{len(tasks)} tasks -> {a.out}: " +
          ", ".join(f"{k} {sum(t['kind'] == k for t in tasks)}" for k in ("open", "info")))
    for page, c in sorted(collections.Counter(t["page"] for t in tasks).items()):
        kinds = collections.Counter(t["kind"] for t in tasks if t["page"] == page)
        print(f"  {page}: {c} ({', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))})")
    print("skipped: " + ", ".join(f"{k} {v}" for k, v in skipped.most_common()))


if __name__ == "__main__":
    main()
