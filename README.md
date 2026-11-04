# hermes-secretary-kit

Skills and scripts that turn [Hermes Agent](https://github.com/NousResearch/hermes-agent)
into a personal secretary you talk to in Telegram. Extracted from a setup that has
run daily for one owner since September 2026, with personal data removed.

What you get:

- **brain**: long-term memory as plain markdown files with a generated index, so the
  agent finds a note in two or three reads instead of loading everything.
- **owner-channel**: rules for when to reply with text, when to put a reaction on the
  owner's message, and when to stay silent. Includes `tg-react.sh` and a night queue
  for results that arrive during quiet hours.
- **deferred-tasks**: "remind me tomorrow at 9", "check the deploy in an hour and tell me"
  turned into Hermes cron jobs with correct time zones and self-contained prompts.
- **evening-review**: a daily check-in that records the day in the journal and builds
  weekly and monthly summaries from those records.

## How it differs from a stock agent

| | Stock Hermes agent | With this kit |
|---|---|---|
| Memory | `MEMORY.md` in the prompt, size-limited | plus a markdown library of any size, read through an index |
| Small task done | a paragraph saying it is done | a 👌 reaction on your message |
| Background result at 3 a.m. | a message at 3 a.m. | queued, shown in the morning briefing |
| "Tell me tomorrow" | often answered now or forgotten | a cron job, with `next_run_at` checked against your time zone |
| "Check and report back" | one-shot check, silently dropped if not ready | repeats until done or the deadline, then reports either way |
| End of day | nothing | one short question, a journal entry, weekly and monthly summaries |

## Install

Requirements: Hermes Agent with the Telegram gateway configured, Python 3.10+, bash, `flock`.
The night queue also uses GNU `sed`, `find`, and `xargs`; on macOS, put those GNU tools on `PATH`.

```bash
git clone https://github.com/vladmesh/hermes-secretary-kit
cd hermes-secretary-kit
HERMES_HOME=~/.hermes BRAIN_PATH=~/brain ./install.sh --with-cron
```

`install.sh` copies the four skills to `$HERMES_HOME/skills/secretary-kit/`, replacing
those skill directories on every run. It copies the memory template into
`$BRAIN_PATH` only if `$BRAIN_PATH/INDEX.md` does not exist; other existing files
do not prevent copying and may be overwritten. It adds `BRAIN_PATH`,
`OWNER_CHAT_ID`, and `OWNER_TZ` to `$HERMES_HOME/.env` only if their assignments
are missing. Existing values, even empty ones, are left unchanged.
`HERMES_HOME` defaults to `~/.hermes`; `BRAIN_PATH` defaults to `~/brain`.
With `--with-cron` it also creates the evening review job on every run, without
checking for an existing job. `REVIEW_TIME` defaults to `30 22 * * *`. For a named
profile set `HERMES_HOME=~/.hermes/profiles/<name>` and `HERMES_PROFILE=<name>`.

Fill in `$HERMES_HOME/.env`:

```
TELEGRAM_BOT_TOKEN=...    # already there if the gateway works
OWNER_CHAT_ID=...         # your Telegram user id; the scripts refuse any other chat
OWNER_TZ=Europe/Lisbon    # also set `timezone:` in config.yaml to the same value
BRAIN_PATH=/home/you/brain
```

Then restart the gateway (`hermes gateway restart`; use `hermes -p <name> gateway restart`
for a named profile). Delete the sample notes in `$BRAIN_PATH`; they are fictional
and exist to show the format. Keep `facts/habits.md` and `journal/notes.md` with
your own habits and plans; the evening review reads both. Re-run `reindex.py`
after deleting or replacing notes.

If you would rather keep the skills in this checkout, point Hermes at it instead of
running the installer:

```yaml
# config.yaml
skills:
  external_dirs:
    - /path/to/hermes-secretary-kit/skills
```

This only exposes the skills. For a new library, copy `brain-template/.` into
`$BRAIN_PATH` and fill in the profile `.env` as above.

## How memory works

```
 always in prompt        read first           read on demand        one at a time
+------------------+   +-------------+   +----------------------+   +---------------------+
| MEMORY.md        |   | INDEX.md    |   | facts/_index.md      |   | facts/home-server.md|
| USER.md          |-->| one line    |-->| people/_index.md     |-->| people/maria-...md  |
| (Hermes profile) |   | per note    |   | projects/_index.md   |   | journal/2026-...md  |
+------------------+   +-------------+   | journal/_index.md    |   +---------------------+
                              ^          +----------------------+             |
                              |                     ^                         |
                              +------ reindex.py ---+---- frontmatter --------+
```

Every note is a markdown file with frontmatter:

```markdown
---
name: home-server
description: Home server - what runs there, how to reach it, what not to touch
type: fact
tags: [infra]
updated: 2026-01-12
---
Small VPS `box-1` (Debian 12). Runs the agent and nightly backups.
```

`reindex.py` reads the frontmatter of `.md` files directly in `facts/`, `people/`,
`projects/`, and `journal/`, excluding `_index.md`. It rewrites `INDEX.md` and
each section's `_index.md`. It has no dependencies and is safe to run after every
write. The agent searches the `description` line, so that line carries the facts
people ask about.

`journal/notes.md` holds dated plans (`### For 2026-01-15`) that the evening review
checks, and open topics that a morning briefing can surface one at a time.

## Example

```
You:   remind me to send invoices to Maria tomorrow morning
Agent: 👌  (reaction; a job is set for 09:00 Lisbon time)

You:   also bump the backup retention to 14 days
Agent: 👌  (after editing the config and checking the next run)

       ... 03:40, a delegated task finishes. Nothing is sent.

Agent: Morning. 3 meetings, first at 10:30.
       Overnight: backup script now keeps 14 days, first run passed (log: /var/log/backup.log).
       Today: send Q4 invoices to Maria.

Agent: Evening check: invoices to Maria sent? Spanish done? Reading: 0 of 20 pages so far.
You:   invoices yes, spanish yes, read 25
Agent: Logged. Plans 2/2, habits 3/3. Steps 7.8k.
```

## Layout

```
brain-template/        memory library skeleton with fictional notes and reindex.py
skills/brain/          how to read, write and close notes
skills/owner-channel/  reply, react or stay silent; scripts/tg-react.sh, scripts/night-queue.sh
skills/deferred-tasks/ reminders and conditional promises on Hermes cron
skills/evening-review/ daily check-in, journal entry, week and month summaries
tests/                 unittest for install.sh, reindex.py, tg_react.py, night-queue.sh
install.sh
```

## Development

Install `shellcheck` to run the lint command below.

```bash
python3 -m unittest discover -s tests
shellcheck install.sh skills/owner-channel/scripts/*.sh
python3 brain-template/reindex.py --check
```

## Limits

- Reactions and the night queue are written for Telegram. Other platforms get the
  silence rules but not `tg-react.sh`.
- `tg-react.sh --find` reads the Hermes `state.db` schema (`sessions`, `messages`).
  If Hermes changes that schema, the lookup breaks; the reaction on the current
  message still works.
- The evening review asks only about plans and habits in the library. Health,
  screen time and similar sources need your own collector scripts.

## License

MIT
