import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "brain-template"


class Reindex(unittest.TestCase):
    def run_reindex(self, root, *args):
        return subprocess.run([sys.executable, str(TEMPLATE / "reindex.py"), "--root", str(root), *args],
                              capture_output=True, text=True)

    def test_template_indexes_are_current(self):
        self.assertEqual(self.run_reindex(TEMPLATE, "--check").returncode, 0)

    def test_new_note_shows_up_and_rerun_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "brain"
            shutil.copytree(TEMPLATE, root)
            (root / "facts" / "coffee.md").write_text(
                "---\nname: coffee\ndescription: Owner drinks flat white\ntype: fact\n"
                "tags: [food]\nupdated: 2026-01-20\n---\nNo sugar.\n")
            self.assertEqual(self.run_reindex(root, "--check").returncode, 1)
            self.assertEqual(self.run_reindex(root).returncode, 0)
            self.assertIn("facts/coffee.md - Owner drinks flat white", (root / "INDEX.md").read_text())
            self.assertIn("[coffee](coffee.md)", (root / "facts" / "_index.md").read_text())
            self.assertEqual(self.run_reindex(root, "--check").returncode, 0)

    def test_note_without_frontmatter_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "facts").mkdir()
            (root / "facts" / "raw.md").write_text("# Wifi router\nmodel X\n")
            self.assertEqual(self.run_reindex(root).returncode, 0)
            self.assertIn("facts/raw.md - Wifi router", (root / "INDEX.md").read_text())


if __name__ == "__main__":
    unittest.main()
