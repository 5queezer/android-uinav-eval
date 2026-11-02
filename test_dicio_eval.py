import json, unittest
from pathlib import Path

import dicio_eval as D


class Settings(unittest.TestCase):
    def test_encoding(self):
        # field 3 (language) = 2 as a varint, field 13 (llm_remote_url) as a length-delimited string
        self.assertEqual(D.settings_pb({13: "http://x", 3: 2}), b"\x18\x02j\x08http://x")
        self.assertEqual(D.varint(300), b"\xac\x02")
        self.assertEqual(D.settings_pb({14: "gemma4:e4b"})[:2], b"r\x0a")

    def test_quote(self):
        self.assertEqual(D.quote("it's fünf"), "'it'\\''s fünf'")


class Reply(unittest.TestCase):
    def test_after_last_bubble(self):
        texts = ["What time is it?", "Weather", "wie spät", "13:00", "wie spät", "Es ist 13:34 Uhr"]
        self.assertEqual(D.reply_after(texts, "wie spät"), ["Es ist 13:34 Uhr"])
        self.assertEqual(D.reply_after(texts, "not said"), [])

    def test_rows_only_in_the_conversation(self):
        windows = [{"type": "APPLICATION", "content": [
            {"text": "Dicio-eval/main"},
            {"interactions": ["SCROLLABLE"], "children": [
                {"text": "hi"}, {"text": "Report"}, {"children": [{"text": "Hello!"}]}]},
            {"content-desc": "Open navigation drawer"}]}]
        self.assertEqual(D.rows(windows), ["hi", "Hello!"])


class Checks(unittest.TestCase):
    state = {"alarm": "2026-11-02 06:30:00", "timer": ["0:05:00"], "calendar": 0, "contacts": 3,
             "call": [], "app": "org.stypox.dicio.x"}

    def test_kinds(self):
        c = lambda **kw: D.check(kw, ["Es ist 13:34 Uhr"], self.state, "Zahnarzt\n15:00")
        self.assertTrue(c(type="reply", re=r"\d\d:\d\d"))
        self.assertTrue(c(type="state", field="alarm", re="06:30:00"))
        self.assertTrue(c(type="state", field="contacts", re="^3$"))
        self.assertTrue(c(type="state", field="call", re=r"^\[\]$"))
        self.assertTrue(c(type="screen", re="zahnarzt"))
        self.assertFalse(c(type="state", field="timer", re="0:08:00"))
        self.assertTrue(c(type="any", of=[{"type": "reply", "re": "nope"}, {"type": "state", "field": "timer",
                                                                            "re": "0:05:00"}]))

    def test_side_effects(self):
        after = self.state | {"timer": ["0:05:00", "0:03:00"], "app": "com.google.android.youtube"}
        self.assertEqual(D.side_effects(self.state, after, "org.stypox.dicio.x"), {"timer", "app"})
        self.assertEqual(D.side_effects(self.state, self.state, "org.stypox.dicio.x"), set())

    def test_task_file(self):
        tasks = json.loads(Path("tasks-dicio.json").read_text())
        self.assertEqual(len({t["id"] for t in tasks}), len(tasks))
        for t in tasks:
            self.assertIn(t["lang"], D.LANG)
            self.assertTrue(t["say"] and t["check"])


if __name__ == "__main__":
    unittest.main()
