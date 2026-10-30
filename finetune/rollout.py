#!/usr/bin/env python3
"""On-policy rollouts for a DAgger round: let the served model chase *training* goals and record every request.

The loop is eval.py's experiment loop (switch states, scroll_up after a scroll, stop on the third repeat of a screen)
at floor 0, so episodes go on past low-confidence steps and visit the states the model actually reaches, wrong turns
included. Each step writes the request body and the candidates behind it; label_onpolicy.py labels them afterwards
from the crawl graph.

usage: OLLAMA_HOST=http://127.0.0.1:8008 rollout.py data/v1 data/onpolicy.jsonl [--goals 200] [--max-steps 12]
"""
import argparse, json, random, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import eval as ev  # noqa: E402
import build_data as bd  # noqa: E402


def episode(goal, target, args, out):
    ev.reset(args.snapshot)
    history, seen, scrolled, exhausted, flipped = [], {}, set(), set(), set()
    toggled = scroll = None
    info = target["kind"] == "info"
    for step in range(1, args.max_steps + 1):
        try:
            lay = ev.layout()
        except (RuntimeError, subprocess.TimeoutExpired):  # android layout fails on a few screens (an open keyboard)
            return
        pkg = ev.foreground()
        try:
            title, cands, rows = ev.parse_layout(lay, goal, True)
        except (KeyError, ValueError):  # a node eval.py cannot read (no class)
            return
        sig = ev.signature(title, cands)
        if toggled:
            effect, f = ev.toggle_effect(*toggled, cands)
            flipped |= f
            history[-1] = f"step {step - 1}: tapped {toggled[0]['role']} '{toggled[0]['base']}' ({effect})"
            toggled = None
        if scroll and scroll[1] == title:
            if scroll[0] == "scroll_down":
                scrolled.add(title)
                if scroll[2] == sig:
                    exhausted.add(title)
            elif scroll[2] != sig:
                exhausted.discard(title)
        scroll = None
        seen[sig] = seen.get(sig, 0) + 1
        if seen[sig] >= 3:
            return
        fixed = ev.options(args, title, scrolled, exhausted)
        if len(cands) + len(fixed) > ev.MAX_OPTIONS:
            cands = ev.parse_layout(lay, goal, True, ev.MAX_OPTIONS - len(fixed))[1]
        answers = rows[:ev.MAX_ANSWERS] if info else []
        state = {"goal": goal, "step": step, "app": pkg, "window_title": title, "history": history[-5:],
                 "candidates": [{k: c[k] for k in ("id", "role", "name", "states", "x", "y", "w", "h")} for c in cands]}
        body = ev.request("kev", state, cands, None, answers, fixed)
        a = ev.systemone(body)["answers"]
        out.write(json.dumps({"target": target, "goal": goal, "body": {"state": body["state"], "questions": body["questions"]},
                              "cands": [{k: c[k] for k in ("id", "base", "name", "on")} for c in cands],
                              "answers": answers, "flipped": sorted(flipped)}) + "\n")
        out.flush()
        if a["done"]["noul"] >= 0.8:
            return
        action = a["action"]["choice"]
        chosen = next((c for c in cands if c["id"] == action), None)
        if chosen and chosen["on"] is not None and chosen["base"] in flipped:
            return
        if chosen and ev.is_unsafe(chosen):
            return
        label = f" {chosen['role']} '{chosen['name']}'" if chosen else ""
        if action == "scroll_down":
            ev.adb("shell", "input", "swipe", *ev.SWIPE)
            how, scroll = "swipe up", (action, title, sig)
        elif action == "scroll_up":
            ev.adb("shell", "input", "swipe", *ev.SWIPE_UP)
            how, scroll = "swipe down", (action, title, sig)
        elif action == "back":
            ev.adb("shell", "input", "keyevent", "KEYCODE_BACK")
            how = "back key"
        elif chosen:
            ev.adb("shell", "input", "tap", str(chosen["cx"]), str(chosen["cy"]))
            how = "tap"
            if chosen["on"] is not None:
                toggled = (chosen, cands)
        else:
            return
        history.append(f"step {step}: {action}{label} ({how})")
        time.sleep(0.8)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("data_dir")
    p.add_argument("out")
    p.add_argument("--screens", default=str(Path(__file__).parent / "data/screens.jsonl"))
    p.add_argument("--goals", type=int, default=200)
    p.add_argument("--skip", type=int, default=0, help="start at this goal of the shuffled pool (another batch)")
    p.add_argument("--max-steps", type=int, default=12)
    p.add_argument("--snapshot", default="uinav-home-apps")
    p.add_argument("--restart", default="", help="script that restarts the emulator after a failed snapshot load")
    a = p.parse_args()
    a.stuck_option = a.toggle_state = a.scroll_end = True  # the experiment loop
    screens, paths = [], set()
    for line in open(a.screens):
        s = json.loads(line)
        if (k := json.dumps(s["path"])) not in paths:
            paths.add(k)
            screens.append(s)
    tgts, _ = bd.targets(screens)
    cache = json.loads((Path(a.data_dir) / "goals.json").read_text())
    pool = [(g, t) for t in tgts for g in cache.get(bd.describe_target(t), []) if not bd.HOLDOUT.search(g)]
    rng = random.Random(1)
    rng.shuffle(pool)
    done = set()
    if Path(a.out).exists():  # resume: skip goals already rolled out
        done = {json.loads(l)["goal"] for l in open(a.out)}
    with open(a.out, "a") as out:
        for n, (goal, t) in enumerate(pool[a.skip:a.skip + a.goals], a.skip):
            if goal in done:
                continue
            t0 = time.time()
            try:
                episode(goal, t, a, out)
            except ev.ResetFailed:  # the emulator hung on a snapshot load: restart it and go on with the next goal
                if not a.restart:
                    raise
                subprocess.run([a.restart], timeout=300)
                continue
            print(f"[{n + 1}/{a.goals}] {t['kind']:4} {goal[:70]!r} {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
