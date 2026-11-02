"""Offline tests for gen_agents.py and the gen: route of eval.episode: canned model replies, no model, no device."""
import json, sys, unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

from PIL import Image

import eval as E
import gen_agents as G
import report as R

sys.path.insert(0, str(Path(__file__).parent / "finetune"))
import compare as C  # noqa: E402

DATA = Path(__file__).parent / "testdata"
GELAB, QWEN, OWL = (G.ADAPTERS[k] for k in ("gelab-zero-4b", "qwen3-vl-4b", "gui-owl-1.5-4b"))


def gelab(action):
    return f"<THINK> The goal needs Settings. </THINK>\nexplain:open it\taction:{action}\tsummary:Opened Settings"


def call(args, act="Tap Settings."):
    return f"Thought: next.\nAction: {act}\n<tool_call>\n" + json.dumps({"name": "mobile_use", "arguments": args}) \
        + "\n</tool_call>"


class GELabParse(unittest.TestCase):
    def test_actions(self):
        self.assertEqual(GELAB.parse(gelab("CLICK\tpoint:500,250")), ({"type": "tap", "x": 540, "y": 600},
                                                                     "Opened Settings"))
        a, _ = GELAB.parse(gelab("SLIDE\tpoint1:500,700\tpoint2:500,300"))
        self.assertEqual(a, {"type": "swipe", "x1": 540, "y1": 1680, "x2": 540, "y2": 720, "direction": "up"})
        self.assertEqual(GELAB.parse(gelab("LONGPRESS\tpoint:1000 0"))[0], {"type": "long_press", "x": 1079, "y": 0})
        self.assertEqual(GELAB.parse(gelab("TYPE\tvalue:hello world"))[0], {"type": "type", "text": "hello world"})
        self.assertEqual(GELAB.parse(gelab("WAIT\tvalue:2"))[0], {"type": "wait", "secs": 2.0})
        self.assertEqual(GELAB.parse(gelab("ABORT\tvalue:cannot"))[0], {"type": "abort"})
        self.assertEqual(GELAB.parse(gelab("AWAKE\tvalue:Settings"))[0]["type"], "noop")
        self.assertEqual(GELAB.parse("<think>x</think>\nexplain:e\taction:CLICK\tpoint:0,0")[0]["x"], 0)  # lower case

    def test_finish(self):
        self.assertEqual(GELAB.parse(gelab("COMPLETE\treturn:Android 16"))[0], {"type": "finish", "answer": "Android 16"})
        self.assertEqual(GELAB.parse(gelab("COMPLETE\treturn:"))[0], {"type": "finish", "answer": None})

    def test_messages(self):
        m = GELAB.messages("Turn on dark theme", [], "AAAA")
        self.assertEqual([p["type"] for p in m[0]["content"]], ["text", "text", "image_url", "text"])
        self.assertIn("已知用户指令为：Turn on dark theme指令结束", m[0]["content"][1]["text"])
        self.assertIn("暂无历史操作", m[0]["content"][1]["text"])
        self.assertEqual(m[0]["content"][2]["image_url"]["url"], "data:image/png;base64,AAAA")
        m = GELAB.messages("g", ["Opened Settings", "Opened Display"], "AAAA")
        self.assertIn("历史动作如下：Opened Display\n", m[0]["content"][1]["text"])  # only its latest summary


