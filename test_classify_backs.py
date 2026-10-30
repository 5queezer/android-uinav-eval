"""Offline tests for finetune/classify_backs.py on synthetic rollout records."""
import contextlib, io, json, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

import eval as E

sys.path.insert(0, str(Path(__file__).parent / "finetune"))
import classify_backs as C  # noqa: E402
from test_finetune import lay, screen  # noqa: E402
from test_label_v4 import DISPLAY, HOME, ROW, record, renamed  # noqa: E402

OPEN = {"kind": "open", "screen": 1, "page": "Display & touch"}


def episode(goal, *screens):
    """Records of one episode: (layout, history line of the action taken on it) per step."""
    recs, history = [], []
    for step, (layout, line) in enumerate(screens, 1):
        recs.append(record(layout, OPEN, goal=goal, history=history[-5:], step=step))
        history.append(f"step {step}: {line}")
    return recs


class Backs(unittest.TestCase):
    def test_the_next_record_logs_the_back(self):
        a = episode("Open the display settings", (lay("settings"), "c5 list item 'Sound' (tap)"),
                    (lay("sounds"), "back (back key)"), (lay("settings"), "back (back key)"))
        b = episode("Open the sounds", (lay("settings"), "scroll_down (swipe up)"))
        self.assertEqual(list(C.backs(a + b)), [a[1]])  # a[2]'s back ended the episode: not recorded


class Classify(unittest.TestCase):
    """Settings -> Display & touch is the target; Sounds is a wrong turn."""

    def setUp(self):
        self.screens = [screen("settings", [HOME]), screen("display", [HOME, DISPLAY]),
                        screen("sounds", [HOME, {"base": "Sound", "scroll": 0}, {"base": "Sounds", "scroll": 0}])]

    def test_recovery_off_the_path(self):
        self.assertEqual(C.classify(record(lay("sounds"), OPEN), self.screens), "recovery")

    def test_progress_loss_on_the_path(self):
        self.assertEqual(C.classify(record(lay("settings"), OPEN), self.screens), "progress_loss")

    def test_left_the_target_page(self):
        self.assertEqual(C.classify(record(lay("display"), OPEN), self.screens), "left_goal")

    def test_left_after_flipping_the_switch(self):  # flipped under the switch's name, the target is its row
        target = {"kind": "set", "screen": 1, "scroll": 0, "page": "Display & touch", "label": ROW, "on": False}
        rec = record(lay("settings"), target, flipped=["Dark theme"])
        self.assertEqual(C.classify(rec, self.screens), "left_goal")
        rec["flipped"] = []
        self.assertEqual(C.classify(rec, self.screens), "progress_loss")

    def test_left_with_the_answer_visible(self):
        row = E.parse_layout(lay("sounds"), "", True)[2][2]
        target = {"kind": "info", "screen": 1, "scroll": 0, "page": "Display & touch", "row": row}
        self.assertEqual(C.classify(record(lay("sounds"), target), self.screens), "left_goal")

    def test_unmatched(self):
        self.assertEqual(C.classify(record(renamed("display", "Popup Window"), OPEN), self.screens), "unmatched")

    def test_main_writes_the_classified_states(self):
        recs = episode("Open the display settings", (lay("settings"), "c5 list item 'Sound' (tap)"),
                       (lay("sounds"), "back (back key)"), (lay("settings"), "c2 list item 'Display' (tap)"),
                       (lay("display"), "back (back key)"), (lay("settings"), "back (back key)"))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(C.lo, "load_screens", return_value=self.screens), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            Path(d, "in.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
            with mock.patch.object(sys, "argv", ["classify_backs.py", f"{d}/in.jsonl", f"{d}/backs.jsonl"]):
                C.main()
            got = [json.loads(line) for line in Path(d, "backs.jsonl").read_text().splitlines()]
        self.assertEqual([(r["body"]["state"]["step"], r["back"]) for r in got], [(2, "recovery"), (4, "left_goal")])
        self.assertIn("2 backs in 5 states", out.getvalue())
        self.assertIn("Display & touch", out.getvalue())


if __name__ == "__main__":
    unittest.main()
