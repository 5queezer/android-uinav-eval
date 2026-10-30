"""Offline tests for eval.py: recorded layouts (testdata/) and scripted model answers, no device."""
import copy, json, unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

import eval as E

DATA = Path(__file__).parent / "testdata"
GOAL = "Turn on Use location for the time zone"
NEW = dict(stuck_option=True, toggle_state=True, scroll_end=True)
OLD = dict(stuck_option=False, toggle_state=False, scroll_end=False)
OLD_ACTION_Q = ("Which single action brings the UI closer to the goal? Prefer the candidate whose label "
                "matches the goal; choose scroll_down only if the needed control is not visible; choose "
                "stuck if no candidate can help.")


def lay(name):
    return json.loads((DATA / f"{name}.json").read_text())


def flip(layout, text):
    """The layout with the checkable in the row labelled `text` toggled."""
    layout = copy.deepcopy(layout)

    def walk(n, hit):
        hit = hit or n.get("text") == text or any(c.get("text") == text for c in n.get("children", []))
        if hit and "CHECKABLE" in (n.get("interactions") or []):
            st = n.get("state") or []
            n["state"] = [s for s in st if s != "CHECKED"] if "CHECKED" in st else st + ["CHECKED"]
        for c in n.get("children", []):
            walk(c, hit)

    for w in layout:
        for n in w["content"]:
            walk(n, False)
    return layout


def drop_row(layout, text):
    """The layout without the clickable row labelled `text` (a scroll that moved the list)."""
    layout = copy.deepcopy(layout)

    def walk(n):
        n["children"] = [c for c in n.get("children", [])
                         if not any(g.get("text") == text for g in c.get("children", []))]
        for c in n["children"]:
            walk(c)

    for w in layout:
        for n in w["content"]:
            walk(n)
    return layout


def answer(action, done=0.1, conf=0.9):
    return {"answers": {"done": {"noul": done},
                        "action": {"choice": action, "confidence": conf, "probabilities": {action: conf}}}}


def run(layouts, actions, flags=NEW, reached=False, max_steps=10):
    """Runs one episode of a text-only model; returns (record, request bodies, adb calls)."""
    args = Namespace(snapshot="x", max_steps=max_steps, floor=0.25, img_px=100, settle=0,
                     variant=dict(flags), **flags)
    bodies, adb_calls = [], []

    def model(body):
        bodies.append(body)
        a = actions[len(bodies) - 1]
        return a if isinstance(a, dict) else answer(a)

    with mock.patch.object(E, "reset"), mock.patch.object(E, "foreground", return_value="com.android.settings"), \
            mock.patch.object(E, "layout", side_effect=layouts), mock.patch.object(E, "systemone", side_effect=model), \
            mock.patch.object(E, "verify", return_value=reached), \
            mock.patch.object(E, "adb", side_effect=lambda *a, **k: adb_calls.append(a)), \
            mock.patch("builtins.print"):
        rec, _ = E.episode("tev1:4b", {"id": "t", "kind": "set", "goal": GOAL}, args)
    return rec, bodies, adb_calls


def crit(body):
    return body["questions"]["action"]["criteria"]


