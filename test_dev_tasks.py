"""Offline tests for the live dev suite (tasks-dev.json from finetune/make_dev_tasks.py): dev pages only, nothing
held out, checks that eval.py can run."""
import json, re, sys, unittest
from pathlib import Path

import eval as E

sys.path.insert(0, str(Path(__file__).parent / "finetune"))
import build_data as B  # noqa: E402
import make_dev_tasks as M  # noqa: E402

HERE = Path(__file__).parent
DATA = HERE / "finetune" / "data"
SHELL_SAFE = re.compile(r"^echo [A-Za-z0-9 %.:/-]+$")


class DevTasks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DATA / "v1" / "dev.jsonl").exists():  # the crawl data is not published with the code
            raise unittest.SkipTest("finetune/data/ not present")
        cls.tasks = json.loads((HERE / "tasks-dev.json").read_text())
        cls.dev = B.pages_of(DATA / "v1" / "dev.jsonl")

    def test_current(self):  # the file is what the script makes from the data on disk
        screens = M.lo.load_screens(DATA / "screens.jsonl")
        tasks, _ = M.make(screens, self.dev, json.loads((DATA / "v1" / "goals.json").read_text()))
        self.assertEqual(tasks, self.tasks)

    def test_size_and_ids(self):
        self.assertTrue(15 <= len(self.tasks) <= 40, len(self.tasks))
        self.assertEqual(len({t["id"] for t in self.tasks}), len(self.tasks))
        self.assertTrue(all(re.fullmatch(r"dev_[a-z0-9_]+_\d+", t["id"]) for t in self.tasks))
        self.assertEqual({t["kind"] for t in self.tasks}, {"open", "info"})

    def test_dev_pages_only(self):
        for t in self.tasks:
            self.assertIn(t["page"], self.dev, t["id"])
            self.assertNotIn(t["page"], B.HOLDOUT_PAGES, t["id"])

    def test_nothing_held_out(self):
        for t in self.tasks:
            self.assertIsNone(B.HOLDOUT.search(" ".join((t["goal"], t["page"], t.get("note", "")))), t["id"])

    def test_open_checks(self):
        for t in (t for t in self.tasks if t["kind"] == "open"):
            self.assertIsNotNone(re.search(t["layout_re"], f"window: {t['page']}\nsome row", re.M), t["id"])
            self.assertIsNone(re.search(t["layout_re"], f"window: {t['page']} more", re.M), t["id"])
            app = re.sub(r"\\(.)", r"\1", t["package"][1:-1])
            self.assertTrue(E.verify(t, t["page"], app, [], None), t["id"])
            self.assertFalse(E.verify(t, "Settings", app, [], None), t["id"])

    def test_info_expected(self):
        for t in (t for t in self.tasks if t["kind"] == "info"):
            self.assertRegex(t["expected_cmd"], SHELL_SAFE, t["id"])
            expected, row = t["expected_cmd"][len("echo "):], t["note"][len("crawled row: "):]
            self.assertTrue(E.contains(row, expected), t["id"])  # the crawled row passes verify and the answer check
            self.assertFalse(E.contains(t["goal"], M.value({"row": row, "label": row.split(": ")[0]})), t["id"])

    def test_only_on_own_page(self):  # verify checks rows (info) or the title (open), not which page shows them
        screens = M.lo.load_screens(DATA / "screens.jsonl")
        texts = M.screen_texts(screens)
        for t in self.tasks:
            own = [i for i, s in enumerate(screens) if s["title"] == t["page"]]
            if t["kind"] == "open":
                self.assertEqual(len(own), 1, t["id"])
            else:
                hits = [i for i, x in enumerate(texts) if E.contains(x, t["expected_cmd"][len("echo "):])]
                self.assertEqual(len(hits), 1, t["id"])
                self.assertIn(hits[0], own, t["id"])

    def test_skips(self):
        s = {"path": [{"base": "Settings", "scroll": 0}, {"base": "X", "scroll": 0}], "title": "X", "app": "a",
             "layouts": [[]]}
        info = {"kind": "info", "screen": 0, "scroll": 0, "page": "X", "label": "Alarm", "row": "Alarm: 7:30 AM"}
        self.assertEqual(M.usable(info, [s]), "time-dependent")
        self.assertEqual(M.usable(info | {"row": "Alarm: a, b"}, [s]), "not shell-safe")
        self.assertEqual(M.usable(info | {"kind": "set"}, [s]), "set")
        self.assertEqual(M.usable(info | {"kind": "open", "page": "Dismiss?"}, [s]), "dialog")
        twin = s | {"path": [{"base": "Settings", "scroll": 0}, {"base": "Y", "scroll": 0}]}
        self.assertEqual(M.usable(info | {"kind": "open"}, [s, twin]), "title not unique")
        self.assertIsNone(M.usable(info | {"kind": "open"}, [s, twin | {"app": "b"}]))
        tv = lambda text, y: {"class": "android.widget.TextView", "text": text, "bounds": f"[0,{y}][100,{y + 10}]",
                              "center": f"[50,{y + 5}]"}
        s["layouts"] = [[{"type": "APPLICATION", "active": True, "window-title": "X", "content": [
            {"class": "android.widget.LinearLayout", "interactions": ["CLICKABLE"], "bounds": "[0,0][100,40]",
             "center": "[50,20]", "children": [tv("IMEI", 0), tv("8674", 20)]}]}]]
        info = info | {"label": "IMEI", "row": "IMEI: 8674"}
        self.assertIsNone(M.usable(info, [s]))
        self.assertEqual(M.usable(info, [s, s], ["IMEI: 8674", "Other\nIMEI: 8674"]), "on another screen")
        self.assertIsNone(M.usable(info, [s, s], ["IMEI: 8674", "IMEI: 86745"]))


if __name__ == "__main__":
    unittest.main()
