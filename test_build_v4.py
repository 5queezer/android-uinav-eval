"""Offline tests for build_data.py's v4 options (--loop, --terminal-copies, --messy-frac, --cap-per-class) on a tiny
crawl made from the testdata screens. The goal cache is prefilled, so the LLM is never asked."""
import contextlib, io, json, random, re, sys, tempfile, unittest, warnings
from collections import Counter
from pathlib import Path
from unittest import mock

import eval as E

sys.path.insert(0, str(Path(__file__).parent / "finetune"))
import build_data as B  # noqa: E402

DATA = Path(__file__).parent / "testdata"
APPS = "Apps: Assistant, recent apps, default apps"
STORAGE = "Storage: 36% used - 5.11 GB free"
PROFILE = "Profile picture, double tap to open Google Account"  # leads to a held-out page
HISTORY = re.compile(r"step (\d+): (c\d+ [\w ]+ '.*' \(tap\)|back \(back key\)|scroll_down \(swipe up\)|"
                     r"tapped [\w ]+ '.*' \((on|off)→(on|off)\))$")


def lay(name, title=None):
    layout = json.loads((DATA / f"{name}.json").read_text())
    for w in layout:
        if title and w.get("type") == "APPLICATION" and w.get("active"):
            w["window-title"] = title
    return layout


def world():
    """Home -> Settings -> Display & touch / Sounds (date_time renamed) / Date & time (held out, a sibling of both)."""
    s = [{"base": "Settings", "scroll": 0}]
    screens = [("drawer", "Home", []), ("settings", None, s), ("display", None, s + [{"base": APPS, "scroll": 0}]),
               ("date_time", "Sounds", s + [{"base": STORAGE, "scroll": 0}]),
               ("date_time", None, s + [{"base": PROFILE, "scroll": 0}])]
    out = []
    for name, title, path in screens:
        layout = lay(name, title)
        out.append({"path": path, "title": E.parse_layout(layout, "")[0], "app": "com.android.settings",
                    "layouts": [layout]})
    return out


def build(*opts, held="Nowhere"):
    """train and dev records of build_data.main on world(), with a goal per target and `held` as the one dev page."""
    screens = world()
    tgts, _ = B.targets(screens)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "screens.jsonl").write_text("".join(json.dumps(s) + "\n" for s in screens))
        (d / "out").mkdir()
        (d / "out" / "goals.json").write_text(json.dumps(
            {B.describe_target(t): [f"{t['kind']} {t['label']} on {t['page']}"] for t in tgts}))
        (d / "dev.jsonl").write_text(json.dumps({"state": {"window_title": held},
                                                 "questions": {"done": {"label": True}}}) + "\n")
        argv = ["build_data.py", str(d / "screens.jsonl"), str(d / "out"), "--held-from", str(d / "dev.jsonl"), *opts]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(B, "llm", side_effect=AssertionError("LLM")), \
                contextlib.redirect_stdout(io.StringIO()):
            B.main()
        return [[json.loads(l) for l in (d / "out" / f"{n}.jsonl").read_text().splitlines()] for n in ("train", "dev")]


def untied(recs):
    """recs with each answer list as a set: eval.parse_layout orders text rows at the same spot by id(), per run."""
    out = json.loads(json.dumps(recs))
    for r in out:
        if a := r["questions"].get("answer"):
            a["label"] = a["criteria"].get(a.get("label"), a.get("label"))
            a["criteria"] = sorted(a["criteria"].values())
    return out


def done(r):
    return r["questions"]["done"]["label"]


class Loop(unittest.TestCase):
    def test_exp_only(self):
        train, _ = build("--loop", "exp")
        switches = {c["base"] for c in E.parse_layout(lay("date_time"), "", True)[1] if c["on"] is not None}
        sounds = [r for r in train if r["state"]["window_title"] == "Sounds"]
        self.assertTrue(sounds)
        for r in train:
            if "action" in r["questions"]:
                self.assertNotIn("stuck", r["questions"]["action"]["criteria"])
        for r in sounds:
            names = {c["name"] for c in r["state"]["candidates"]}
            for b in switches:
                self.assertTrue({b + " [on]", b + " [off]"} & names, b)
                self.assertNotIn(b, names)

    def test_original_loop_offers_stuck(self):  # the contrast: --exp-frac 0 renders the original loop
        train, _ = build("--exp-frac", "0")
        self.assertTrue(all("stuck" in r["questions"]["action"]["criteria"] for r in train if not done(r)))


