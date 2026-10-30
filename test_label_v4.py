"""Offline tests for the on-policy oracle (label_onpolicy.label: --labels path and the distance ablation) and its goal
swap (relabel_for)."""
import contextlib, io, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

import eval as E

sys.path.insert(0, str(Path(__file__).parent / "finetune"))
import label_onpolicy as L  # noqa: E402
from test_finetune import lay, screen  # noqa: E402

HOME = {"base": "Settings", "scroll": 0}
ROW = "Dark theme: Will never turn on automatically"  # the row around the Dark theme switch on testdata/display
DISPLAY = {"base": "Display & touch: x", "scroll": 0}  # not visible on the recorded Settings screen


def renamed(name, title):
    """A testdata layout under another window title (a crawled page that is not held out)."""
    layout = lay(name)
    for w in layout:
        if w.get("type") == "APPLICATION":
            w["window-title"] = title
    return layout


def scrolled(path, *layouts):
    """A crawled screen with one layout per scroll position."""
    title = E.parse_layout(layouts[0], "", toggle=True, limit=999)[0]
    return {"path": path, "title": title, "layouts": list(layouts),
            "bases": [{c["base"] for c in E.parse_layout(l, "", toggle=True, limit=999)[1]} for l in layouts]}


def record(layout, target, goal="Open the display settings", fixed=("scroll_down", "back"), history=(), step=1,
           flipped=()):
    """A rollout record of `layout`, as rollout.py writes it."""
    title, cands, rows = E.parse_layout(layout, goal, True)
    info = target["kind"] == "info"
    state = {"goal": goal, "step": step, "app": "com.android.settings", "window_title": title,
             "history": list(history),
             "candidates": [{k: c[k] for k in ("id", "role", "name", "states", "x", "y", "w", "h")} for c in cands]}
    body = E.request("kev", state, cands, None, rows if info else [], {k: E.FIXED[k] for k in E.FIXED if k in fixed})
    return {"target": target, "goal": goal, "body": body, "answers": rows if info else [], "flipped": list(flipped),
            "cands": [{k: c[k] for k in ("id", "base", "name", "on")} for c in cands]}


def action(out):
    return out["questions"]["action"]["label"]


class Back(unittest.TestCase):
    """--labels distance: back is labelled only when it shortens the way and no visible tap does better."""

    def test_back_after_a_wrong_turn(self):
        screens = [screen("settings", [HOME]), screen("display", [HOME, DISPLAY]),
                   screen("sounds", [HOME, {"base": "Sound", "scroll": 0}, {"base": "Sounds", "scroll": 0}])]
        out = L.label(record(lay("sounds"), {"kind": "open", "screen": 1}), screens, "distance")
        self.assertEqual(action(out), "back")

    def test_a_visible_later_step_beats_back(self):  # the target's last step is a row of the wrong page
        screens = [screen("display", [HOME, DISPLAY, {"base": "Time: 12:01 PM", "scroll": 0}]),
                   screen("sounds", [HOME, {"base": "Sound", "scroll": 0}, {"base": "Sounds", "scroll": 0}])]
        rec = record(lay("sounds"), {"kind": "open", "screen": 0})
        self.assertEqual(action(L.label(rec, screens, "distance")),
                         next(c["id"] for c in rec["cands"] if c["base"] == "Time: 12:01 PM"))

    def test_no_back_on_an_ancestor_when_nothing_helps(self):  # the next step is not on this screen at all
        screens = [screen("settings", [HOME]), screen("display", [HOME, DISPLAY])]
        self.assertIsNone(L.label(record(lay("settings"), {"kind": "open", "screen": 1}, fixed=("back",)), screens,
                                  "distance"))

    def test_no_back_when_it_only_ties(self):  # back + reopen costs as much as the scroll that is not offered
        screens = [scrolled([HOME], renamed("display", "Settings"), lay("settings")),
                   screen("sounds", [HOME, {"base": "Brightness level: 83%", "scroll": 0}])]
        out = L.label(record(lay("settings"), {"kind": "open", "screen": 1}), screens, "distance")  # no scroll_up
        self.assertIsNone(out)

    def test_never_back_on_the_target_page(self):
        # three pages down, the switch is on the first page and scroll_up is not offered: back and reopening would be
        # shorter, but it teaches leaving the page the goal is on
        page = [renamed(n, "Display & touch") for n in ("settings", "date_time", "drawer")] + [lay("display")]
        screens = [screen("settings", [HOME]), scrolled([HOME, DISPLAY], *page)]
        target = {"kind": "set", "screen": 1, "scroll": 0, "label": "Adaptive brightness", "on": False}
        self.assertIsNone(L.label(record(lay("display"), target), screens, "distance"))