class ToolCallParse(unittest.TestCase):
    def test_qwen_999_grid(self):
        self.assertEqual(QWEN.parse(call({"action": "click", "coordinate": [500, 500]})),
                         ({"type": "tap", "x": 541, "y": 1201}, "Tap Settings."))
        self.assertEqual(QWEN.parse(call({"action": "click", "coordinate": [999, 999]}))[0],
                         {"type": "tap", "x": 1079, "y": 2399})
        a = QWEN.parse(call({"action": "swipe", "coordinate": [500, 300], "coordinate2": [500, 800]}))[0]
        self.assertEqual((a["direction"], a["y1"], a["y2"]), ("down", 721, 1922))
        self.assertEqual(QWEN.parse(call({"action": "system_button", "button": "Back"}))[0], {"type": "back"})
        self.assertEqual(QWEN.parse(call({"action": "system_button", "button": "Enter"}))[0],
                         {"type": "key", "key": "KEYCODE_ENTER"})

    def test_qwen_answer_then_terminate(self):
        self.assertEqual(QWEN.parse(call({"action": "answer", "text": "16"}))[0], {"type": "answer", "text": "16"})
        self.assertEqual(QWEN.parse(call({"action": "terminate", "status": "success"}))[0],
                         {"type": "finish", "answer": None})
        self.assertEqual(QWEN.parse(call({"action": "terminate", "status": "failure"}))[0], {"type": "abort"})

    def test_owl_1000_grid(self):
        self.assertEqual(OWL.parse(call({"action": "click", "coordinate": [500, 500]}))[0],
                         {"type": "tap", "x": 540, "y": 1200})
        self.assertEqual(OWL.parse(call({"action": "answer", "text": "Android 16"}))[0],
                         {"type": "finish", "answer": "Android 16"})
        self.assertEqual(OWL.parse(call({"action": "key", "text": "home"}))[0], {"type": "home"})
        self.assertEqual(OWL.parse(call({"action": "open", "text": "Settings"}))[0]["type"], "noop")
        # arguments as a JSON string and no closing tag
        self.assertEqual(OWL.parse('Action: x\n<tool_call>\n{"name": "mobile_use", "arguments": '
                                   '"{\\"action\\": \\"click\\", \\"coordinate\\": [0, 1000]}"}')[0],
                         {"type": "tap", "x": 0, "y": 2399})

    def test_history(self):
        m = QWEN.messages("What is my Android version?", ["Open Settings.", "Tap About."], "AAAA")
        self.assertIn("operation on the current device): Step 1: Open Settings.; Step 2: Tap About.; .",
                      m[1]["content"][0]["text"])
        self.assertTrue(m[0]["content"][0]["text"].startswith("\n\n# Tools"))
        m = OWL.messages("g", [], "AAAA")
        self.assertTrue(m[1]["content"][0]["text"].endswith("Previous actions:\nNone"))
        # history_n=4: the last four steps as screenshot + reply turns, earlier ones as 'Action:' sentences
        notes = []
        for i in range(6):
            m = OWL.messages("g", notes, f"IMG{i}")
            notes.append(OWL.parse(call({"action": "click", "coordinate": [i, i]}, f"Tap {i}."))[1])
        self.assertEqual([x["role"] for x in m], ["system"] + ["user", "assistant"] * 4 + ["user"])
        self.assertTrue(m[1]["content"][0]["text"].endswith("Previous actions:\nStep 1: Tap 0."))
        self.assertEqual([len(x["content"]) for x in m[1::2]], [2, 1, 1, 1, 1])  # the prompt only in the first turn
        self.assertIn("Tap 4.", m[-2]["content"][0]["text"])
        self.assertEqual(len(OWL.messages("g", [], "AAAA")), 2)  # a new episode resets the turns


class Malformed(unittest.TestCase):
    def test_noop(self):
        for agent, reply in [(GELAB, "I will tap Settings."), (GELAB, gelab("CLICK\tpoint:abc")),
                             (GELAB, gelab("JUMP")), (QWEN, "Action: tap\n<tool_call>\n{not json"),
                             (QWEN, "no tool call"), (OWL, call({"action": "click"})),
                             (OWL, call({"action": "click", "coordinate": [5]}))]:
            with mock.patch.object(agent, "call", return_value=reply):
                r, a, note = G.decide(agent, "g", [], "AAAA")
            self.assertEqual(r, reply)
            self.assertEqual(a["type"], "noop", reply)
            self.assertTrue(note.startswith("noop (malformed reply"), note)


class Transport(unittest.TestCase):
    def test_ollama_parts_and_lifted_tool_calls(self):
        msgs = QWEN.messages("g", [], "AAAA")
        conv = G.ollama_messages(msgs)
        self.assertEqual([(m["role"], bool(m.get("images"))) for m in conv],
                         [("system", False), ("user", False), ("user", True)])
        self.assertEqual(conv[2]["images"], ["AAAA"])
        reply = {"message": {"content": "Thought: t\nAction: Tap Settings.", "tool_calls": [
            {"function": {"name": "mobile_use", "arguments": {"action": "click", "coordinate": [500, 500]}}}]}}
        with mock.patch.object(G, "post", return_value=reply) as p:
            text = QWEN.call(msgs)
        self.assertEqual(p.call_args[0][0], G.OLLAMA + "/api/chat")
        self.assertEqual(QWEN.parse(text), ({"type": "tap", "x": 541, "y": 1201}, "Tap Settings."))

    def test_openai(self):
        reply = {"choices": [{"message": {"content": gelab("CLICK\tpoint:500,500")}}]}
        with mock.patch.object(G, "post", return_value=reply) as p:
            text = GELAB.call(GELAB.messages("g", [], "AAAA"))
        url, body = p.call_args[0][:2]
        self.assertTrue(url.endswith("/chat/completions"))
        self.assertEqual((body["temperature"], body["max_tokens"]), (0.1, 4096))
        self.assertEqual(GELAB.parse(text)[0], {"type": "tap", "x": 540, "y": 1200})
        self.assertIsNone(GELAB.ollama)