class Weights(unittest.TestCase):
    def test_terminal_copies(self):
        one, dev1 = build()
        three, dev3 = build("--terminal-copies", "3")
        self.assertGreater(sum(map(done, one)), 0)
        self.assertEqual(sum(map(done, three)), 3 * sum(map(done, one)))
        self.assertEqual(sum(not done(r) for r in three), sum(not done(r) for r in one))
        self.assertEqual(dev1, dev3)

    def test_cap_per_class(self):
        def most(recs):
            return max(Counter((r["state"]["goal"], B.action_class(r)) for r in recs).values())
        self.assertGreater(most(build()[0]), 2)  # a set goal taps three times: Settings, the page, the switch
        self.assertLessEqual(most(build("--cap-per-class", "2")[0]), 2)

    def test_capped_keeps_path_order(self):
        recs = [{"questions": {"done": {"label": False}, "action": {"label": f"c{i}"}}} for i in range(5)]
        self.assertEqual([r["questions"]["action"]["label"] for r in B.capped(recs, 2)], ["c0", "c2"])
        self.assertIs(B.capped(recs, 0), recs)


class Messy(unittest.TestCase):
    def setUp(self):
        self.train, _ = build("--messy-frac", "1", "--loop", "exp")
        self.messy = [r for r in self.train if any("(back key)" in h for h in r["state"]["history"])]

    def test_ends_done_with_a_well_formed_history(self):
        self.assertGreater(len(self.messy), 0)
        self.assertEqual(sum(map(done, self.train)) - sum(map(done, build("--loop", "exp")[0])), len(self.messy))
        for r in self.messy:
            self.assertTrue(done(r))
            h = r["state"]["history"]
            steps = [int(HISTORY.match(x).group(1)) for x in h]  # each line in eval.py's format
            self.assertEqual(steps, list(range(r["state"]["step"] - len(h), r["state"]["step"])))
            i = next(j for j, x in enumerate(h) if x.endswith("(back key)"))
            self.assertTrue(h[i - 1].endswith("(tap)"))  # the wrong turn, then its back
            self.assertTrue(any(n in h[i - 1] for n in (APPS, STORAGE)), h[i - 1])

    def test_no_held_out_page(self):
        train, dev = build("--messy-frac", "1", "--terminal-copies", "2", "--loop", "exp")
        for r in train + dev:
            self.assertNotIn(r["state"]["window_title"], B.HOLDOUT_PAGES)
            self.assertFalse(any(PROFILE in h for h in r["state"]["history"]), r["state"]["history"])


class DevPages(unittest.TestCase):
    OPTS = (("--loop", "exp"), ("--messy-frac", "1"), ("--terminal-copies", "3"), ("--cap-per-class", "1"))

    def test_dev_ignores_train_only_options(self):
        _, dev = build(held="Sounds")
        self.assertTrue(dev)
        for opts in self.OPTS + (sum(self.OPTS, ()),):
            self.assertEqual(untied(build(*opts, held="Sounds")[1]), untied(dev), opts)

    def test_no_train_record_on_or_through_a_dev_page(self):  # Sounds is the only sibling of Display & touch
        for opts in self.OPTS + ((),):
            train, _ = build(*opts, held="Sounds")
            self.assertTrue(train)
            for r in train:
                self.assertNotEqual(r["state"]["window_title"], "Sounds")
                self.assertFalse(any(STORAGE in h for h in r["state"]["history"]), r["state"]["history"])

    def test_wrong_turn_skips_dev_pages_with_the_same_draws(self):
        class Always(random.Random):  # a wrong turn after every tap
            def random(self):
                return 0.0
        search = [{"base": "Settings", "scroll": 0}, {"base": "Search settings", "scroll": 0}]
        screens = world() + [{"path": search, "title": "Search", "app": "com.android.settings",
                              "layouts": [lay("display", "Search")]}]
        tgts, by_path = B.targets(screens)
        t = next(t for t in tgts if t["kind"] == "open" and t["page"] == "Display & touch")
        seen = set()
        for seed in range(8):
            plain, avoided = Always(seed), Always(seed)
            seen |= {r["state"]["window_title"] for r in B.records_for("open display", t, screens, by_path, True,
                                                                        plain)}
            recs = B.records_for("open display", t, screens, by_path, True, avoided, avoid={"Sounds"})
            self.assertEqual(plain.getstate(), avoided.getstate())  # dev targets after this one draw the same
            backs = [r["state"]["window_title"] for r in recs if B.action_class(r) == "back"]
            self.assertEqual(backs, ["Search"])
        self.assertIn("Sounds", seen)  # without avoid the draws do pick the dev page


class PagesOf(unittest.TestCase):
    def test_closes_the_file(self):
        with tempfile.TemporaryDirectory() as d, warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", ResourceWarning)
            (Path(d) / "dev.jsonl").write_text(json.dumps({"state": {"window_title": "Sounds"},
                                                           "questions": {"done": {"label": True}}}) + "\n")
            self.assertEqual(B.pages_of(Path(d) / "dev.jsonl"), {"Sounds"})
        self.assertFalse([x for x in w if issubclass(x.category, ResourceWarning)])


if __name__ == "__main__":
    unittest.main()
