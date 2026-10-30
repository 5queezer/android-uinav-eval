#!/usr/bin/env python3
"""Crawl the emulator's Settings and Clock screens from the eval's start snapshot and save every screen's raw layout.

Depth-first with the back key; switches, radio buttons and anything risky are recorded but never tapped, so the
device state stays the snapshot's. Each screen is captured at every scroll position. Output: one JSON line per
screen with its path from the home screen (the taps and scrolls that reach it) and the raw layouts.

usage: crawl.py OUT.jsonl [--max-depth 4] [--max-screens 400]
"""
import argparse, json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import eval as ev  # noqa: E402
from build_data import HOLDOUT  # noqa: E402

SKIP = re.compile(r"reset|erase|sign in|add account|emergency|sos|developer|clear|force stop|disable|search|"
                  r"feedback|tips|help|google|backup|update|wallpaper|share|more options|navigate up|vpn|^add |^edit |rename|keyboard", re.I)
HOME_APPS = {"Settings", "Clock"}
SETTLE = 0.8


def capture():
    try:
        lay = ev.layout()
    except RuntimeError:  # android layout can fail on some screens (an open keyboard): a dead end
        return [], "?", []
    try:
        title, cands, rows = ev.parse_layout(lay, "", toggle=True, limit=999)
    except (KeyError, ValueError):  # a node eval.py cannot read (no class): treat the screen as a dead end
        return lay, "?", []
    return lay, title, cands


def screen_key(title, cands):
    return title, tuple(sorted(c["base"] for c in cands))[:12]


def tappable(c, depth):
    if depth == 0:
        return c["base"] in HOME_APPS and (not ev_args.only or re.search(ev_args.only, c["base"]) or c["base"] == "Settings")
    if depth >= 2 and HOLDOUT.search(c["base"]):  # the eval's targets stay unseen below the Settings list
        return False
    if depth == 1 and ev_args.only and not re.search(ev_args.only, c["base"]):
        return False
    return c["on"] is None and c["name"] and not ev.is_unsafe(c) and not SKIP.search(c["base"].split(":")[0])


def tap(base, scroll, title=None):
    for _ in range(scroll):
        ev.adb("shell", "input", "swipe", *ev.SWIPE)
        time.sleep(0.5)
    _, t, cands = capture()
    c = next((c for c in cands if c["base"] == base), None)
    if not c or (title and t != title):
        return False
    ev.adb("shell", "input", "tap", str(c["cx"]), str(c["cy"]))
    time.sleep(SETTLE)
    return True


def goto(path):
    ev.reset(ev_args.snapshot)
    for step in path:
        if not tap(step["base"], step["scroll"]):
            return False
    return True


def main():
    global ev_args
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--max-depth", type=int, default=4)
    p.add_argument("--max-screens", type=int, default=280)
    p.add_argument("--taps-per-screen", type=int, default=10)
    p.add_argument("--snapshot", default="uinav-home-apps")
    p.add_argument("--only", default="", help="regex: tap only these home apps / Settings rows (a top-up crawl)")
    p.add_argument("--resume", action="store_true", help="skip screens already in OUT (their subtrees were finished)")
    ev_args = p.parse_args()
    seen, count = set(), 0
    if ev_args.resume:
        for line in open(ev_args.out):
            s = json.loads(line)
            if len(s["path"]) > 2 and not (ev_args.only and s["app"] != "com.android.settings"):
                # Home, Settings and the categories are walked again to reach the rest; a top-up crawl of an app
                # (--only) also forgets that app's screens reached some other way (Settings > Apps > Clock > Open)
                t, c, _ = ev.parse_layout(s["layouts"][0], "", toggle=True, limit=999)
                seen.add(screen_key(t, c))
                count += 1
    out = open(ev_args.out, "a" if ev_args.resume else "w")

    def explore(path):
        nonlocal count
        lay, title, cands = capture()
        key = screen_key(title, cands)
        if key in seen or count >= ev_args.max_screens:
            return
        seen.add(key)
        pkg = ev.foreground()
        layouts, sig = [lay], ev.signature(title, cands)
        for _ in range(4):  # every scroll position, until a swipe changes nothing
            ev.adb("shell", "input", "swipe", *ev.SWIPE)
            time.sleep(0.6)
            lay2, t2, c2 = capture()
            if t2 != title or ev.signature(t2, c2) == sig:
                break
            layouts.append(lay2)
            sig = ev.signature(t2, c2)
        count += 1
        out.write(json.dumps({"path": path, "title": title, "app": pkg, "layouts": layouts}) + "\n")
        out.flush()
        print(f"[{count}] depth {len(path)} {' > '.join(s['base'][:25] for s in path)} -> {title!r} "
              f"({len(layouts)} scroll positions)", flush=True)
        if len(path) >= ev_args.max_depth:
            return
        todo, done = [], set()
        for k, l in enumerate(layouts):
            for c in ev.parse_layout(l, "", toggle=True, limit=999)[1]:
                if c["base"] not in done and tappable(c, len(path)):
                    done.add(c["base"])
                    todo.append({"base": c["base"], "scroll": k})
        for step in todo if len(path) <= 1 else todo[:ev_args.taps_per_screen]:  # every Settings / Clock row
            for _ in range(len(layouts) - 1):  # back at this screen (normally): return to the top of the list
                ev.adb("shell", "input", "swipe", *ev.SWIPE_UP)
                time.sleep(0.3)
            if not tap(step["base"], step["scroll"], title) and \
                    not (goto(path) and tap(step["base"], step["scroll"])):
                print(f"  could not reach {step['base']!r}", flush=True)
                continue
            _, t2, c2 = capture()
            if screen_key(t2, c2) == key and len(path) <= 1:  # apps and top-level pages can be slow to open
                time.sleep(2.5)
                _, t2, c2 = capture()
            if screen_key(t2, c2) != key:  # the tap led somewhere new
                explore(path + [step])
            ev.adb("shell", "input", "keyevent", "KEYCODE_BACK")
            time.sleep(SETTLE)

    ev.reset(ev_args.snapshot)
    explore([])
    print(f"done: {count} screens", flush=True)


if __name__ == "__main__":
    main()
