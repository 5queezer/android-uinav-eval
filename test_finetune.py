"""Offline tests for finetune/: the synthetic done screen (build_data.flip) and the on-policy oracle (label_onpolicy)."""
import json, sys, unittest
from pathlib import Path

import eval as E

sys.path.insert(0, str(Path(__file__).parent / "finetune"))
import build_data as B  # noqa: E402
import label_onpolicy as L  # noqa: E402

DATA = Path(__file__).parent / "testdata"


def lay(name):
    if name == "sounds":  # date_time under another title: a crawled page that is not held out
        layout = lay("date_time")
        for w in layout:
            if w.get("window-title") == "Date & time":
                w["window-title"] = "Sounds"
        return layout
    return json.loads((DATA / f"{name}.json").read_text())


def screen(name, path):
    title, cands, _ = E.parse_layout(lay(name), "", toggle=True, limit=999)
    return {"path": path, "title": title, "layouts": [lay(name)], "bases": [{c["base"] for c in cands}]}


def record(name, target, goal="Open the display settings"):
    """A rollout record of the screen `name`, as rollout.py writes it."""
    title, cands, rows = E.parse_layout(lay(name), goal, True)
    fixed = {"back": E.FIXED["back"], "scroll_down": E.FIXED["scroll_down"]}
    state = {"goal": goal, "step": 1, "app": "com.android.settings", "window_title": title, "history": [],
             "candidates": [{k: c[k] for k in ("id", "role", "name", "states", "x", "y", "w", "h")} for c in cands]}
    body = E.request("kev", state, cands, None, [], fixed)
    return {"target": target, "goal": goal, "body": body, "answers": rows, "flipped": [],
            "cands": [{k: c[k] for k in ("id", "base", "name", "on")} for c in cands]}


class Flip(unittest.TestCase):
    def test_flips_one_switch(self):
        before = {c["base"]: c["on"] for c in E.parse_layout(lay("date_time"), "", True)[1] if c["on"] is not None}
        base = next(iter(before))
        after = {c["base"]: c["on"] for c in E.parse_layout(B.flip(lay("date_time"), base), "", True)[1]
                 if c["on"] is not None}
        self.assertEqual(after[base], not before[base])
        self.assertEqual({k: v for k, v in after.items() if k != base}, {k: v for k, v in before.items() if k != base})

    def test_unknown_switch(self):
        self.assertIsNone(B.flip(lay("date_time"), "no such switch"))


class Oracle(unittest.TestCase):
    """Settings list -> Display & touch is the target; Sounds is a wrong turn; Date & time is held out."""

    def setUp(self):
        rows = [c["base"] for c in E.parse_layout(lay("settings"), "", True, limit=999)[1]]
        self.sound = next(b for b in rows if b.startswith("Sound"))  # visible on the recorded Settings screen
        self.target = {"kind": "open", "screen": 1, "page": "Display & touch"}

    def screens(self, step):
        return [screen("settings", [{"base": "Settings", "scroll": 0}]),
                screen("display", [{"base": "Settings", "scroll": 0}, step]),
                screen("date_time", [{"base": "Settings", "scroll": 0}, {"base": "System", "scroll": 2},
                                     {"base": "Date & time", "scroll": 0}]),
                screen("sounds", [{"base": "Settings", "scroll": 0}, {"base": "Sound", "scroll": 0},
                                  {"base": "Sounds", "scroll": 0}])]

    def test_tap_the_visible_next_step(self):
        rec = record("settings", self.target)
        out = L.label(rec, self.screens({"base": self.sound, "scroll": 0}))
        self.assertEqual(out["questions"]["action"]["label"], next(c["id"] for c in rec["cands"] if c["base"] == self.sound))
        self.assertFalse(out["questions"]["done"]["label"])

    def test_scroll_toward_a_hidden_step(self):
        out = L.label(record("settings", self.target), self.screens({"base": "Display & touch: x", "scroll": 1}))
        self.assertEqual(out["questions"]["action"]["label"], "scroll_down")

    def test_done_on_the_target_page(self):
        out = L.label(record("display", self.target), self.screens({"base": self.sound, "scroll": 0}))
        self.assertTrue(out["questions"]["done"]["label"])
        self.assertNotIn("action", out["questions"])

    def test_back_after_a_wrong_turn(self):
        out = L.label(record("sounds", self.target), self.screens({"base": self.sound, "scroll": 0}))
        self.assertEqual(out["questions"]["action"]["label"], "back")

    def test_no_label_on_a_held_out_page(self):  # Date & time is where an eval task ends
        self.assertIsNone(L.label(record("date_time", self.target), self.screens({"base": self.sound, "scroll": 0})))


if __name__ == "__main__":
    unittest.main()
