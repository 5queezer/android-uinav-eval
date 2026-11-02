#!/usr/bin/env python3
"""Benchmark Dicio (voice assistant) builds on the emulator: send an utterance through the debug-only
EVAL_INPUT broadcast, wait for the reply, then check the reply text and the device state.

Every episode starts from the `dicio` snapshot (dicio/setup.sh), writes the variant's settings into
Dicio's DataStore and records which side effects happened (timers, alarms, calendar events, contacts,
placed calls, the foreground app); a side effect the task does not allow is a false action.

usage: dicio_eval.py --variant upstream|branch-text|llm:<ollama model> [--tasks tasks-dicio.json]
"""
import argparse, json, re, time
from datetime import datetime
from pathlib import Path

import eval as E

HERE = Path(__file__).parent
VARIANTS = json.loads((HERE / "dicio/variants.json").read_text())
LANG = {"de": 2, "en": 3}  # language.proto
DIGITS = re.compile(r"\d")


# ---------------------------------------------------------------- settings.pb (user_settings.proto)
def varint(n):
    out = bytearray()
    while True:
        b, n = n & 0x7F, n >> 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def settings_pb(fields):
    """fields: {field number: int | str}; enums and ints as varints, strings length-delimited."""
    out = bytearray()
    for num, v in sorted(fields.items()):
        if isinstance(v, str):
            data = v.encode()
            out += varint(num << 3 | 2) + varint(len(data)) + data
        else:
            out += varint(num << 3) + varint(v)
    return bytes(out)


def configure(pkg, fields):
    E.sh(f"am force-stop {pkg}")
    data = settings_pb(fields)
    r = E.subprocess.run(["adb", "-s", E.SERIAL, "shell", f"run-as {pkg} sh -c 'mkdir -p files/datastore && "
                          f"cat > files/datastore/settings.pb'"], input=data, capture_output=True, timeout=30)
    if r.returncode:
        raise RuntimeError(f"writing settings failed: {r.stderr.decode()}")


# ---------------------------------------------------------------- device state
def fingerprint():
    alarm = re.search(r"Next alarm clock information:\s*\n\s*user:0 .*?= ([\d-]+ [\d:]+)", E.sh("dumpsys alarm"))
    timers = re.findall(r"RUNNING\|[^|]*\|Σ([\d:]+)", E.sh("dumpsys notification --noredact"))
    count = lambda uri: len(re.findall(r"^Row:", E.sh(f"content query --uri {uri} --projection _id"), re.M))
    # the emulator hangs up at once, so placed calls are read from the call log
    calls = re.findall(r"number=([^,\s]+)", E.sh("content query --uri content://call_log/calls --projection number"))
    return {"alarm": alarm.group(1) if alarm else None, "timer": sorted(timers),
            "calendar": count("content://com.android.calendar/events"),
            "contacts": count("content://com.android.contacts/raw_contacts"),
            "call": calls, "app": E.foreground()}


def side_effects(before, after, pkg):
    fx = {k for k in ("alarm", "timer", "calendar", "contacts", "call") if before[k] != after[k]}
    if after["app"] not in (pkg, before["app"]):
        fx.add("app")
    return fx


# ---------------------------------------------------------------- Dicio's conversation
def rows(windows):
    """Visible texts of Dicio's conversation (its scrollable list) in layout order; a user bubble's
    text is one row."""
    out = []

    def walk(n, inside):
        inside = inside or "SCROLLABLE" in E.flags(n)
        t = E.own(n)
        if inside and t and t != "Report":
            out.append(t)
        for c in n.get("children", []):
            walk(c, inside)

    for w in windows:
        if w.get("type") == "APPLICATION":
            for c in w.get("content", []):
                walk(c, False)
    return out


def quote(s):  # for the device shell
    return "'" + s.replace("'", "'\\''") + "'"


def app_text(windows):
    """All visible text of the application windows (another app's screen)."""
    out = []

    def walk(n):
        if E.own(n):
            out.append(E.own(n))
        for c in n.get("children", []):
            walk(c)

    for w in windows:
        if w.get("type") == "APPLICATION":
            for c in w.get("content", []):
                walk(c)
    return "\n".join(out)


def reply_after(texts, said):
    """The rows after the last occurrence of the utterance (the user's bubble)."""
    idx = max((i for i, t in enumerate(texts) if t == said), default=None)
    return [] if idx is None else texts[idx + 1:]


def wait_reply(pkg, said, timeout):
    """Polls until Dicio has answered (or another app took the foreground) and nothing changed for ~2 s."""
    t0, last, stable, reply = time.time(), None, 0, []
    while time.time() - t0 < timeout:
        fg = E.foreground()
        reply = reply_after(rows(E.layout()), said) if fg == pkg else []
        sig = (fg, [DIGITS.sub("0", r) for r in reply])  # a running countdown is still the same reply
        stable = stable + 1 if sig == last else 0
        last = sig
        if stable >= 3 and (reply or fg != pkg):
            return reply, time.time() - t0
        time.sleep(0.7)
    return reply, None


