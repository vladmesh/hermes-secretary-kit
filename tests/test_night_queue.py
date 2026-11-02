import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/owner-channel/scripts/night-queue.sh"


class NightQueue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = dict(os.environ, BRAIN_PATH=self.tmp.name, HERMES_HOME=self.tmp.name, OWNER_TZ="UTC")

    def run_q(self, *args, **env):
        return subprocess.run(["bash", str(SCRIPT), *args], env={**self.env, **env},
                              capture_output=True, text=True)

    def test_add_peek_drain(self):
        self.assertEqual(self.run_q("add", "build finished\nlink: example").returncode, 0)
        peek = self.run_q("peek").stdout
        self.assertIn("build finished", peek)
        self.assertIn("  link: example", peek)
        self.assertIn("build finished", self.run_q("drain").stdout)
        self.assertEqual(self.run_q("peek").stdout, "")
        self.assertTrue(list((Path(self.tmp.name) / "night-queue-backup").glob("night-results-*.md")))

    def test_quiet_window_wraps_midnight(self):
        inside = self.run_q("is-quiet", NIGHT_QUIET_START="00:00", NIGHT_QUIET_END="23:59")
        outside = self.run_q("is-quiet", NIGHT_QUIET_START="00:00", NIGHT_QUIET_END="00:00")
        self.assertEqual(inside.returncode, 0)
        self.assertEqual(outside.returncode, 1)

    def test_empty_add_rejected(self):
        self.assertEqual(self.run_q("add", "  ").returncode, 2)


if __name__ == "__main__":
    unittest.main()