class Execute(unittest.TestCase):
    def test_commands(self):
        self.assertEqual(G.commands({"type": "tap", "x": 1, "y": 2}), [("shell", "input", "tap", "1", "2")])
        self.assertEqual(G.commands(G.swipe((540, 1700), (540, 700))),
                         [("shell", "input", "swipe", "540", "1700", "540", "700", "400")])
        self.assertEqual(G.commands({"type": "back"}), [("shell", "input", "keyevent", "KEYCODE_BACK")])
        self.assertEqual(G.commands({"type": "type", "text": "it's me"}), [("shell", "input", "text", "'it'\"'\"'s%sme'")])
        for t in ({"type": "finish", "answer": None}, {"type": "noop", "reason": "x"}, {"type": "wait", "secs": 1}):
            self.assertEqual(G.commands(t), [])

    def test_hit_smallest(self):
        big = {"x": 0, "y": 0, "w": 1080, "h": 400, "name": "row"}
        small = {"x": 900, "y": 100, "w": 100, "h": 100, "name": "switch"}
        self.assertIs(G.hit({"type": "tap", "x": 950, "y": 150}, [big, small]), small)
        self.assertIs(G.hit({"type": "tap", "x": 10, "y": 10}, [big, small]), big)
        self.assertIsNone(G.hit({"type": "tap", "x": 10, "y": 500}, [big, small]))
        self.assertIsNone(G.hit({"type": "back"}, [big]))

    def test_unknown_name(self):
        with self.assertRaises(SystemExit):
            G.adapter("gen:nope")


def run(agent_name, replies, task=None, reached=False, max_steps=10, layouts=None):
    """Runs one gen: episode on recorded layouts; returns (record, adb calls, prompts sent)."""
    flags = dict(stuck_option=True, toggle_state=True, scroll_end=True)
    args = Namespace(snapshot="x", max_steps=max_steps, floor=0.25, img_px=100, settle=0, variant=flags, **flags)
    task = task or {"id": "t", "kind": "open", "goal": "Open display settings"}
    s = json.loads((DATA / "settings.json").read_text())
    adb_calls, prompts = [], []
    agent = G.adapter("gen:" + agent_name)

    def model(msgs):
        prompts.append(msgs)
        return replies[len(prompts) - 1]

    with mock.patch.object(E, "reset"), mock.patch.object(E, "foreground", return_value="com.android.settings"), \
            mock.patch.object(E, "layout", side_effect=layouts or [s] * (max_steps + 1)), \
            mock.patch.object(E, "verify", side_effect=reached if isinstance(reached, list) else None,
                              return_value=reached), \
            mock.patch.object(E, "expected_value", return_value="16"), \
            mock.patch.object(E, "screenshot", return_value=(Image.new("RGB", (45, 100)), "AAAA")), \
            mock.patch.object(E, "adb", side_effect=lambda *a, **k: adb_calls.append(a)), \
            mock.patch.object(agent, "call", side_effect=model), mock.patch("builtins.print"):
        rec, _ = E.episode("gen:" + agent_name, task, args)
    return rec, adb_calls, prompts