# ---------------------------------------------------------------- checks
def check(c, reply, state, layout_text):
    kind = c["type"]
    if kind == "any":
        return any(check(x, reply, state, layout_text) for x in c["of"])
    if kind == "reply":  # Dicio's answer
        return re.search(c["re"], "\n".join(reply), re.I | re.S) is not None
    if kind == "state":  # a fingerprint field
        return re.search(c["re"], json.dumps(state[c["field"]], ensure_ascii=False)) is not None
    if kind == "screen":  # the visible text of the app in the foreground, if that is not Dicio
        return re.search(c["re"], layout_text, re.I | re.S) is not None
    if kind == "shell":
        return re.search(c["re"], E.sh(c["cmd"])) is not None
    raise ValueError(kind)


def logs():
    out = E.sh("logcat -d -s RemoteLlmEngine:* RealLlmEngine:* DicioTools:* SkillEvaluator:E EvalInputReceiver:*")
    return [l.split(": ", 1)[-1] for l in out.splitlines() if ": " in l and not l.startswith("-")][-40:]


def episode(task, variant, args):
    pkg = variant["package"]
    E.reset(args.snapshot)
    for port in variant.get("reverse", []):  # the host's LLM server through adb: the emulator's NAT
        E.adb("reverse", f"tcp:{port}", f"tcp:{port}")  # sometimes refuses right after a snapshot load
    configure(pkg, {int(k): v for k, v in variant["settings"].items()} | {3: LANG[task["lang"]]})
    E.sh("logcat -c")
    E.sh(f"am start -n {pkg}/org.stypox.dicio.MainActivity")
    for _ in range(40):  # input before the skills are loaded falls through to a placeholder fallback;
        if len(rows(E.layout())) >= 4:  # the home screen lists the skills once they are
            break
        time.sleep(0.5)
    before = fingerprint()
    turns, total = [], 0.0
    for said in task["say"]:
        E.sh(f"am broadcast -a org.stypox.dicio.EVAL_INPUT -p {pkg} --es text {quote(said)}")
        reply, secs = wait_reply(pkg, said, args.timeout)
        turns.append({"said": said, "reply": reply, "secs": secs})
        total += secs or args.timeout
        if E.foreground() != pkg and said != task["say"][-1]:
            E.sh(f"am start -n {pkg}/org.stypox.dicio.MainActivity")
            time.sleep(1.5)
    time.sleep(2)  # an app or a call Dicio starts may come up a moment after its reply
    after = fingerprint()
    screen = app_text(E.layout()) if after["app"] != pkg else ""  # a screen check is about another app
    if after["app"] != pkg:  # bring Dicio back to read its answer to the last utterance
        E.sh(f"am start -n {pkg}/org.stypox.dicio.MainActivity")
        time.sleep(1.5)
        turns[-1]["reply"] = reply_after(rows(E.layout()), task["say"][-1]) or turns[-1]["reply"]
    fx = side_effects(before, after, pkg)
    ok = all(check(c, turns[-1]["reply"], after, screen) for c in task["check"])
    false_action = sorted(fx - set(task.get("allow", [])))
    return {"task": task["id"], "cat": task["cat"], "lang": task["lang"], "variant": args.variant,
            "outcome": "false_action" if false_action else "success" if ok else "fail",
            "ok": ok, "false_action": false_action, "effects": sorted(fx), "turns": turns,
            "secs": round(total, 1), "state": after, "log": logs()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--variant", required=True, help="a dicio/variants.json key, or llm:<model>")
    p.add_argument("--tasks", default="tasks-dicio.json")
    p.add_argument("--task-ids")
    p.add_argument("--lang", help="only tasks in this language")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--snapshot", default="dicio")
    p.add_argument("--out", default="results-dicio")
    a = p.parse_args()
    name, _, model = a.variant.partition(":")
    variant = dict(VARIANTS[name if model else a.variant])
    if model:  # remote LLM fallback: field 14 = llm_remote_model
        variant["settings"] = variant["settings"] | {"14": model}
    tasks = json.loads(Path(a.tasks).read_text())
    if a.task_ids:
        tasks = [t for t in tasks if t["id"] in a.task_ids.split(",")]
    if a.lang:
        tasks = [t for t in tasks if t["lang"] == a.lang]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / (re.sub(r"[^\w.-]+", "_", a.variant) + ".jsonl")
    done = {(r["task"], r["run"]) for r in map(json.loads, path.open())} if path.exists() else set()
    for run in range(a.runs):
        for t in tasks:
            if (t["id"], run) in done:
                continue
            r = episode(t, variant, a) | {"run": run, "time": datetime.now().isoformat(timespec="seconds")}
            with path.open("a") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"{a.variant} {t['id']}#{run}: {r['outcome']} {r['secs']}s effects={r['effects']} "
                  f"reply={' | '.join(r['turns'][-1]['reply'])[:110]!r}", flush=True)


if __name__ == "__main__":
    main()