class Target(unittest.TestCase):
    """On the target page the goal is done, whatever happened before."""

    MESSY = ["step 3: c5 list item 'Sound & vibration' (tap)", "step 4: back (back key)",
             "step 5: scroll_down (swipe up)", "step 6: scroll_up (swipe down)", "step 7: c2 list item 'Apps' (tap)"]

    def setUp(self):
        self.screens = [screen("settings", [HOME]), screen("display", [HOME, DISPLAY])]

    def test_open_after_a_messy_history(self):
        out = L.label(record(lay("display"), {"kind": "open", "screen": 1}, history=self.MESSY, step=8), self.screens)
        self.assertTrue(out["questions"]["done"]["label"])
        self.assertNotIn("action", out["questions"])

    def test_open_by_another_way_in(self):  # the same page crawled under two paths; the target is the second
        self.screens.append(screen("display", [HOME, {"base": "Search settings", "scroll": 0}]))
        rec = record(lay("display"), {"kind": "open", "screen": 2}, history=self.MESSY)
        self.assertTrue(L.label(rec, self.screens, "distance")["questions"]["done"]["label"])
        self.assertEqual(action(L.label(rec, self.screens)), "back")  # path matches the first crawl, as before v4

    def test_info_answers_with_the_row(self):
        rec = record(lay("display"), {"kind": "info", "screen": 1, "scroll": 0, "row": "Brightness level: 83%"},
                     history=self.MESSY)
        out = L.label(rec, self.screens)
        self.assertTrue(out["questions"]["done"]["label"])
        self.assertEqual(out["questions"]["answer"]["label"], f"t{rec['answers'].index('Brightness level: 83%') + 1}")

    def test_set_taps_the_switch_then_is_done(self):
        target = {"kind": "set", "screen": 1, "scroll": 0, "label": "Dark theme", "on": False}
        rec = record(lay("display"), target, goal="Turn on dark theme", history=self.MESSY)
        self.assertEqual(action(L.label(rec, self.screens)), next(c["id"] for c in rec["cands"] if c["base"] == "Dark theme"))
        rec = record(lay("display"), target, goal="Turn on dark theme", history=self.MESSY, flipped=["Dark theme"])
        self.assertTrue(L.label(rec, self.screens)["questions"]["done"]["label"])

    def test_set_is_done_under_another_name_of_the_switch(self):  # the row (with its summary) is the target's label
        target = {"kind": "set", "screen": 1, "scroll": 0, "label": ROW, "on": False}
        rec = record(lay("display"), target, goal="Turn on dark theme", flipped=["Dark theme"])  # the switch's name
        for labels in ("path", "distance"):
            self.assertTrue(L.label(rec, self.screens, labels)["questions"]["done"]["label"])
        rec = record(lay("display"), target, goal="Turn on dark theme", flipped=["Use 24-hour format: 1:00 PM"])
        self.assertFalse(L.label(rec, self.screens)["questions"]["done"]["label"])