class Candidates(unittest.TestCase):
    def test_on_off_names(self):
        _, cands, _ = E.parse_layout(lay("date_time"), GOAL, toggle=True)
        names = {c["name"] for c in cands}
        self.assertIn("Set time automatically [on]", names)
        self.assertIn("Use location: Location may be used to set time zone [off]", names)
        self.assertIn("Use 24-hour format: 1:00 PM [off]", names)
        self.assertIn("Date: October 27, 2026", names)  # not checkable: no state
        self.assertFalse(any("checked" in c["states"] for c in cands))
        c = next(c for c in cands if c["base"] == "Use location: Location may be used to set time zone")
        self.assertEqual(E.describe(c), "list item 'Use location: Location may be used to set time zone [off]' "
                                        "at (0,1463)")

    def test_row_inherits_clickable_switch(self):
        # Display: the Dark theme row holds a Switch that is itself clickable (and a candidate)
        _, cands, _ = E.parse_layout(lay("display"), GOAL, toggle=True)
        names = [c["name"] for c in cands]
        self.assertIn("Dark theme: Will never turn on automatically [off]", names)
        self.assertIn("Dark theme [off]", names)
        on = E.parse_layout(flip(lay("display"), "Dark theme"), GOAL, toggle=True)[1]
        self.assertIn("Dark theme: Will never turn on automatically [on]", [c["name"] for c in on])

    def test_old_names_unchanged(self):
        _, cands, _ = E.parse_layout(lay("date_time"), GOAL)
        by = {c["name"]: c["states"] for c in cands}
        self.assertEqual(by["Set time automatically"], ["checked"])
        self.assertEqual(by["Use location: Location may be used to set time zone"], [])
        self.assertNotIn("Dark theme [off]", [c["name"] for c in E.parse_layout(lay("display"), GOAL)[1]])


class Signature(unittest.TestCase):
    def test_signature(self):
        title, cands, _ = E.parse_layout(lay("date_time"), GOAL, toggle=True)
        self.assertEqual(E.signature(title, cands), E.signature(title, list(reversed(cands))))
        _, flipped, _ = E.parse_layout(flip(lay("date_time"), "Use location"), GOAL, toggle=True)
        self.assertNotEqual(E.signature(title, cands), E.signature(title, flipped))
        self.assertNotEqual(E.signature(title, cands), E.signature("Other", cands))
        # without toggle names the states still tell the screens apart once a switch is on
        old = E.parse_layout(lay("date_time"), GOAL)[1]
        old_on = E.parse_layout(flip(lay("date_time"), "Use location"), GOAL)[1]
        self.assertNotEqual(E.signature(title, old), E.signature(title, old_on))

    def test_repeat_stop(self):
        s = lay("settings")
        rec, bodies, _ = run([s, s, s, s], ["back", "back", "back"])
        self.assertEqual((rec["outcome"], rec["stuck_reason"], rec["steps"]), ("stuck", "repeat", 2))
        self.assertEqual(len(bodies), 2)  # the third sighting ends the episode before asking the model
        self.assertEqual(rec["variant"], NEW)

    def test_repeat_after_other_screen(self):
        s, d = lay("settings"), lay("display")
        rec, bodies, _ = run([s, d, s, d, s], ["c2", "back", "c2", "back"])
        self.assertEqual((rec["outcome"], rec["steps"]), ("stuck", 4))

    def test_old_variant_has_stuck_and_no_repeat_stop(self):
        s = lay("settings")
        rec, bodies, _ = run([s] * 4, ["back", "back", "back"], flags=OLD, max_steps=3)
        self.assertEqual(rec["outcome"], "max_steps")
        self.assertIn("stuck", crit(bodies[0]))
        self.assertEqual(bodies[0]["questions"]["action"]["instructions"], OLD_ACTION_Q)
        rec, _, _ = run([s], ["stuck"], flags=OLD)
        self.assertEqual((rec["outcome"], rec["stuck_reason"]), ("stuck", "model"))

    def test_new_variant_has_no_stuck(self):
        rec, bodies, _ = run([lay("settings")], [answer("back", conf=0.1)])
        self.assertNotIn("stuck", crit(bodies[0]))
        self.assertNotIn("stuck", bodies[0]["questions"]["action"]["instructions"])
        self.assertEqual(rec["outcome"], "uncertain")  # low confidence still ends as uncertain


