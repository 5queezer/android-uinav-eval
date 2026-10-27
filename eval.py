#!/usr/bin/env python3
"""Evaluate Ollama decision models (System One API) on multi-turn Android UI navigation.

Mirrors uinav's src/decide.rs (questions, criteria order, gate) and src/a11y.rs (candidate
ranking, describe(), unsafe blocklist) so that findings transfer back to uinav.
"""
import argparse, base64, io, json, os, re, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime
from pathlib import Path

from PIL import Image

SERIAL = os.environ.get("ANDROID_SERIAL", "emulator-5560")
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
os.environ.setdefault("ANDROID_HOME", str(Path.home() / "Android/Sdk"))
TEXT_ONLY = {"tev1", "kev"}  # model families that reject images with HTTP 400
MAX_CANDIDATES = 23  # the choice question allows 26 keys; three are scroll_down, back, stuck
MAX_OPTIONS = 26  # choice keys a/b/../z; candidates are trimmed when more fixed options are offered
MAX_ANSWERS = 25  # plus "none"
UNSAFE = ["password", "passphrase", "pin", "credit", "delete", "remove", "uninstall", "format"]
BULK_ROLES = {"list item", "tree item", "page tab"}
ROLES = {"Switch": "switch", "CheckBox": "check box", "RadioButton": "radio button",
         "EditText": "text", "SeekBar": "slider", "Button": "button", "ImageButton": "button"}
DONE_Q = "Judging by the screenshot and the UI state, has the goal already been achieved?"
DONE_Q_TEXT = "Judging by the UI state, has the goal already been achieved?"
ANSWER_Q = ("Which visible text answers the question in the goal? "
            "Choose none if the answer is not visible.")
FIXED = {
    "scroll_down": "scroll the screen down (swipe up) to reveal more controls",
    "scroll_up": "scroll the app window up to reveal controls above",
    "back": "go back / close the current popup (press the Android back key)",
    "stuck": "no candidate can help reach the goal",
}
SWIPE = ["540", "1700", "540", "700", "400"]
SWIPE_UP = SWIPE[2:4] + SWIPE[:2] + SWIPE[4:]  # the inverse (a swipe down) for scroll_up


# ---------------------------------------------------------------- device
def adb(*args, timeout=30):
    return subprocess.run(["adb", "-s", SERIAL, *args], capture_output=True, timeout=timeout)


def sh(cmd, timeout=30):
    return adb("shell", cmd, timeout=timeout).stdout.decode(errors="replace")


class ResetFailed(Exception):
    """The emulator did not come back from a snapshot load; the run cannot continue."""


def load(snapshot):
    try:
        out = adb("emu", "avd", "snapshot", "load", snapshot, timeout=60).stdout.decode(errors="replace")
        if "KO" in out:  # the console answers KO with exit status 0
            return False
        deadline = time.time() + 30
        while time.time() < deadline:  # adb reports the device offline for a moment after a load
            if sh("getprop sys.boot_completed", timeout=5).strip() == "1":
                return True
            time.sleep(0.1)
    except subprocess.TimeoutExpired:
        pass
    return False


def reset(snapshot):
    if not load(snapshot):
        time.sleep(5)
        if not load(snapshot):
            raise ResetFailed(f"snapshot load '{snapshot}' failed twice; is the emulator alive?")
    time.sleep(0.5)


def layout():
    # --no-idle: pages with live text (About's uptime, a running stopwatch) never go idle and the
    # idle wait then fails after ~4 s; we settle after every action instead.
    r = subprocess.run(["android", "layout", "--no-idle", "--device", SERIAL],
                       capture_output=True, timeout=60)
    if r.returncode:
        raise RuntimeError(f"android layout failed: {r.stderr.decode()[-300:]}")
    return json.loads(r.stdout)


def foreground():
    m = re.search(r"u0 ([\w.]+)/", sh("dumpsys activity activities | grep -m1 topResumedActivity"))
    return m.group(1) if m else ""


