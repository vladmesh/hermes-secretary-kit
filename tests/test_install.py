import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "install.sh"
SKILLS = ("brain", "owner-channel", "deferred-tasks", "evening-review")
HERMES_STUB = '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$HERMES_ARGS_FILE"\n'


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.hermes_home = root / "hermes"
        self.brain = root / "brain"
        self.bin = root / "bin"
        self.bin.mkdir()
        self.args_file = root / "hermes-args"
        env = {k: v for k, v in os.environ.items() if k not in ("HERMES_PROFILE", "REVIEW_TIME")}
        self.env = dict(env, HOME=str(root / "home"), HERMES_HOME=str(self.hermes_home),
                        BRAIN_PATH=str(self.brain), HERMES_ARGS_FILE=str(self.args_file),
                        PATH=f"{self.bin}{os.pathsep}{env.get('PATH', '')}")

    def run_install(self, *args, **env):
        res = subprocess.run(["bash", str(SCRIPT), *args], env={**self.env, **env},
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res

    def stub_hermes(self):
        stub = self.bin / "hermes"
        stub.write_text(HERMES_STUB)
        stub.chmod(0o755)

    def test_skills_copied_and_scripts_executable(self):
        self.run_install()
        skills_dir = self.hermes_home / "skills/secretary-kit"
        self.assertEqual(sorted(p.name for p in skills_dir.iterdir()), sorted(SKILLS))
        for skill in SKILLS:
            self.assertTrue((skills_dir / skill / "SKILL.md").is_file(), skill)
        scripts = list((skills_dir / "owner-channel/scripts").iterdir())
        self.assertTrue(scripts)
        for script in scripts:
            self.assertTrue(os.access(script, os.X_OK), script)

    def test_brain_template_copied_and_indexed_when_empty(self):
        self.brain.mkdir()
        res = self.run_install()
        self.assertIn("brain template ->", res.stdout)
        self.assertTrue((self.brain / "INDEX.md").is_file())
        self.assertTrue((self.brain / "people/maria-costa.md").is_file())
        check = subprocess.run(["python3", str(self.brain / "reindex.py"), "--root", str(self.brain), "--check"],
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_existing_brain_left_untouched(self):
        self.brain.mkdir()
        (self.brain / "INDEX.md").write_text("my index\n")
        res = self.run_install()
        self.assertIn("left untouched", res.stdout)
        self.assertEqual(sorted(p.name for p in self.brain.iterdir()), ["INDEX.md"])
        self.assertEqual((self.brain / "INDEX.md").read_text(), "my index\n")

    def test_env_file_idempotent(self):
        self.run_install()
        self.run_install()
        lines = (self.hermes_home / ".env").read_text().splitlines()
        self.assertEqual(lines.count(f"BRAIN_PATH={self.brain}"), 1)
        self.assertEqual(lines.count("OWNER_CHAT_ID="), 1)
        self.assertEqual(lines.count("OWNER_TZ="), 1)
        self.assertEqual(len(lines), 3)

    def test_env_file_keeps_existing_values(self):
        self.hermes_home.mkdir()
        (self.hermes_home / ".env").write_text("OWNER_TZ=Europe/Lisbon\n")
        self.run_install()
        lines = (self.hermes_home / ".env").read_text().splitlines()
        self.assertIn("OWNER_TZ=Europe/Lisbon", lines)
        self.assertNotIn("OWNER_TZ=", lines)

    def test_no_cron_without_flag(self):
        self.stub_hermes()
        self.run_install()
        self.assertFalse(self.args_file.exists())

    def expected_cron_args(self):
        prompt = (ROOT / "skills/evening-review/templates/evening-review-prompt.md").read_text().rstrip("\n")
        return ["cron", "create", "30 22 * * *", *prompt.split("\n"),
                "--name", "Evening review", "--skill", "evening-review", "--skill", "brain",
                "--deliver", "telegram"]

    def test_with_cron_default_profile(self):
        self.stub_hermes()
        self.run_install("--with-cron")
        self.assertEqual(self.args_file.read_text().splitlines(), self.expected_cron_args())

    def test_with_cron_and_profile(self):
        self.stub_hermes()
        self.run_install("--with-cron", HERMES_PROFILE="work")
        self.assertEqual(self.args_file.read_text().splitlines(), ["-p", "work", *self.expected_cron_args()])

    def test_with_cron_custom_review_time(self):
        self.stub_hermes()
        self.run_install("--with-cron", REVIEW_TIME="0 21 * * *")
        self.assertEqual(self.args_file.read_text().splitlines()[2], "0 21 * * *")


if __name__ == "__main__":
    unittest.main()
