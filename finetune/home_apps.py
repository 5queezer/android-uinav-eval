#!/usr/bin/env python3
"""Home-screen records for goals in other apps: the first step is the right app icon, not Settings.

Round 1 and 2 trained only on Settings and Clock goals, so the model learnt "from the home screen, tap Settings" and
took it for 8 of 10 Phone-app goals. These records teach the first step for Gmail, Photos, YouTube, Messages and
Chrome (Phone stays held out as the new-app test). Goals come from a local LLM on the CPU, cached in goals-home.json.

usage: home_apps.py data/screens.jsonl data/v3/home.jsonl [--per-app 12]
"""
import argparse, json, random, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import eval as ev  # noqa: E402
import build_data as bd  # noqa: E402

APPS = {"Gmail": "email", "Photos": "photos and pictures", "YouTube": "videos",
        "Messages": "text messages (SMS)", "Chrome": "the web browser"}


def goals(app, what, n, model):
    prompt = (f"A phone user asks an assistant for help. Write {n} different short requests (one per line, no numbering, "
              f"no quotes) that can only be done in the Android app \"{app}\" ({what}); the first step is to open "
              f"{app} from the home screen. Every request must clearly be about {what}. Do not name the app in at "
              f"least half of them. Vary the wording.")
    body = {"model": model, "think": False, "stream": False, "keep_alive": "20m",
            "options": {"temperature": 0.8, "num_gpu": 0}, "prompt": prompt}  # CPU: the GPU is shared
    req = urllib.request.Request(bd.OLLAMA + "/api/generate", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return [l.strip(" -•\"'") for l in json.loads(r.read())["response"].splitlines() if l.strip()][:n]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("screens")
    p.add_argument("out")
    p.add_argument("--per-app", type=int, default=12)
    p.add_argument("--model", default="gemma4:12b-it-q8_0")
    a = p.parse_args()
    home = next(json.loads(l) for l in open(a.screens) if json.loads(l)["path"] == [])
    cache_path = Path(a.out).with_name("goals-home.json")
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    for app, what in APPS.items():
        if app not in cache:
            cache[app] = goals(app, what, a.per_app, a.model)
            cache_path.write_text(json.dumps(cache, indent=1))
            print(app, cache[app], flush=True)
    rng, recs = random.Random(4), []
    for app, gs in cache.items():
        for goal in gs:
            if bd.HOLDOUT.search(goal):
                continue
            for exp in (True, False):  # both loop variants
                args = bd.Args(exp)
                title, cands, rows = ev.parse_layout(home["layouts"][0], goal, args.toggle_state)
                fixed = ev.options(args, title, set(), set())
                chosen = next((c for c in cands if c["base"] == app), None)
                if not chosen:
                    continue
                state = {"goal": goal, "step": 1, "app": home["app"], "window_title": title, "history": [],
                         "candidates": [{k: c[k] for k in ("id", "role", "name", "states", "x", "y", "w", "h")} for c in cands]}
                body = ev.request("kev", state, cands, None, [], fixed)
                body["questions"]["done"]["label"] = False
                body["questions"]["action"]["label"] = chosen["id"]
                recs.append({"state": body["state"], "questions": body["questions"]})
    rng.shuffle(recs)
    with open(a.out, "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(recs)} home-screen records -> {a.out}")


if __name__ == "__main__":
    main()
