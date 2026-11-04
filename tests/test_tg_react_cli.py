import importlib.util
import io
import json
import os
import sqlite3
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "skills/owner-channel/scripts/tg_react.py"
OWNER = "100000001"  # fictional chat id
TOKEN = "123456:fictional-secret"


class ReactionCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "state.db"
        self.env = {"HOME": self.tmp.name, "HERMES_HOME": self.tmp.name,
                    "OWNER_CHAT_ID": OWNER, "TELEGRAM_BOT_TOKEN": TOKEN}
        # set_reaction captures urlopen as a default argument, so patch before loading.
        with patch("urllib.request.urlopen", side_effect=AssertionError("Unexpected network request")) as opener:
            self.opener = opener
            spec = importlib.util.spec_from_file_location("tg_react_cli", SCRIPT)
            self.m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.m)

    def run_main(self, *args, **env):
        out = io.StringIO()
        with patch.dict(os.environ, {**self.env, **env}, clear=True), \
                patch("sys.argv", [str(SCRIPT), *args]), patch("sys.stdout", out):
            code = self.m.main()
        return code, out.getvalue()

    def assert_result(self, result, code, body):
        self.assertEqual(result, (code, json.dumps(body, ensure_ascii=False) + "\n"))

    def test_missing_owner_chat_id(self):
        self.env.pop("OWNER_CHAT_ID")
        self.assert_result(self.run_main("👌", "--message-id", "71"), 1,
                           {"ok": False, "error": "OWNER_CHAT_ID is not set"})

    def test_explicit_non_owner_chat_id(self):
        self.assert_result(self.run_main("👌", "--message-id", "71", "--chat-id", "100000002"), 1,
                           {"ok": False, "error": "Only the owner chat is supported"})

    def test_find_prints_json_rows_without_token_or_emoji(self):
        self.env.pop("TELEGRAM_BOT_TOKEN")
        with sqlite3.connect(self.db) as d:
            d.executescript(
                "CREATE TABLE sessions(id TEXT, source TEXT, chat_id TEXT);"
                "CREATE TABLE messages(id INTEGER, session_id TEXT, role TEXT, content TEXT,"
                " timestamp REAL, platform_message_id TEXT);"
            )
            d.execute("INSERT INTO sessions VALUES(?,?,?)", ("s", "telegram", OWNER))
            d.executemany("INSERT INTO messages VALUES(?,?,?,?,?,?)", [
                (1, "s", "user", "fix the button 👌", 900, "71"),
                (2, "s", "user", "fix the button again 👌", 950, "72"),
            ])
        with patch.object(self.m.time, "time", return_value=1000):
            result = self.run_main("--find", "--search", "button", "--db", str(self.db))
        self.assert_result(result, 0, [
            {"db_message_id": 2, "message_id": "72", "session_id": "s",
             "timestamp": 950.0, "content": "fix the button again 👌"},
            {"db_message_id": 1, "message_id": "71", "session_id": "s",
             "timestamp": 900.0, "content": "fix the button 👌"},
        ])

    def test_session_message_id_fallback_and_success_payload(self):
        def opener(req, timeout):
            self.assertEqual(req.full_url, "https://api.telegram.org/bot" + TOKEN + "/setMessageReaction")
            self.assertEqual(req.get_method(), "POST")
            self.assertEqual(req.get_header("Content-type"), "application/json")
            self.assertEqual(timeout, 20)
            self.assertEqual(json.loads(req.data), {
                "chat_id": int(OWNER), "message_id": 71,
                "reaction": [{"type": "emoji", "emoji": "👌"}],
            })
            return io.BytesIO(b'{"ok":true,"result":true}')
        self.opener.side_effect = opener
        self.assert_result(self.run_main("👌", HERMES_SESSION_MESSAGE_ID="71"), 0,
                           {"ok": True, "chat_id": OWNER, "message_id": "71", "emoji": "👌"})
        self.assertFalse(self.db.exists())

    def test_explicit_message_id_overrides_session(self):
        self.opener.side_effect = lambda *a, **kw: io.BytesIO(b'{"ok":true}')
        self.assert_result(self.run_main("👌", "--message-id", "72", HERMES_SESSION_MESSAGE_ID="71"), 0,
                           {"ok": True, "chat_id": OWNER, "message_id": "72", "emoji": "👌"})

    def test_missing_message_id(self):
        self.assert_result(self.run_main("👌"), 1,
                           {"ok": False, "error": "No source message id; find the original owner message first"})

    def test_missing_emoji(self):
        self.assert_result(self.run_main("--message-id", "71"), 1,
                           {"ok": False, "error": "Emoji is required unless --find"})

    def test_fresh_database_reports_missing_schema(self):
        with sqlite3.connect(self.db):
            pass
        before = self.db.read_bytes()
        self.assert_result(self.run_main("--find", "--db-message-id", "1", "--db", str(self.db)), 1,
                           {"ok": False, "error": "no such table: messages"})
        self.assertEqual(self.db.read_bytes(), before)

    def test_missing_database_is_not_created(self):
        self.assert_result(self.run_main("--find", "--db-message-id", "1", "--db", str(self.db)), 1,
                           {"ok": False, "error": "unable to open database file"})
        self.assertFalse(self.db.exists())

    def test_opener_exception_prints_sanitized_error(self):
        def opener(req, timeout):
            raise urllib.error.URLError(req.full_url)
        self.opener.side_effect = opener
        result = self.run_main("👌", "--message-id", "71")
        self.assert_result(result, 1,
                           {"ok": False, "error": "Telegram reaction request failed (URLError)"})
        self.assertNotIn(TOKEN, result[1])

    def test_telegram_rejection_prints_error(self):
        self.opener.side_effect = lambda *a, **kw: io.BytesIO(
            b'{"ok":false,"description":"Bad Request: reaction not allowed"}'
        )
        self.assert_result(self.run_main("👌", "--message-id", "71"), 1,
                           {"ok": False, "error": "Telegram rejected reaction: Bad Request: reaction not allowed"})


if __name__ == "__main__":
    unittest.main()
