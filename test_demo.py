"""Offline tests for finetune/run/demo.py: the screen recorder is stopped even when the episode fails."""
import sys, unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent / "finetune" / "run"))
import demo as D  # noqa: E402


class RecordTest(unittest.TestCase):
    def test_recorder_stopped_when_episode_raises(self):
        proc = mock.Mock()

        def episode(model, task, args):
            D.ev.reset("snap")  # starts screenrecord, then the episode fails
            raise RuntimeError("device lost")

        orig_reset = D.ev.reset
        with mock.patch.object(D.ev, "episode", episode), mock.patch.object(D, "adb") as adb, \
                mock.patch.object(D.subprocess, "Popen", return_value=proc), mock.patch.object(D.time, "sleep"), \
                mock.patch.object(D.ev, "reset", lambda snap: None):
            with self.assertRaises(RuntimeError):
                D.record({"id": "t"}, Namespace(model="kev"), Path("/nonexistent"))
            self.assertIn(mock.call("shell", "pkill", "-INT", "screenrecord", timeout=10), adb.call_args_list)
            proc.wait.assert_called_once_with(timeout=20)
            self.assertFalse(any(c.args[:1] == ("pull",) for c in adb.call_args_list))
        self.assertIs(D.ev.reset, orig_reset)

    def test_hung_device_kills_recorder(self):
        proc = mock.Mock()

        def episode(model, task, args):
            D.ev.reset("snap")
            raise RuntimeError("device lost")

        def adb(*a, **kw):
            if "pkill" in a:  # the device hangs on the recorder stop
                raise D.subprocess.TimeoutExpired("adb", 10)

        with mock.patch.object(D.ev, "episode", episode), mock.patch.object(D, "adb", adb), \
                mock.patch.object(D.subprocess, "Popen", return_value=proc), mock.patch.object(D.time, "sleep"), \
                mock.patch.object(D.ev, "reset", lambda snap: None):
            with self.assertRaises(D.subprocess.TimeoutExpired):
                D.record({"id": "t"}, Namespace(model="kev"), Path("/nonexistent"))
            proc.kill.assert_called_once_with()

    def test_no_recorder_no_pkill(self):
        with mock.patch.object(D.ev, "episode", side_effect=RuntimeError("no reset")), \
                mock.patch.object(D, "adb") as adb:
            with self.assertRaises(RuntimeError):
                D.record({"id": "t"}, Namespace(model="kev"), Path("/nonexistent"))
            adb.assert_not_called()


if __name__ == "__main__":
    unittest.main()
