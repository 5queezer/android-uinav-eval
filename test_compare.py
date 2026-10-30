"""Offline test for finetune/compare.py's episode diagnostics (synthetic records)."""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "finetune"))
import compare as C  # noqa: E402


def rec(outcome, reached, task="t", final=None):
    """An episode whose steps 1.. were on the goal state or not as in `reached`; `final` is the reached flag of an
    unlogged last observation (the one after max_steps or the repeat-stuck one), as eval.episode leaves it."""
    seen = reached + ([final] if final is not None else [])
    first = next((i + 1 for i, x in enumerate(seen) if x), None)
    return {"task": task, "outcome": outcome, "first_reached_step": first,
            "step_log": [{"step": i + 1, "reached": x} for i, x in enumerate(reached)]}


class Metrics(unittest.TestCase):
    def test_counts(self):
        m = C.metrics([rec("success", [False, True]),
                       rec("max_steps", [True, False, False]),  # backed out of the goal
                       rec("uncertain", [False, True, True]),  # stayed but never said done
                       rec("wrong_answer", [True]),
                       rec("false_done", [False]),
                       rec("stuck", [False, False])])
        self.assertEqual((m["n"], m["success"], m["reached"]), (6, 1, 4))
        self.assertEqual((m["left"], m["no_stop"], m["reached_end"]), (1, 1, 0))
        self.assertEqual((m["wrong_answer"], m["false_done"]), (1, 1))

    def test_unlogged_final_observation(self):
        m = C.metrics([rec("max_steps", [False, False], final=True),  # reached only after the last action
                       rec("stuck", [False, True], final=True),  # repeat-stuck while on the goal
                       rec("max_steps", [True, False, True], final=True),  # came back and stayed to the end
                       rec("max_steps", [True, True], final=False)])  # left on the last action, unseen in the log
        self.assertEqual((m["reached"], m["reached_end"], m["no_stop"], m["left"]), (4, 1, 3, 0))

    def test_set_tasks_skipped(self):
        kinds = {"wifi_off": "set", "open_display": "open", "android_version": "info"}
        m = C.metrics([rec("max_steps", [True, False], task="wifi_off"),
                       rec("max_steps", [False], task="wifi_off", final=True),
                       rec("max_steps", [True, False], task="open_display"),
                       rec("uncertain", [True], task="android_version")], kinds)
        self.assertEqual((m["reached"], m["left"], m["no_stop"], m["reached_end"]), (4, 1, 1, 0))


if __name__ == "__main__":
    unittest.main()