class Episode(unittest.TestCase):
    def test_tap_then_finish(self):
        d = json.loads((DATA / "display.json").read_text())
        s = json.loads((DATA / "settings.json").read_text())
        cands = E.parse_layout(s, "Open display settings", True, 10 ** 6)[1]
        row = next(c for c in cands if c["name"].startswith("Battery"))
        x, y = round(row["cx"] * 1000 / 1080), round(row["cy"] * 1000 / 2400)  # GUI-Owl's 0-1000 grid
        rec, taps, prompts = run("gui-owl-1.5-4b", [call({"action": "click", "coordinate": [x, y]}, "Tap Battery."),
                                                    call({"action": "terminate", "status": "success"}, "Done.")],
                                 reached=[False, True], layouts=[s, d])
        self.assertEqual((rec["outcome"], rec["steps"], rec["first_reached_step"], rec["floor"]), ("success", 2, 2, 0.0))
        self.assertEqual(taps, [("shell", "input", "tap", str(round(x * 1.08)), str(round(y * 2.4)))])
        log = rec["step_log"]
        self.assertEqual(log[0]["chosen"], E.describe(row))
        self.assertEqual((log[0]["gate"], log[0]["done"], log[0]["conf"], log[0]["top3"]), ("act", 0.0, None, None))
        self.assertEqual(log[1]["parsed"], {"type": "finish", "answer": None})
        self.assertIn("<tool_call>", log[1]["reply"])
        self.assertEqual([x["role"] for x in prompts[1]], ["system", "user", "assistant", "user"])
        self.assertIn("Tap Battery.", prompts[1][2]["content"][0]["text"])
        # the fields report.py and compare.py --metrics read
        for k in ("model", "task", "kind", "floor", "outcome", "steps", "first_reached_step", "answer", "step_log",
                  "variant", "expected"):
            self.assertIn(k, rec)
        for s_ in log:
            for k in ("step", "window", "app", "reached", "action", "chosen", "conf", "done", "gate", "ms"):
                self.assertIn(k, s_)
            self.assertIn("model", s_["ms"])
        rec |= {"run": 0, "reached": True, "secs": 1.0}
        self.assertEqual([R.at_floor(rec, f) for f in (0.25, 0.6)], ["success", "success"])
        self.assertTrue(R.pattern(rec).startswith("success @"))
        self.assertEqual(C.metrics([rec])["success"], 1)

    def test_false_done(self):
        rec, taps, _ = run("gelab-zero-4b", [gelab("COMPLETE\treturn:done")])
        self.assertEqual((rec["outcome"], rec["steps"], taps), ("false_done", 1, []))

    def test_info_answers(self):
        task = {"id": "android_version", "kind": "info", "goal": "What is my Android version?"}
        rec, _, _ = run("gelab-zero-4b", [gelab("COMPLETE\treturn:Your Android version is 16.")], task, reached=True)
        self.assertEqual((rec["outcome"], rec["answer"], rec["expected"]), ("success", "Your Android version is 16.", "16"))
        rec, _, _ = run("gelab-zero-4b", [gelab("COMPLETE\treturn:It is 15.")], task, reached=True)
        self.assertEqual(rec["outcome"], "wrong_answer")
        rec, _, _ = run("gui-owl-1.5-4b", [call({"action": "terminate", "status": "success"})], task, reached=True)
        self.assertEqual((rec["outcome"], rec["answer"]), ("wrong_answer", None))  # finished without an answer
        # Qwen answers first and terminates on the next step
        rec, taps, _ = run("qwen3-vl-4b", [call({"action": "answer", "text": "16"}),
                                           call({"action": "terminate", "status": "success"})], task, reached=True)
        self.assertEqual((rec["outcome"], rec["answer"], rec["steps"], taps), ("success", "16", 2, []))
        self.assertEqual(rec["step_log"][0]["gate"], "noop")

    def test_malformed_is_a_noop_step(self):
        rec, taps, _ = run("qwen3-vl-4b", ["I would tap Display.", "still no tool call"], max_steps=2,
                           layouts=[json.loads((DATA / n).read_text()) for n in
                                    ("settings.json", "display.json", "settings.json")])
        self.assertEqual((rec["outcome"], rec["steps"], taps), ("max_steps", 2, []))
        self.assertEqual([s["gate"] for s in rec["step_log"]], ["noop", "noop"])
        self.assertTrue(rec["step_log"][0]["action"].startswith("noop (malformed reply"))

    def test_repeat_screen_and_abort(self):
        rec, _, prompts = run("gelab-zero-4b", [gelab("WAIT\tvalue:0"), gelab("WAIT\tvalue:0"), gelab("WAIT\tvalue:0")])
        self.assertEqual((rec["outcome"], rec["stuck_reason"], rec["steps"], len(prompts)), ("stuck", "repeat", 2, 2))
        rec, _, _ = run("gelab-zero-4b", [gelab("ABORT\tvalue:no way")])
        self.assertEqual((rec["outcome"], rec["stuck_reason"]), ("stuck", "model"))


if __name__ == "__main__":
    unittest.main()