class Toggle(unittest.TestCase):
    ROW = "Use location: Location may be used to set time zone"

    def ids(self, layout, flags=NEW):
        cands = E.parse_layout(layout, GOAL, flags["toggle_state"])[1]
        return next(c["id"] for c in cands if c["base"] == self.ROW)

    def test_effect(self):
        before = E.parse_layout(lay("date_time"), GOAL, True)[1]
        after = E.parse_layout(flip(lay("date_time"), "Use location"), GOAL, True)[1]
        chosen = next(c for c in before if c["base"] == self.ROW)
        self.assertEqual(E.toggle_effect(chosen, before, after), ("off→on", {self.ROW}))
        self.assertEqual(E.toggle_effect(chosen, before, before), ("off→off", set()))
        other = E.parse_layout(lay("settings"), GOAL, True)[1]
        self.assertEqual(E.toggle_effect(chosen, before, other), ("was off; not on the next screen", set()))

    def test_anti_undo(self):
        a, b = lay("date_time"), flip(lay("date_time"), "Use location")
        c = self.ids(a)
        rec, bodies, taps = run([a, b, a], [c, c], reached=True)
        self.assertEqual((rec["outcome"], rec.get("anti_undo"), rec["steps"]), ("success", True, 2))
        self.assertEqual(len(taps), 1)  # the second pick is not acted on
        self.assertEqual(bodies[1]["state"]["history"], [f"step 1: tapped list item '{self.ROW}' (off→on)"])
        self.assertEqual(rec["step_log"][0]["effect"], "off→on")
        self.assertTrue(rec["step_log"][1]["anti_undo"])
        rec, _, _ = run([a, b, a], [c, c], reached=False)
        self.assertEqual((rec["outcome"], rec.get("anti_undo")), ("false_done", True))

    def test_anti_undo_covers_the_row_switch_pair(self):
        # Display's Dark theme row and its own Switch flip together; re-picking either is an undo
        a, b = lay("display"), flip(lay("display"), "Dark theme")
        cands = E.parse_layout(a, GOAL, True)[1]
        row = next(c["id"] for c in cands if c["base"].startswith("Dark theme:"))
        sw = next(c["id"] for c in E.parse_layout(b, GOAL, True)[1] if c["base"] == "Dark theme")
        rec, _, taps = run([a, b], [row, sw])
        self.assertEqual((rec["outcome"], rec.get("anti_undo"), len(taps)), ("false_done", True, 1))

    def test_low_confidence_undo_is_uncertain(self):
        a, b = lay("date_time"), flip(lay("date_time"), "Use location")
        c = self.ids(a)
        rec, _, _ = run([a, b], [c, answer(c, conf=0.1)])
        self.assertEqual(rec["outcome"], "uncertain")
        self.assertNotIn("anti_undo", rec)

    def test_no_flip_no_undo(self):
        a = lay("date_time")
        c = self.ids(a)
        rec, _, taps = run([a, a, a], [c, c], max_steps=2)  # the tap changed nothing: not an undo
        self.assertEqual((rec["outcome"], len(taps)), ("max_steps", 2))

    def test_old_variant_taps_again(self):
        a, b = lay("date_time"), flip(lay("date_time"), "Use location")
        c = self.ids(a, OLD)
        rec, bodies, taps = run([a, b, a], [c, c], flags=OLD, max_steps=2)
        self.assertEqual((rec["outcome"], len(taps)), ("max_steps", 2))
        self.assertEqual(bodies[1]["state"]["history"], [f"step 1: {c} list item '{self.ROW}' (tap)"])


