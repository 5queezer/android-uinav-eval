#!/usr/bin/env python3
"""Record one demo video per task: emulator screen + a caption panel with the model's decisions.

usage: demo.py OUT_DIR [--model d3:4b] [--floor 0.25] [--task-ids a,b]   (resumable: skips finished mp4s)
"""
import argparse, json, subprocess, sys, textwrap, time
from pathlib import Path

EVAL_DIR = Path.home() / "Projects/uinav-wt-android-eval-exp1/android-eval"
sys.path.insert(0, str(EVAL_DIR))
import eval as ev  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

W, H, PW = 540, 1200, 760  # phone width/height in the video, panel width
F = "/usr/share/fonts/google-noto/NotoSans-%s.ttf"
MONO = "/usr/share/fonts/jetbrains-mono-fonts/JetBrainsMono-Regular.otf"
font = lambda size, w="Regular": ImageFont.truetype(F % w, size)
BG, FG, DIM, ACC = (18, 20, 26), (235, 237, 242), (130, 136, 150), (110, 170, 255)
OUTCOME = {"success": ((60, 180, 100), "SUCCESS"), "stuck": ((220, 150, 40), "STUCK"),
           "uncertain": ((200, 170, 60), "UNCERTAIN"), "max_steps": ((200, 90, 70), "MAX STEPS"),
           "false_done": ((210, 70, 70), "FALSE DONE"), "wrong_answer": ((210, 70, 70), "WRONG ANSWER"),
           "unsafe_blocked": ((170, 100, 200), "UNSAFE BLOCKED"), "error": ((210, 70, 70), "ERROR")}
WHY = {"stuck": "same screen seen 3 times", "uncertain": "confidence below the floor",
       "max_steps": "step limit reached", "unsafe_blocked": "chosen control is on the unsafe blocklist",
       "false_done": "model said done, but the goal was not reached"}


def adb(*a, **kw):
    return subprocess.run(["adb", "-s", ev.SERIAL, *a], capture_output=True, **kw)


def label(step, key):
    names = dict(c.split(":", 1) for c in step["candidates"])
    return f"'{names[key]}'" if key in names else key


def wrap(d, text, f, width):
    out = []
    for para in text.split("\n"):
        line = ""
        for w in para.split():
            if d.textlength((line + " " + w).strip(), font=f) > width:
                out.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        out.append(line)
    return out


def panel(path, task, model, floor, steps, cur, rec=None):
    """steps[:cur] are shown; steps[cur-1] is highlighted with its top-3; rec set = final panel."""
    im = Image.new("RGB", (PW, H), BG)
    d = ImageDraw.Draw(im)
    x, y, tw = 36, 36, PW - 72
    d.text((x, y), f"uinav decision loop  ·  {model}  ·  floor {floor}", font=font(20), fill=DIM)
    y += 34
    d.text((x, y), f"task: {task['id']}  ({task['kind']})", font=font(20), fill=DIM)
    y += 46
    for ln in wrap(d, task["goal"], font(38, "Bold"), tw):
        d.text((x, y), ln, font=font(38, "Bold"), fill=FG)
        y += 50
    y += 20
    d.line((x, y, x + tw, y), fill=(50, 54, 64), width=2)
    y += 22
    if cur == 0:
        d.text((x, y), "reading the screen …", font=font(26), fill=DIM)
    for s in steps[max(0, cur - 9):cur]:  # the last few steps fit
        last = s is steps[cur - 1]
        what = {"scroll_down": "scroll down", "scroll_up": "scroll up", "back": "back"}.get(
            s["action"], f"tap {label(s, s['action'])}")
        if s["gate"] != "act":  # the episode ended here; the action was not executed
            what = "stop: done" if s["done"] >= 0.8 else f"stop ({what} not executed)"
        col = FG if last else DIM
        d.text((x, y), f"{s['step']:>2}", font=ImageFont.truetype(MONO, 24), fill=ACC if last else DIM)
        line = wrap(d, f"{what}" + (f"  ({s['effect'].replace('→', ' to ')})" if s.get("effect") else ""), font(26, "SemiBold"), tw - 60)
        for ln in line[:2]:
            d.text((x + 50, y - 2), ln, font=font(26, "SemiBold" if last else "Regular"), fill=col)
            y += 36
        d.text((x + 50, y - 4), f"conf {s['conf']:.2f}   done {s['done']:.2f}   [{s['window'] or s['app']}]"[:60],
               font=font(19), fill=DIM)
        y += 34
        if last and not rec:
            y += 4
            for key, p in s["top3"]:
                d.rounded_rectangle((x + 50, y, x + 50 + int(300 * p) + 2, y + 24), 4,
                                    fill=ACC if key == s["action"] else (70, 76, 90))
                d.text((x + 370, y - 2), f"{p:.2f}  {label(s, key)}"[:34], font=font(20), fill=FG if key == s["action"] else DIM)
                y += 32
            d.text((x + 50, y), "done?", font=font(20), fill=DIM)
            d.rounded_rectangle((x + 120, y + 4, x + 120 + int(230 * s["done"]) + 2, y + 22), 4, fill=(90, 160, 110))
            d.text((x + 370, y - 2), f"{s['done']:.2f}  (0.80 = stop)", font=font(20), fill=DIM)
            y += 40
        y += 6
    if rec:
        col, txt = OUTCOME.get(rec["outcome"], ((150, 150, 150), rec["outcome"].upper()))
        y = H - 230
        d.rounded_rectangle((x, y, x + tw, y + 190), 14, fill=col)
        d.text((x + 24, y + 18), txt, font=font(44, "Bold"), fill=(255, 255, 255))
        sub = (f"answer: {rec['answer']!r}" + (f"   (expected {rec['expected']!r})" if rec.get("expected") else "")
               if rec.get("answer") else WHY.get(rec["outcome"], "goal state reached"))
        if rec.get("anti_undo"):
            sub = "re-picked the switch it already flipped → counted as done"
        for i, ln in enumerate(wrap(d, sub, font(24), tw - 48)[:3]):
            d.text((x + 24, y + 86 + i * 32), ln, font=font(24), fill=(255, 255, 255))
    im.save(path)


