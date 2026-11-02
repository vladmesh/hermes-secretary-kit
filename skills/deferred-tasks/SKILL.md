---
name: deferred-tasks
description: "Use when asked to do something later: in N minutes, tomorrow at 9, every Monday, or 'check and report back'."
version: 1.0.0
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [cron, reminders, scheduling]
    related_skills: [owner-channel, brain]
---

# Deferred tasks

A promise about the future goes into Hermes cron. A promise kept only in the
conversation is lost when the session ends. "In a minute" still means a job.

## Creating a job
1. Read the real clock: `TZ=$OWNER_TZ date '+%Y-%m-%dT%H:%M:%S%:z'`. The session
   start time or an old message timestamp is not "now".
2. One-off: ISO timestamp with an explicit offset. "In N minutes" counts from now;
   "tomorrow at 09:00" is in the owner's zone with that date's DST offset.
   Recurring: a cron expression in the profile time zone (`timezone` in
   config.yaml). `0 9 * * *` stays as is; do not shift it to UTC by hand.
3. Write a self-contained prompt. The job does not see this chat. Include: what
   to do or check, where the data is, what counts as done, when to stay silent
   (`[SILENT]`), and the output format. Attach only the skills and toolsets it needs.
4. Create it, read back `next_run_at`, convert to the owner's zone, compare with
   the request. Fix mistakes before confirming.
5. Tell the owner the local time ("tomorrow 09:00") or "in N minutes".

```python
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
zone = ZoneInfo("Europe/Lisbon")  # OWNER_TZ
now = datetime.now(zone)
print((now + timedelta(minutes=10)).isoformat())
print(datetime.combine(now.date() + timedelta(days=1), time(9), zone).isoformat())
```

"Do it now" is never deferred. If the future step needs information from the
owner, get it before scheduling or write the condition into the prompt.

## Meetings
When the owner mentions a call or meeting and a calendar tool is connected,
create the event (1 hour by default) and a reminder job 10 minutes before.

## Conditional promises ("check and tell me", "if X then Y")
A plain one-shot job runs once; if the condition is not met yet, the promise
silently dies. Use a repeating job that owns the promise until it is closed:

- Schedule `every 30m` (or similar) with a hard deadline written in the prompt.
- The prompt checks the condition first. Not met and before the deadline: answer
  `[SILENT]`. Met: do the work, report, then remove its own job.
  Deadline passed: tell the owner it did not happen and why, then remove the job.
- Keep state between runs in the job notepad (`hermes cron notepad`), not in memory.
- For a cheap check, use `--monitor-script`: the agent runs only when the script
  output changes.
- Results meant for the morning briefing go to the night queue
  (owner-channel skill), not into an ad-hoc note.

## Finishing and cancelling
One-off jobs end by themselves. If the reason went away, remove the job
explicitly. `run` followed by an immediate `remove` kills the running work: let
it finish first.

Checklist before confirming: real current time, correct zone, self-contained
prompt, actual `next_run_at`, correct delivery target.
