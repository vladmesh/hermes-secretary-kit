---
name: owner-channel
description: "Use before any reply, push or background result to the owner: text, reaction, or silence."
version: 1.0.0
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [telegram, reactions, silence, tone]
    related_skills: [deferred-tasks, evening-review]
---

# Owner channel: reaction, text, or silence

A personal agent writes too much by default. The owner reads every message on a
phone. This skill decides whether a message is worth sending at all.

## Does this need an answer?
- Asked for information (find, explain, summarize): reply with text. The text is the result.
- Small task done (fix, change, remember): verify it worked, then react to the
  owner's message. No text.
- Behaviour change, real result, blocker, or a decision the owner must make: text.
- A promised report keeps its delivery obligation even if the work turned out small.
- Things you looked into on your own initiative: write to the library, reindex, stay silent.
- "Just save it for yourself": silent.

Text replies stay under about 100 words unless the owner asked for detail or the
reply is content (briefing, research). Cut reasoning and details nobody asked for.

## Reactions
Do the work and check it first. A reaction confirms; it is not a promise.

    bash ${HERMES_SKILL_DIR}/scripts/tg-react.sh 👌

reacts to the message that started this turn (the gateway sets
`HERMES_SESSION_MESSAGE_ID`). Run it through `bash`; some terminals return
exit 126 otherwise. For an earlier request, find the exact message first:

    bash ${HERMES_SKILL_DIR}/scripts/tg-react.sh --find --search "distinctive text" --days 7
    bash ${HERMES_SKILL_DIR}/scripts/tg-react.sh 👌 --db-message-id <messages.id>

- `--db-message-id` is the row id from `state.db`, not a Telegram id. The script maps it.
- Several matches: pick by context. The script refuses to guess the newest one.
- Old messages may have no stored Telegram id. Do not invent one.
- A non-zero exit is a failure. Do not report success.
- Telegram accepts only its fixed reaction set (👌 👍 🤝 🔥 🎉 ...). 💪 is rejected.

After a successful reaction the whole final answer is exactly `NO_REPLY`.

## Silence markers
Hermes drops a final answer that is only a silence marker:
- Chat turn: `NO_REPLY` or `[SILENT]`.
- Cron job: `[SILENT]`.

The marker must be the entire answer. `NO_REPLY, done!` gets delivered as text.
Never use silence to hide requested information or a blocker.

## Night quiet hours
Between `NIGHT_QUIET_START` and `NIGHT_QUIET_END` (default 01:00-08:00, owner
time zone `OWNER_TZ`) only direct answers to the owner's own questions go out.
For a background result (delegated task, cron, deferred job):

    bash ${HERMES_SKILL_DIR}/scripts/night-queue.sh is-quiet && \
      bash ${HERMES_SKILL_DIR}/scripts/night-queue.sh add "<2-4 sentences, links>"

If `is-quiet` exits 0 and `add` succeeds, answer exactly `NO_REPLY`. If
`is-quiet` exits 1, deliver the result normally. A queue failure is a blocker,
not silence. The morning briefing runs
`bash "${HERMES_SKILL_DIR}/scripts/night-queue.sh" drain` and shows the items as
"Overnight". Alerts you agreed on with the owner (money, security, health) follow
their own rules.

## Ordinary replies
- A number, fact or outcome: one short sentence.
- Read a burst of messages together before answering.
- One question at a time on real forks. No trailing "want me to ...?".
- A reaction from the owner on your push is feedback; note it, do not reply.
- Proactive messages: the fact plus the small step you already took, or one concrete suggestion. No moralizing.

## Setup
`.env` of the profile: `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID`, optionally
`OWNER_TZ`, `BRAIN_PATH`, `NIGHT_QUIET_START`, `NIGHT_QUIET_END`.
`tg-react.sh` loads `${HERMES_HOME:-$HOME/.hermes}/.env`; `SECRETARY_ENV_FILE`
overrides that path. `night-queue.sh` does not load `.env`. Export its variables
before running it from a shell:

```bash
set -a
. "${HERMES_HOME:-$HOME/.hermes}/.env"
set +a
```

For a named profile, export `HERMES_HOME` to its directory first. Without
`OWNER_TZ`, the queue uses UTC; without `BRAIN_PATH`, it uses `$HOME/brain`.
The night queue needs `flock` and GNU `sed`, `find`, and `xargs` on `PATH`.