class Scroll(unittest.TestCase):
    def test_scroll_down_toward_a_hidden_step(self):
        screens = [screen("settings", [HOME]), screen("display", [HOME, {"base": "Display & touch: x", "scroll": 1}])]
        self.assertEqual(action(L.label(record(lay("settings"), {"kind": "open", "screen": 1}), screens)), "scroll_down")

    def test_scroll_up_toward_a_hidden_step(self):  # Settings scrolled one page down; the step is on the first
        screens = [scrolled([HOME], renamed("display", "Settings"), lay("settings")),
                   screen("sounds", [HOME, {"base": "Brightness level: 83%", "scroll": 0}])]
        rec = record(lay("settings"), {"kind": "open", "screen": 1}, fixed=("scroll_down", "scroll_up", "back"))
        self.assertEqual(action(L.label(rec, screens)), "scroll_up")


class Swap(unittest.TestCase):
    """A launcher state recorded for a YouTube goal, relabelled for a YT Music goal: YT Music is ranked out of the
    recorded request (27 apps, 23 candidates) and must be in the rebuilt one."""

    def setUp(self):
        self.drawer = renamed("drawer", "Launcher")
        self.screens = [scrolled([HOME], self.drawer),
                        screen("display", [HOME, {"base": "YouTube", "scroll": 0}]),
                        screen("settings", [HOME, {"base": "YT Music", "scroll": 0}])]
        self.rec = record(self.drawer, {"kind": "open", "screen": 1}, goal="Watch a video on YouTube",
                          history=["step 1: c3 button 'Settings' (tap)"], step=2)
        self.earlier = {1: record(lay("settings"), {"kind": "open", "screen": 1}), 2: self.rec}  # 9 candidates

    def test_request_is_ranked_for_the_new_goal(self):
        self.assertNotIn("YT Music", {c["base"] for c in self.rec["cands"]})
        out = L.relabel_for(self.rec, {"kind": "open", "screen": 2}, "Play my music", self.screens,
                            earlier=self.earlier)
        want = E.parse_layout(self.drawer, "Play my music", True)[1]
        st = out["state"]
        self.assertEqual(st["goal"], "Play my music")
        self.assertEqual(st["history"], self.rec["body"]["state"]["history"])
        self.assertEqual(st["step"], 2)
        self.assertEqual([(c["id"], c["name"]) for c in st["candidates"]], [(c["id"], c["name"]) for c in want])
        self.assertEqual(list(out["questions"]["action"]["criteria"])[-2:], ["scroll_down", "back"])
        self.assertEqual(action(out), next(c["id"] for c in want if c["base"] == "YT Music"))

    def test_held_out_page(self):  # Date & time is where an eval task ends: no label for any goal
        screens = self.screens + [screen("date_time", [HOME, {"base": "Date", "scroll": 0}])]
        rec = record(lay("date_time"), {"kind": "open", "screen": 1})
        self.assertIsNone(L.label(rec, screens))
        self.assertIsNone(L.relabel_for(rec, {"kind": "open", "screen": 2}, "Play my music", screens))

    def test_history_ids_must_not_depend_on_the_goal(self):
        target = {"kind": "open", "screen": 2}
        self.assertIsNone(L.relabel_for(self.rec, target, "Play my music", self.screens))  # earlier screens unknown
        self.assertTrue(L.goal_free(self.earlier[1]))
        self.assertFalse(L.goal_free(self.rec))  # 27 apps, 23 offered: the goal picks which
        rec = record(self.drawer, {"kind": "open", "screen": 1}, goal="Watch a video on YouTube", step=3,
                     history=["step 1: c3 button 'Settings' (tap)", "step 2: c5 button 'Clock' (tap)",
                              "step 3: back (back key)"])
        earlier = self.earlier | {3: rec}
        self.assertIsNone(L.relabel_for(rec, target, "Play my music", self.screens, earlier=earlier))
        rec["body"]["state"]["history"] = ["step 1: c3 button 'Settings' (tap)", "step 2: back (back key)",
                                           "step 3: tapped switch 'Dark theme' (off→on)"]  # toggle lines carry no id
        self.assertIsNotNone(L.relabel_for(rec, target, "Play my music", self.screens, earlier=earlier))

    def test_flips_each_switch_once(self):  # a row and its own switch both recorded: one switch, flipped once
        screens = [screen("settings", [HOME]), screen("display", [HOME, DISPLAY])]
        rec = record(lay("display"), {"kind": "open", "screen": 1}, flipped=sorted([ROW, "Dark theme"]))
        out = L.relabel_for(rec, {"kind": "set", "screen": 1, "scroll": 0, "label": ROW, "on": False},
                            "Turn on dark theme", screens)
        self.assertTrue(out["questions"]["done"]["label"])
        names = {c["name"] for c in out["state"]["candidates"]}
        self.assertLessEqual({ROW + " [on]", "Dark theme [on]"}, names)

    def test_relabel_is_deterministic(self):  # parse_layout orders rows at one position by id(n), a memory address
        def text(t):
            return {"class": "android.widget.TextView", "text": t, "bounds": "[0,300][500,400]", "center": "[250,350]"}

        for order in (["B: 1", "A: 2"], ["A: 2", "B: 1"]):
            nodes = [text(t) for t in reversed(order)][::-1]  # made last to first: in CPython the ids fall
            layout = [{"type": "APPLICATION", "active": True, "window-title": "T", "content": nodes}]
            self.assertEqual(L.parse(layout, "")[2], order)


