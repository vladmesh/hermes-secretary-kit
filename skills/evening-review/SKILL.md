---
name: evening-review
description: "Use when running the evening check-in or when the owner answers it; also for weekly and monthly summaries."
version: 1.0.0
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [review, journal, habits]
    related_skills: [brain, owner-channel, deferred-tasks]
---

# Evening review

A daily cron job asks the owner how the day went, records the answer in the
journal, and builds weekly and monthly summaries from those records.

## Setup
```bash
hermes cron create "30 22 * * *" "$(cat ${HERMES_SKILL_DIR}/templates/evening-review-prompt.md)" \
  --name "Evening review" --skill evening-review --skill brain --deliver telegram
```
Adjust the time. `install.sh --with-cron` runs the same command for you.

## Asking
Build one compact message with every open item, not one question per turn:
1. Today's block from `journal/notes.md` (`### For YYYY-MM-DD`).
2. Habits and targets from `facts/habits.md` for the review date. Read the target,
   do not hardcode it. On a rest day, skip habit questions.
3. Skip anything already discussed today in the owner chat (check session_search
   or the chat context passed to the job). State its status instead of asking again.
4. Skip anything a data source already answers (step counter, screen time). If a
   source is stale or empty, say so; missing data is "no data", not zero.

Silence is not a reason to ask again. The morning briefing does not repeat the questions.

## When the owner answers
1. Real time: `TZ=$OWNER_TZ date`. Late answers after midnight belong to the
   previous day.
2. Update `journal/notes.md`: tick confirmed items, keep partial ones open, add
   new plans the owner mentions. Move items to another day only if the owner says so.
3. Write `journal/YYYY-MM-DD-day-review.md`:
   ```
   ---
   name: YYYY-MM-DD-day-review
   description: Day review YYYY-MM-DD - <one-line gist>
   type: journal
   tags: [day-review]
   updated: YYYY-MM-DD
   ---
   Done: ...
   Not done: ...
   Note: one or two sentences.
   ```
   Then `python3 $BRAIN_PATH/reindex.py`. Week and month summaries are built from
   these files; without them the summaries are empty.
4. Reply briefly, no tables: what got done (plans first), numbers, a two-line take.

## Week and month
On Sunday (week) and the last day of the month (month), the summary is owed
once the owner answers the evening review, even partially. Do not ask "want a
summary?". Do not send it before the answer.
1. Read the period's `*-day-review.md` files and `journal/notes.md`.
2. Count habits from the day reviews, not from the plan list.
3. Write `journal/YYYY-MM-DD-week-review.md` (or `month-review`), reindex.
4. Put the period heading in the first line of the reply: `Week 2026-01-12 - 2026-01-18`.
   Unknown values are marked unknown; do not hold the report until everything is filled.

If delivery fails, note the blocker in `journal/notes.md` under `## Open` so the
next run sees it.
