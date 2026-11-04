import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/owner-channel/scripts/night-queue.sh"
TIMESTAMP = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
USAGE = (
    "Night quiet hours: background results that arrive between NIGHT_QUIET_START and\n"
    "NIGHT_QUIET_END are queued here instead of pinging the owner. The morning\n"
    'briefing drains the queue into an "Overnight" block.\n'
    '  night-queue.sh add "<text>"   append an item with a timestamp (multi-line ok)\n'
    "  night-queue.sh is-quiet       exit 0 inside the quiet window, 1 outside\n"
    "  night-queue.sh peek           print queued items without clearing\n"
    "  night-queue.sh drain          print queued items and clear the file (backup kept)\n"
)


class NightQueueCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        home = root / "home"
        home.mkdir()
        bin_dir = root / "bin"
        bin_dir.mkdir()
        date = bin_dir / "date"
        date.write_text(
            '#!/bin/sh\n'
            'if [ "$1" = "+%H:%M" ]; then\n'
            '  printf "%s\\n" "$FIXED_TIME"\n'
            'else\n'
            '  exec /bin/date "$@"\n'
            'fi\n'
        )
        date.chmod(0o700)
        self.env = {
            "HOME": str(home),
            "BRAIN_PATH": str(root / "brain"),
            "HERMES_HOME": str(root / "hermes"),
            "OWNER_TZ": "UTC",
            "PATH": str(bin_dir) + os.pathsep + os.defpath,
            "TMPDIR": self.tmp.name,
            "LC_ALL": "C",
            "FIXED_TIME": "22:00",
        }
        self.queue = root / "brain" / "journal" / "night-results.md"
        self.backup_dir = root / "hermes" / "night-queue-backup"

    def run_q(self, *args, **env):
        return subprocess.run(["bash", str(SCRIPT), *args], env={**self.env, **env},
                              capture_output=True, text=True)

    def test_missing_subcommand_prints_usage_to_stderr(self):
        result = self.run_q()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, USAGE)
        self.assertFalse(self.queue.exists())

    def test_unknown_subcommand_prints_usage_to_stderr(self):
        result = self.run_q("unknown-task-101")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, USAGE)
        self.assertFalse(self.queue.exists())

    def test_empty_drain_prints_nothing_and_creates_no_backup(self):
        for state in ("missing", "zero-byte"):
            with self.subTest(state=state):
                if state == "zero-byte":
                    self.queue.parent.mkdir(parents=True)
                    self.queue.write_text("")
                result = self.run_q("drain")
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")
                self.assertFalse(self.backup_dir.exists())
                if state == "missing":
                    self.assertFalse(self.queue.exists())
                else:
                    self.assertEqual(self.queue.read_text(), "")

    def test_several_adds_preserve_order_and_timestamps_in_peek(self):
        expected = ""
        for item in ("task-101 finished", "task-102 finished", "task-103 finished"):
            with self.subTest(item=item):
                added = self.run_q("add", item)
                self.assertEqual(added.returncode, 0)
                self.assertEqual(added.stdout, f"queued: {self.queue}\n")
                self.assertEqual(added.stderr, "")
                peek = self.run_q("peek")
                self.assertEqual(peek.returncode, 0)
                self.assertEqual(peek.stderr, "")
                last_line = peek.stdout.splitlines()[-1]
                match = re.fullmatch(rf"- \[({TIMESTAMP})\] {re.escape(item)}", last_line)
                self.assertIsNotNone(match)
                expected += f"- [{match.group(1)}] {item}\n"
                self.assertEqual(peek.stdout, expected)
        again = self.run_q("peek")
        self.assertEqual(again.returncode, 0)
        self.assertEqual(again.stdout, expected)
        self.assertEqual(again.stderr, "")

    def test_multiline_add_indents_every_continuation_line(self):
        item = "task-104 finished\nlink: example.invalid/task-104\n\n- owner-205 notified"
        added = self.run_q("add", item)
        self.assertEqual(added.returncode, 0)
        self.assertEqual(added.stdout, f"queued: {self.queue}\n")
        self.assertEqual(added.stderr, "")
        peek = self.run_q("peek")
        self.assertEqual(peek.returncode, 0)
        self.assertEqual(peek.stderr, "")
        self.assertRegex(
            peek.stdout,
            rf"\A- \[{TIMESTAMP}\] task-104 finished\n"
            r"  link: example\.invalid/task-104\n  \n  - owner-205 notified\n\Z",
        )

    def test_drain_matches_peek_and_backs_up_original_queue(self):
        for item in ("task-301 finished", "task-302 finished"):
            added = self.run_q("add", item)
            self.assertEqual(added.returncode, 0)
            self.assertEqual(added.stderr, "")
        peek = self.run_q("peek")
        self.assertEqual(peek.returncode, 0)
        self.assertEqual(peek.stderr, "")
        self.assertNotEqual(peek.stdout, "")
        original = self.queue.read_text()
        self.assertTrue(original.endswith(peek.stdout))
        drained = self.run_q("drain")
        self.assertEqual(drained.returncode, 0)
        self.assertEqual(drained.stdout, peek.stdout)
        self.assertEqual(drained.stderr, "")
        backups = list(self.backup_dir.glob("night-results-*.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)
        empty = self.run_q("peek")
        self.assertEqual(empty.returncode, 0)
        self.assertEqual(empty.stdout, "")
        self.assertEqual(empty.stderr, "")
        cleared = self.queue.read_text()
        self.assertNotEqual(cleared, original)
        drained_again = self.run_q("drain")
        self.assertEqual(drained_again.returncode, 0)
        self.assertEqual(drained_again.stdout, "")
        self.assertEqual(drained_again.stderr, "")
        self.assertEqual(list(self.backup_dir.glob("night-results-*.md")), backups)
        self.assertEqual(backups[0].read_text(), original)
        self.assertEqual(self.queue.read_text(), cleared)

    def test_wrapping_quiet_window_at_fixed_times(self):
        for now, expected in (
            ("21:59", 1),
            ("22:00", 0),
            ("23:59", 0),
            ("00:00", 0),
            ("06:59", 0),
            ("07:00", 1),
            ("12:00", 1),
        ):
            with self.subTest(now=now):
                result = self.run_q("is-quiet", FIXED_TIME=now,
                                    NIGHT_QUIET_START="22:00", NIGHT_QUIET_END="07:00")
                self.assertEqual(result.returncode, expected)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