class Modes(unittest.TestCase):
    """--labels path (the default) reproduces the labels before v4; distance is the ablation."""

    def setUp(self):  # Display & touch, four pages long, is an ancestor of the target; its next step is on the first
        page = [renamed(n, "Display & touch") for n in ("settings", "date_time", "drawer")] + [lay("display")]
        self.screens = [screen("settings", [HOME]), scrolled([HOME, DISPLAY], *page),
                        screen("sounds", [HOME, DISPLAY, {"base": "Not on screen", "scroll": 0}])]
        self.rec = record(lay("display"), {"kind": "open", "screen": 2})  # scrolled to the end; no scroll_up offered

    def test_back_and_reopen_only_in_distance(self):
        self.assertIsNone(L.label(self.rec, self.screens))
        self.assertEqual(action(L.label(self.rec, self.screens, "distance")), "back")

    def test_relabel_for_takes_the_mode(self):
        target = {"kind": "open", "screen": 2}
        self.assertIsNone(L.relabel_for(self.rec, target, "Open it", self.screens))
        self.assertEqual(action(L.relabel_for(self.rec, target, "Open it", self.screens, "distance")), "back")

    def test_wrong_turn_is_back_even_when_not_offered(self):  # as before v4; distance only labels offered actions
        screens = [screen("settings", [HOME]), screen("display", [HOME, DISPLAY]),
                   screen("sounds", [HOME, {"base": "Sound", "scroll": 0}, {"base": "Sounds", "scroll": 0}])]
        rec = record(lay("sounds"), {"kind": "open", "screen": 1}, fixed=("scroll_down",))
        self.assertEqual(action(L.label(rec, screens)), "back")
        self.assertIsNone(L.label(rec, screens, "distance"))


class Main(unittest.TestCase):
    def run_main(self, *args):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(L, "load_screens", return_value=[]), \
                mock.patch.object(L.bd, "targets", return_value=([], {})), \
                mock.patch.object(L.bd, "pages_of", return_value={"Sounds"}) as pages_of:
            Path(d, "in.jsonl").write_text("")
            Path(d, "goals.json").write_text("{}")  # no dependency on the unpublished goal cache
            with mock.patch.object(sys, "argv", ["label_onpolicy.py", f"{d}/in.jsonl", f"{d}/out.jsonl", "--swap", "1",
                                                 "--goals", f"{d}/goals.json", *args]):
                L.main()
        return pages_of

    def test_dev_pages_are_held_out_by_default(self):  # --swap draws no dev-page target without --skip-pages-of
        self.assertEqual(self.run_main().call_args[0][0], str(Path(L.__file__).parent / "data/v1/dev.jsonl"))
        self.assertFalse(self.run_main("--skip-pages-of", "").called)


if __name__ == "__main__":
    unittest.main()
