#!/usr/bin/env python3
"""Put a Telegram reaction on an exact owner message, or find that message.

Never guesses Telegram ids: a reaction goes either to the message that started
the current turn (HERMES_SESSION_MESSAGE_ID) or to a message found in the
Hermes session database and picked explicitly.

Environment:
    TELEGRAM_BOT_TOKEN        bot token (not needed for --find)
    OWNER_CHAT_ID             the only chat the script will touch
    HERMES_HOME               profile directory with state.db
    HERMES_SESSION_CHAT_ID    set by the Hermes gateway for the current turn
    HERMES_SESSION_MESSAGE_ID set by the Hermes gateway for the current turn
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path


def owner_chat() -> str:
    chat = os.environ.get("OWNER_CHAT_ID", "").strip()
    if not chat:
        raise ValueError("OWNER_CHAT_ID is not set")
    return chat


def find_messages(db_path, chat, owner, *, search=None, db_id=None, message_id=None,
                  session_id=None, days=7, now=None):
    """Owner's own Telegram messages matching the filters, newest first."""
    if str(chat) != str(owner):
        raise ValueError("Only the owner chat is supported")
    if not any((search, db_id, message_id)):
        raise ValueError("Provide --search, --db-message-id or --message-id")
    if days <= 0 or days > 365:
        raise ValueError("--days must be 1..365")
    clauses = ["s.source='telegram'", "s.chat_id=?", "m.role='user'", "m.platform_message_id IS NOT NULL"]
    params: list = [str(chat)]
    if search:
        clauses += ["instr(m.content, ?) > 0", "m.timestamp >= ?"]
        params += [search, (now if now is not None else time.time()) - days * 86400]
    if db_id:
        clauses.append("m.id=?")
        params.append(db_id)
    if message_id:
        clauses.append("m.platform_message_id=?")
        params.append(str(message_id))
    if session_id:
        clauses.append("m.session_id=?")
        params.append(session_id)
    query = (
        "SELECT m.id AS db_message_id, m.platform_message_id AS message_id, m.session_id,"
        " m.timestamp, m.content FROM messages m JOIN sessions s ON s.id=m.session_id WHERE "
        + " AND ".join(clauses)
        + " ORDER BY m.timestamp DESC, m.id DESC LIMIT 51"
    )
    with sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(query, params).fetchall()
    result, seen = [], set()
    for row in rows:
        item = dict(row)
        if not str(item["message_id"]).isdigit() or int(item["message_id"]) <= 0:
            continue
        text = item["content"] or ""
        # Internal events injected by plugins are stored as user turns; skip them.
        if "[INTERNAL BACKGROUND EVENT" in text or text.lstrip().startswith("[SYSTEM"):
            continue
        if item["message_id"] in seen:
            continue
        seen.add(item["message_id"])
        result.append(item)
    return result


def select_message(rows) -> int:
    if len(rows) != 1:
        raise ValueError(
            f"Expected one exact message, found {len(rows)}; use --find, inspect candidates, then --db-message-id"
        )
    return int(rows[0]["message_id"])


def set_reaction(token, chat, owner, message_id, emoji, opener=urllib.request.urlopen):
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set")
    if str(chat) != str(owner) or int(message_id) <= 0:
        raise ValueError("Invalid owner chat/message id")
    body = json.dumps(
        {"chat_id": int(chat), "message_id": int(message_id), "reaction": [{"type": "emoji", "emoji": emoji}]},
        ensure_ascii=False,
    ).encode()
    req = urllib.request.Request(
        "https://api.telegram.org/bot" + token + "/setMessageReaction",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with opener(req, timeout=20) as resp:
            result = json.load(resp)
    except Exception as exc:
        # urllib errors carry the URL, and the URL carries the token. Never print it.
        raise RuntimeError("Telegram reaction request failed (" + type(exc).__name__ + ")") from None
    if result.get("ok") is not True:
        raise RuntimeError("Telegram rejected reaction: " + str(result.get("description", "unknown error")))
    return {"ok": True, "chat_id": str(chat), "message_id": str(message_id), "emoji": emoji}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("emoji", nargs="?")
    p.add_argument("--find", action="store_true", help="print candidate messages as JSON, do not react")
    p.add_argument("--search", help="literal substring of the original message")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--db-message-id", type=int, help="messages.id from state.db (not a Telegram id)")
    p.add_argument("--message-id", help="Telegram message id")
    p.add_argument("--session-id")
    p.add_argument("--chat-id", default=os.environ.get("HERMES_SESSION_CHAT_ID"))
    p.add_argument("--db", type=Path, default=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "state.db")
    a = p.parse_args()
    try:
        owner = owner_chat()
        chat = a.chat_id or owner
        if chat != owner:
            raise ValueError("Only the owner chat is supported")
        mid = a.message_id
        if a.find or a.search or a.db_message_id or a.session_id:
            rows = find_messages(a.db, chat, owner, search=a.search, db_id=a.db_message_id,
                                 message_id=mid, session_id=a.session_id, days=a.days)
            if a.find:
                print(json.dumps(rows, ensure_ascii=False))
                return 0
            mid = select_message(rows)
        if not mid:
            mid = os.environ.get("HERMES_SESSION_MESSAGE_ID")
        if not mid:
            raise ValueError("No source message id; find the original owner message first")
        if not a.emoji:
            raise ValueError("Emoji is required unless --find")
        out = set_reaction(os.environ.get("TELEGRAM_BOT_TOKEN"), chat, owner, int(mid), a.emoji)
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except (ValueError, RuntimeError, sqlite3.Error) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
