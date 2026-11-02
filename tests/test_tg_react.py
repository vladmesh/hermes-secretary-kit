import importlib.util
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/owner-channel/scripts/tg_react.py"
spec = importlib.util.spec_from_file_location("tg_react", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

OWNER = "100000001"  # fictional chat id


class Reactions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "state.db"
        with sqlite3.connect(self.db) as d:
            d.executescript(
                "CREATE TABLE sessions(id TEXT, source TEXT, chat_id TEXT);"
                "CREATE TABLE messages(id INTEGER, session_id TEXT, role TEXT, content TEXT,"
                " timestamp REAL, platform_message_id TEXT);"
            )
            d.executemany("INSERT INTO sessions VALUES(?,?,?)",
                          [("s", "telegram", OWNER), ("other", "telegram", "12"), ("web", "cli", OWNER)])
            d.executemany("INSERT INTO messages VALUES(?,?,?,?,?,?)", [
                (1, "s", "user", "fix the button", 900, "71"),
                (2, "s", "user", "fix the button", 950, "72"),
                (3, "s", "assistant", "fix the button", 950, "73"),
                (4, "other", "user", "fix the button", 950, "74"),
                (5, "web", "user", "fix the button", 950, "75"),
                (6, "s", "user", "[INTERNAL BACKGROUND EVENT fix the button", 950, "76"),
                (7, "s", "user", "fix the button", 950, None),
                (8, "s", "user", "old one", 1, "78"),
            ])

    def find(self, **kw):
        return m.find_messages(self.db, OWNER, OWNER, **kw)

    def test_ambiguous_search_does_not_pick_newest(self):
        rows = self.find(search="fix", now=1000)
        self.assertEqual([r["message_id"] for r in rows], ["72", "71"])
        with self.assertRaises(ValueError):
            m.select_message(rows)

    def test_db_id_maps_to_telegram_id(self):
        self.assertEqual(m.select_message(self.find(db_id=1)), 71)

    def test_foreign_internal_and_missing_rejected(self):
        for i in [3, 4, 5, 6, 7, 99]:
            with self.assertRaises(ValueError):
                m.select_message(self.find(db_id=i))
        with self.assertRaises(ValueError):
            m.find_messages(self.db, "12", OWNER, db_id=4)

    def test_search_is_literal_and_time_bounded(self):
        self.assertEqual(self.find(search="%", now=1000), [])
        self.assertEqual(self.find(search="old one", now=1000000, days=1), [])

    def test_payload_and_success(self):
        def opener(req, timeout):
            body = json.loads(req.data)
            self.assertEqual(body["message_id"], 71)
            self.assertEqual(body["reaction"][0]["emoji"], "👌")
            return io.BytesIO(b'{"ok":true}')
        self.assertTrue(m.set_reaction("fake", OWNER, OWNER, 71, "👌", opener)["ok"])

    def test_failure_is_not_success_and_hides_token(self):
        def bad(req, timeout):
            raise RuntimeError(req.full_url)
        with self.assertRaises(RuntimeError) as ctx:
            m.set_reaction("secret-token", OWNER, OWNER, 71, "👌", bad)
        self.assertNotIn("secret-token", str(ctx.exception))
        with self.assertRaises(RuntimeError):
            m.set_reaction("fake", OWNER, OWNER, 71, "👌",
                           lambda *a, **kw: io.BytesIO(b'{"ok":false,"description":"no"}'))


if __name__ == "__main__":
    unittest.main()