def record(task, args, out):
    marks, rec_proc = [], {}
    orig_reset, orig_sys = ev.reset, ev.systemone

    def reset(snap):
        orig_reset(snap)
        adb("shell", "rm", "-f", "/sdcard/demo.mp4")
        rec_proc["p"] = subprocess.Popen(["adb", "-s", ev.SERIAL, "shell", "screenrecord", "--size", f"{W}x{H}",
                                          "--bit-rate", "6000000", "/sdcard/demo.mp4"])
        time.sleep(1.0)  # encoder start-up; the first frame is t=0
        rec_proc["t0"] = time.time() - 0.6

    def systemone(body):
        r = orig_sys(body)
        marks.append(time.time() - rec_proc["t0"])
        return r

    ev.reset, ev.systemone = reset, systemone
    try:
        rec, _ = ev.episode(args.model, task, args)
    finally:
        ev.reset, ev.systemone = orig_reset, orig_sys
    time.sleep(2.0)  # show where it ended
    end = time.time() - rec_proc["t0"]
    adb("shell", "pkill", "-INT", "screenrecord")
    rec_proc["p"].wait(timeout=20)
    time.sleep(0.5)
    adb("pull", "/sdcard/demo.mp4", str(out / f"{task['id']}.raw.mp4"), timeout=60, check=True)
    rec |= {"marks": [round(m, 2) for m in marks], "end": round(end, 2)}
    (out / f"{task['id']}.json").write_text(json.dumps(rec, indent=1))
    return rec


def render(task, rec, args, out):
    tmp = out / "panels" / task["id"]
    tmp.mkdir(parents=True, exist_ok=True)
    steps, marks = rec["step_log"], rec["marks"]
    times = [0.0] + marks[:len(steps)]
    lines = []
    for i in range(len(steps) + 1):
        p = tmp / f"p{i:02}.png"
        last = i == len(steps)
        panel(p, task, args.model, args.floor, steps, i, rec if last else None)
        dur = (times[i + 1] - times[i]) if not last else rec["end"] - times[i] + 10
        lines += [f"file '{p}'", f"duration {max(dur, 0.04):.3f}"]
    lines.append(f"file '{tmp / f'p{len(steps):02}.png'}'")
    raw = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(out / f"{task['id']}.raw.mp4")], capture_output=True, text=True).stdout)
    hold = max(rec["end"] - raw, 0) + 2  # screenrecord stops emitting frames on a still screen
    (tmp / "list.txt").write_text("\n".join(lines) + "\n")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / f"{task['id']}.raw.mp4"),
         "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-filter_complex",
         f"[0:v]fps=30,scale={W}:{H},setsar=1,tpad=stop_mode=clone:stop_duration={hold:.2f}[l];"
         "[1:v]fps=30,format=yuv420p,setsar=1[r];[l][r]hstack=inputs=2:shortest=1,format=yuv420p[v]",
         "-map", "[v]", "-c:v", "libx264", "-crf", "22", "-preset", "medium", "-movflags", "+faststart",
         str(out / f"{task['id']}.mp4")], check=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--model", default="d3:4b")
    p.add_argument("--floor", type=float, default=0.25)
    p.add_argument("--task-ids")
    p.add_argument("--render-only", action="store_true")
    a = p.parse_args()
    args = argparse.Namespace(model=a.model, floor=a.floor, max_steps=15, img_px=1200, settle=0.8,
                              snapshot="uinav-home-apps", stuck_option=True, toggle_state=True, scroll_end=True)
    args.variant = {k: True for k in ("stuck_option", "toggle_state", "scroll_end")}
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tasks = json.loads((EVAL_DIR / "tasks.json").read_text())
    if a.task_ids:
        tasks = [t for t in tasks if t["id"] in a.task_ids.split(",")]
    if not a.render_only:
        ev.post("/v1/systemone", {"model": a.model, "keep_alive": "30m", "state": "warm-up",
                                  "questions": {"q": {"type": "noul", "instructions": "Is this a test?"}}})
    for t in tasks:
        if (out / f"{t['id']}.mp4").exists() and not a.render_only:
            continue
        rec = json.loads((out / f"{t['id']}.json").read_text()) if a.render_only else record(t, args, out)
        render(t, rec, args, out)
        print(f"{t['id']}: {rec['outcome']} after {rec['steps']} steps, {rec['end']:.0f}s video", flush=True)
    ev.unload(a.model) if not a.render_only else None


if __name__ == "__main__":
    main()