def screenshot(max_px):
    im = Image.open(io.BytesIO(adb("exec-out", "screencap", "-p").stdout)).convert("RGB")
    im.thumbnail((max_px, max_px))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return im, base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------- layout -> candidates, rows
def own(n):
    return " ".join((n.get("text") or n.get("content-desc") or "").split())


def flags(n):
    return set(n.get("interactions") or [])


def gather(n, texts, states, chk):
    """Texts and checked/selected states of the subtree, stopping at clickable descendants.
    chk gets the checked flag of each checkable descendant, clickable ones included (a Settings
    row around its own clickable Switch)."""
    for c in n.get("children", []):
        if "CHECKABLE" in flags(c):
            chk.append("CHECKED" in (c.get("state") or []))
        if "CLICKABLE" in flags(c):
            continue
        if own(c):
            texts.append(own(c))
        states.update(s.lower() for s in c.get("state") or [] if s in ("CHECKED", "SELECTED"))
        gather(c, texts, states, chk)


def parse_layout(windows, goal, toggle=False, limit=MAX_CANDIDATES):
    """Returns (window title, ranked candidates, visible text rows) of the APPLICATION windows.
    toggle: checkable candidates (or rows holding a checkable) are named '... [on]' / '... [off]'."""
    apps = [w for w in windows if w.get("type") == "APPLICATION"]
    title = next((w["window-title"] for w in apps if w.get("active")),
                 apps[0]["window-title"] if apps else "")
    cands, rows = [], {}

    def walk(n, in_click, row):
        f = flags(n)
        clickable = "CLICKABLE" in f
        x1, y1, x2, y2 = map(int, re.findall(r"-?\d+", n["bounds"]))
        cx, cy = map(int, re.findall(r"-?\d+", n["center"]))
        if (clickable or ("CHECKABLE" in f and not in_click)) and not n.get("off-screen") \
                and 0 <= cx < 1080 and 0 <= cy < 2400:
            texts, states = [], {s.lower() for s in n.get("state") or [] if s in ("CHECKED", "SELECTED")}
            chk = ["CHECKED" in (n.get("state") or [])] if "CHECKABLE" in f else []
            gather(n, texts, states, chk)
            name = own(n) or (texts[0] + (": " + ", ".join(texts[1:]) if texts[1:] else "") if texts else "")
            role = ROLES.get(n["class"].split(".")[-1]) or ("button" if own(n) else "list item")
            # base: the name without the state, to find the same control on the next screen
            c = {"role": role, "name": name[:120], "base": name[:120], "on": chk[0] if chk else None}
            if toggle and chk:  # an off switch would otherwise look like a plain row
                states.discard("checked")
                c["name"] += " [on]" if chk[0] else " [off]"
            cands.append(c | {"states": sorted(states),
                              "x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1, "cx": cx, "cy": cy})
        if clickable or "LONG_CLICKABLE" in f:
            row = (y1, x1, id(n))  # texts below belong to this row
        if own(n) and not n.get("off-screen"):
            rows.setdefault(row or (y1, x1, id(n)), []).append(own(n))
        for c in n.get("children", []):
            walk(c, in_click or clickable, row)

    for w in apps:
        for n in w["content"]:
            walk(n, False, None)
    # Nested clickables (a FrameLayout around the real row) share bounds; keep the named one.
    seen, uniq = set(), []
    for c in sorted(cands, key=lambda c: not c["name"]):
        if (k := (c["x"], c["y"], c["w"], c["h"])) not in seen:
            seen.add(k)
            uniq.append(c)
    gw = words(goal)
    uniq.sort(key=lambda c: (not c["name"], gw.isdisjoint(words(c["name"])),
                             c["role"] in BULK_ROLES, c["y"], c["x"]))
    cands = sorted(uniq[:limit], key=lambda c: (c["y"], c["x"]))
    for i, c in enumerate(cands):
        c["id"] = f"c{i + 1}"
    rows = [list(dict.fromkeys(t)) for _, t in sorted(rows.items())]  # tabs repeat desc as text
    texts = [t[0] + (": " + ", ".join(t[1:]) if t[1:] else "") for t in rows]
    return title, cands, list(dict.fromkeys(texts))


def words(s):
    return {w for w in re.split(r"[^\w]+", s.lower()) if len(w) >= 3}


def describe(c):
    s = f"{c['role']} '{c['name']}'"
    if c["states"]:
        s += f" [{', '.join(c['states'])}]"
    return s + f" at ({c['x']},{c['y']})"


def signature(title, cands):
    """The screen as the model sees it: window title plus candidate names and states."""
    return title, tuple(sorted((c["name"], tuple(c["states"])) for c in cands))


def toggle_effect(chosen, before, after):
    """Effect of tapping the checkable candidate `chosen` ('off→on'), judged from the candidates
    before and after, and the base names of all checkables whose state flipped between them."""
    now = {c["base"]: c["on"] for c in after if c["on"] is not None}
    flipped = {c["base"] for c in before if c["on"] is not None and now.get(c["base"], c["on"]) != c["on"]}
    o = lambda v: "on" if v else "off"
    if chosen["base"] in now:
        return f"{o(chosen['on'])}→{o(now[chosen['base']])}", flipped
    return f"was {o(chosen['on'])}; not on the next screen", flipped


def options(args, title, scrolled, exhausted):
    """The fixed action options that follow the candidates, in FIXED order."""
    keep = {"back"}
    if not (args.scroll_end and title in exhausted):
        keep.add("scroll_down")
    if args.scroll_end and (title in exhausted or title in scrolled):
        keep.add("scroll_up")
    if not args.stuck_option:
        keep.add("stuck")
    return {k: v for k, v in FIXED.items() if k in keep}


def action_q(crit):
    """The action question, naming only the scroll and stuck options that are offered."""
    q = "Which single action brings the UI closer to the goal? Prefer the candidate whose label matches the goal"
    if sc := [k for k in ("scroll_down", "scroll_up") if k in crit]:
        q += f"; choose {' or '.join(sc)} only if the needed control is not visible"
    if "stuck" in crit:
        q += "; choose stuck if no candidate can help"
    return q + "."


def is_unsafe(c):
    s = f"{c['name']} {c['role']}".lower()
    return any(w in s for w in UNSAFE)


# ---------------------------------------------------------------- model
def post(path, body, timeout=180):
    req = urllib.request.Request(OLLAMA + path, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from None


def is_vision(model):
    return model.split(":")[0] not in TEXT_ONLY


def request(model, state, cands, image, answers, fixed):
    crit = {c["id"]: describe(c) for c in cands} | fixed
    qs = {"done": {"type": "noul", "instructions": DONE_Q if image else DONE_Q_TEXT},
          "action": {"type": "choice", "instructions": action_q(crit), "criteria": crit}}
    if answers:
        qs["answer"] = {"type": "choice", "instructions": ANSWER_Q,
                        "criteria": {f"t{i + 1}": t[:200] for i, t in enumerate(answers)}
                        | {"none": "the answer is not visible on the screen"}}
    body = {"model": model, "keep_alive": "30m", "state": state, "questions": qs}
    if image:
        body["images"] = [image]
    return body


# ---------------------------------------------------------------- tasks
TRANSFORMS = {
    "pct": lambda v: f"{v}%",
    "date_long": lambda v: (d := datetime.strptime(v, "%Y-%m-%d")).strftime("%B ") + f"{d.day}, {d.year}",
    "gmt_offset": lambda v: f"GMT{v[0]}{v[1:3]}:{v[3:5]}",
    "ms_minutes": lambda v: f"{int(v) // 60000} minutes",
}


def expected_value(task):
    out = sh(task["expected_cmd"]).strip()
    if "extract" in task:
        out = re.search(task["extract"], out).group(1)
    return TRANSFORMS[task["transform"]](out) if "transform" in task else out


def contains(hay, needle):
    """Whole-token match, so '15' does not match inside a MAC address like 02:15:b8."""
    pat = r"(?<![\w.:])" + re.escape(needle) + r"(?![\w:]|\.\d)"
    return re.search(pat, hay, re.I) is not None


def verify(task, title, pkg, rows, expected):
    if task["kind"] == "info":
        return contains("\n".join(rows), expected)
    if task["kind"] == "set":
        return re.search(task["expect"], sh(task["check_cmd"]).strip()) is not None
    text = f"window: {title}\n" + "\n".join(rows)
    return (re.search(task.get("package", ""), pkg) is not None
            and re.search(task.get("layout_re", ""), text, re.M) is not None)


# ---------------------------------------------------------------- episode
def systemone(body):
    try:
        return post("/v1/systemone", body)
    except Exception as e:  # one retry, then the episode is an error
        print(f"  model request failed, retrying once: {e}", flush=True)
        time.sleep(2)
        return post("/v1/systemone", body)


def episode(model, task, args):
    reset(args.snapshot)
    vision = is_vision(model)
    info = task["kind"] == "info"
    expected = expected_value(task) if info else None
    history, steps, shots, first_reached = [], [], [], None
    seen, scrolled, exhausted, flipped = {}, set(), set(), set()  # per episode, for the experiment flags
    toggled = scroll = None  # (chosen, candidates) of a toggle tap / (action, title, signature) of a scroll
    rec = {"model": model, "task": task["id"], "kind": task["kind"], "floor": args.floor, "expected": expected,
           "variant": args.variant}
    for step in range(1, args.max_steps + 2):
        t, ms = time.time(), {}
        lay = layout()
        ms["layout"] = round((time.time() - t) * 1000)
        t = time.time()
        pkg = foreground()
        title, cands, rows = parse_layout(lay, task["goal"], args.toggle_state)
        reached = verify(task, title, pkg, rows, expected)
        ms["verify"] = round((time.time() - t) * 1000)
        if reached and first_reached is None:
            first_reached = step
        sig = signature(title, cands)
        if toggled:  # record what the tap did to the switch, e.g. on→off
            effect, f = toggle_effect(*toggled, cands)
            flipped |= f
            history[-1] = f"step {step - 1}: tapped {toggled[0]['role']} '{toggled[0]['base']}' ({effect})"
            steps[-1]["effect"] = effect
            toggled = None
        if scroll and scroll[1] == title:  # the scroll stayed in the window
            if scroll[0] == "scroll_down":  # unchanged = end of the list
                scrolled.add(title)
                if scroll[2] == sig:
                    exhausted.add(title)
            elif scroll[2] != sig:  # a scroll_up that moved the list: there is something below again
                exhausted.discard(title)
        scroll = None
        if step > args.max_steps:  # final observation after the last action
            return rec | {"outcome": "max_steps", "steps": args.max_steps, "first_reached_step": first_reached,
                          "answer": None, "step_log": steps}, shots
        seen[sig] = seen.get(sig, 0) + 1
        if args.stuck_option and seen[sig] >= 3:  # replaces the model's stuck option
            return rec | {"outcome": "stuck", "stuck_reason": "repeat", "steps": step - 1,
                          "first_reached_step": first_reached, "answer": None, "step_log": steps}, shots
        fixed = options(args, title, scrolled, exhausted)
        if len(cands) + len(fixed) > MAX_OPTIONS:  # keep the best-ranked candidates
            cands = parse_layout(lay, task["goal"], args.toggle_state, MAX_OPTIONS - len(fixed))[1]
        t, image = time.time(), None
        if vision:
            im, image = screenshot(args.img_px)
            shots.append(im)
            ms["shot"] = round((time.time() - t) * 1000)
        answers = rows[:MAX_ANSWERS] if info else []
        state = {"goal": task["goal"], "step": step, "app": pkg, "window_title": title,
                 "history": history[-5:],
                 "candidates": [{k: c[k] for k in ("id", "role", "name", "states", "x", "y", "w", "h")}
                                for c in cands]}
        t = time.time()
        resp = systemone(request(model, state, cands, image, answers, fixed))
        ms["model"] = round((time.time() - t) * 1000)
        a = resp["answers"]
        done, action = a["done"]["noul"], a["action"]["choice"]
        conf = a["action"]["confidence"]
        top = sorted(a["action"]["probabilities"].items(), key=lambda kv: -kv[1])[:3]
        answer = None
        if answers:
            ch = a["answer"]["choice"]
            answer = answers[int(ch[1:]) - 1] if ch != "none" else None
        chosen = next((c for c in cands if c["id"] == action), None)
        # gate: mirrors decide.rs gate() without the Apply rule
        finished = ("false_done" if not reached else
                    "wrong_answer" if info and not (answer and contains(answer, expected)) else "success")
        extra = {}
        if done >= 0.8:
            gate = finished
        elif conf < args.floor:
            gate = "uncertain"
        elif args.toggle_state and chosen and chosen["on"] is not None and chosen["base"] in flipped:
            gate, extra["anti_undo"] = finished, True  # undoing its own flip: the model thinks it is done
        elif action == "stuck":
            gate, extra["stuck_reason"] = "stuck", "model"
        elif chosen and is_unsafe(chosen):
            gate = "unsafe_blocked"
        elif chosen or action in ("scroll_down", "scroll_up", "back"):
            gate = "act"
        else:
            gate = "error"
        label = f" {chosen['role']} '{chosen['name']}'" if chosen else ""
        steps.append({"step": step, "window": title, "app": pkg, "reached": reached,
                      "candidates": [f"{c['id']}:{c['name']}" for c in cands], "action": action,
                      "chosen": describe(chosen) if chosen else None, "conf": round(conf, 3),
                      "top3": [[k, round(p, 3)] for k, p in top], "done": round(done, 3),
                      "answer": answer, "gate": gate, "ms": ms} | extra)
        print(f"  s{step:<2} done={done:.2f} {action} conf={conf:.2f}{label}"
              f"{f' answer={answer!r}' if answer else ''} -> {gate} [{title}] reached={reached} "
              f"model={ms['model']}ms layout={ms['layout']}ms", flush=True)
        if gate != "act":
            return rec | extra | {"outcome": gate, "steps": step, "first_reached_step": first_reached,
                                  "answer": answer, "step_log": steps}, shots
        t = time.time()
        if action == "scroll_down":
            adb("shell", "input", "swipe", *SWIPE)
            how = "swipe up"
            scroll = (action, title, sig)
        elif action == "scroll_up":
            adb("shell", "input", "swipe", *SWIPE_UP)
            how = "swipe down"
            scroll = (action, title, sig)
        elif action == "back":
            adb("shell", "input", "keyevent", "KEYCODE_BACK")
            how = "back key"
        else:
            adb("shell", "input", "tap", str(chosen["cx"]), str(chosen["cy"]))
            how = "tap"
            if args.toggle_state and chosen["on"] is not None:
                toggled = (chosen, cands)
        ms["act"] = round((time.time() - t) * 1000)
        history.append(f"step {step}: {action}{label} ({how})")
        time.sleep(args.settle)


# ---------------------------------------------------------------- main
def main():
    here = Path(__file__).parent
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models", required=True, help="comma-separated, e.g. clef-flash,tev1:4b")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--tasks", default=str(here / "tasks.json"))
    p.add_argument("--task-ids", help="comma-separated filter")
    p.add_argument("--max-steps", type=int, default=15)
    p.add_argument("--floor", type=float, default=0.6)
    p.add_argument("--img-px", type=int, default=1200, help="long side of the screenshot sent")
    p.add_argument("--settle", type=float, default=0.8, help="seconds to wait after an action")
    p.add_argument("--out", default=str(here / "results"))
    p.add_argument("--snapshot", default="uinav-home-apps", help="emulator snapshot each episode starts from")
    # experiment changes, on by default; --no-<flag> restores the earlier behaviour
    on = argparse.BooleanOptionalAction
    p.add_argument("--stuck-option", action=on, default=True,
                   help="no 'stuck' choice; end as stuck when the same screen is seen a third time")
    p.add_argument("--toggle-state", action=on, default=True,
                   help="name switches and rows holding one '[on]'/'[off]', record a tap's effect in "
                        "the history, and score re-picking a toggle the episode flipped as done")
    p.add_argument("--scroll-end", action=on, default=True,
                   help="drop scroll_down after one that changed nothing, offer scroll_up after a scroll_down")
    args = p.parse_args()
    args.variant = {k: getattr(args, k) for k in ("stuck_option", "toggle_state", "scroll_end")}
    variant = " ".join(("+" if v else "-") + k for k, v in args.variant.items())
    tasks = json.loads(Path(args.tasks).read_text())
    if args.task_ids:
        ids = args.task_ids.split(",")
        tasks = [t for t in tasks if t["id"] in ids]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    prev = None
    for model in args.models.split(","):
        safe = re.sub(r"[^\w.-]", "_", model)
        path = out / f"{safe}.jsonl"
        lines = path.read_text().splitlines() if path.exists() else []
        # errors are retried on resume; report.py keeps the last record per (model, task, run)
        have = {(r["task"], r["run"]) for r in map(json.loads, filter(None, lines)) if r["outcome"] != "error"}
        todo = [(t, r) for r in range(args.runs) for t in tasks if (t["id"], r) not in have]
        if not todo:
            continue
        unload(prev)
        t = time.time()
        try:  # load before timing steps (decision models reject /api/generate loads, but it unloads them)
            post("/v1/systemone", {"model": model, "keep_alive": "30m", "state": "warm-up",
                                   "questions": {"q": {"type": "noul", "instructions": "Is this a test?"}}})
            print(f"== {model}: loaded in {time.time() - t:.1f}s, {len(todo)} episodes", flush=True)
        except Exception as e:
            print(f"== {model}: warm-up failed ({e}); running anyway, {len(todo)} episodes", flush=True)
        prev = model
        for task, run in todo:
            print(f"{model} {task['id']}#{run}: {task['goal']}", flush=True)
            t = time.time()
            try:
                rec, shots = episode(model, task, args)
            except Exception as e:  # keep going (unless the emulator is gone); the record says what broke
                fatal = e
                rec, shots = {"model": model, "task": task["id"], "kind": task["kind"], "floor": args.floor,
                              "variant": args.variant, "outcome": "error", "error": f"{type(e).__name__}: {e}",
                              "steps": 0, "step_log": []}, []
            else:
                fatal = None
            rec |= {"run": run, "secs": round(time.time() - t, 1),
                    "reached": rec.get("first_reached_step") is not None}
            if rec["outcome"] != "success" and shots:
                d = out / "img" / safe / f"{task['id']}-{run}"
                d.mkdir(parents=True, exist_ok=True)
                for i, im in enumerate(shots, 1):
                    im.save(d / f"step-{i}.jpg", quality=70)
            with path.open("a") as f:
                f.write(json.dumps(rec) + "\n")
                f.flush()
                os.fsync(f.fileno())
            why = f" ({rec['stuck_reason']})" if "stuck_reason" in rec else " (anti-undo)" if rec.get("anti_undo") else ""
            print(f"{model} {task['id']}#{run}: {rec['outcome']}{why} after {rec['steps']} steps "
                  f"(reached@{rec.get('first_reached_step')}) answer={rec.get('answer')!r} "
                  f"expected={rec.get('expected')!r} {rec['secs']}s [{variant}]"
                  f"{' ' + rec['error'] if 'error' in rec else ''}",
                  flush=True)
            if isinstance(fatal, ResetFailed):
                unload(prev)
                sys.exit(f"FATAL: {fatal} Restart the emulator and rerun the same command to resume.")
    unload(prev)


def unload(model):
    try:
        if model:
            post("/api/generate", {"model": model, "keep_alive": 0}, timeout=60)
    except Exception as e:
        print(f"unloading {model} failed: {e}", flush=True)


if __name__ == "__main__":
    main()