class Scroll(unittest.TestCase):
    def test_options(self):
        new, old = Namespace(**NEW), Namespace(**OLD)
        self.assertEqual(list(E.options(old, "T", set(), set())), ["scroll_down", "back", "stuck"])
        self.assertEqual(list(E.options(old, "T", {"T"}, {"T"})), ["scroll_down", "back", "stuck"])
        self.assertEqual(list(E.options(new, "T", set(), set())), ["scroll_down", "back"])
        self.assertEqual(list(E.options(new, "T", {"T"}, set())), ["scroll_down", "scroll_up", "back"])
        self.assertEqual(list(E.options(new, "T", {"T"}, {"T"})), ["scroll_up", "back"])
        self.assertEqual(list(E.options(new, "U", {"T"}, {"T"})), ["scroll_down", "back"])
        self.assertEqual(E.action_q(E.options(old, "T", set(), set())), OLD_ACTION_Q)
        self.assertIn("choose scroll_up only if", E.action_q(E.options(new, "T", {"T"}, {"T"})))

    def test_noop_scroll_exhausts_window(self):
        d = lay("display")
        rec, bodies, swipes = run([d, d, d], ["scroll_down", "scroll_up", "c2"], max_steps=2)
        self.assertEqual(list(crit(bodies[0]))[-2:], ["scroll_down", "back"])
        self.assertEqual(list(crit(bodies[1]))[-2:], ["scroll_up", "back"])
        self.assertNotIn("scroll_down", bodies[1]["questions"]["action"]["instructions"])
        self.assertEqual(swipes[0][-5:], tuple(E.SWIPE))
        self.assertEqual(swipes[1][-5:], ("540", "700", "540", "1700", "400"))
        # a scroll_up that moved the list brings scroll_down back
        rec, bodies, _ = run([d, d, drop_row(d, "Screen saver"), d], ["scroll_down", "scroll_up", "c2"])
        self.assertEqual(list(crit(bodies[2]))[-3:], ["scroll_down", "scroll_up", "back"])

    def test_noop_scroll_up_keeps_exhausted(self):
        d = lay("display")
        no_repeat = dict(NEW, stuck_option=False)  # the same screen comes up three times here
        _, bodies, _ = run([d, d, d, d], ["scroll_down", "scroll_up", "back"], flags=no_repeat, max_steps=3)
        self.assertEqual(list(crit(bodies[2]))[-3:], ["scroll_up", "back", "stuck"])

    def test_moving_scroll_offers_both(self):
        d = lay("display")
        _, bodies, _ = run([d, drop_row(d, "Brightness level"), d], ["scroll_down", "back"], max_steps=2)
        self.assertEqual(list(crit(bodies[1]))[-3:], ["scroll_down", "scroll_up", "back"])

    def test_scroll_into_other_window_is_not_a_window_scroll(self):
        _, bodies, _ = run([lay("display"), lay("settings"), lay("settings")], ["scroll_down", "back"],
                           max_steps=2)
        self.assertNotIn("scroll_up", crit(bodies[1]))

    def test_old_variant_keeps_scrolling(self):
        d = lay("display")
        _, bodies, _ = run([d, d, d], ["scroll_down", "scroll_down"], flags=OLD, max_steps=2)
        self.assertEqual(list(crit(bodies[1]))[-3:], ["scroll_down", "back", "stuck"])


class Count(unittest.TestCase):
    def test_at_most_26_options(self):
        dr = lay("drawer")  # 23 candidates
        self.assertEqual(len(E.parse_layout(dr, GOAL)[1]), E.MAX_CANDIDATES)
        mixed = dict(NEW, stuck_option=False)  # stuck, scroll_down, scroll_up and back: four fixed options
        for flags in (NEW, OLD, mixed):
            moved = json.loads(json.dumps(dr).replace('"Maps"', '"Notes"'))  # the scroll changed the screen
            _, bodies, _ = run([dr, moved, dr], ["scroll_down", "back"], flags=flags, max_steps=2)
            for b in bodies:
                self.assertLessEqual(len(crit(b)), E.MAX_OPTIONS)
                self.assertEqual(len(crit(b)), len(set(crit(b))))
        self.assertEqual(list(crit(bodies[1]))[-4:], ["scroll_down", "scroll_up", "back", "stuck"])
        self.assertEqual(len(crit(bodies[1])), 26)
        self.assertEqual(sum(k.startswith("c") for k in crit(bodies[1])), 22)


class Verify(unittest.TestCase):
    def test_info_enforces_package(self):
        rows = ["Sort by", "First name"]
        task = {"kind": "info", "package": "^com\\.google\\.android\\.dialer$"}
        self.assertTrue(E.verify(task, "Settings", "com.google.android.dialer", rows, "First name"))
        self.assertFalse(E.verify(task, "Settings", "com.google.android.contacts", rows, "First name"))
        self.assertTrue(E.verify({"kind": "info"}, "Settings", "com.android.settings", rows, "First name"))


if __name__ == "__main__":
    unittest.main()
