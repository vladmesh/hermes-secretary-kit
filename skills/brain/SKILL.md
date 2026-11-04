---
name: brain
description: "Use when the owner says remember/what do you know about, or you need context on people, projects, past decisions. Markdown memory with a generated index."
version: 1.0.0
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [memory, markdown, notes]
    related_skills: [evening-review, deferred-tasks]
---

# brain: memory library

Location: `$BRAIN_PATH` (set it in the profile `.env`). Format and sections are
described in `$BRAIN_PATH/README.md`.

## Reading
1. `cat $BRAIN_PATH/INDEX.md`. One line per note.
2. Need a whole section: `cat $BRAIN_PATH/<section>/_index.md`.
3. Need a note: `cat` that one file. Do not read the library end to end.
4. Nothing found: `grep -ril "<word>" $BRAIN_PATH`, then session_search.

Before telling the owner "X is still pending", check X against the live source
(billing page, API, file). A note shows the state on its `updated` date, not now.

## Writing
- New note: `<section>/<kebab-slug>.md` with frontmatter (`name`, one-line
  `description`, `type`, `tags`, `updated` = today) and a short body. Link other
  notes as `[[slug]]`.
- Refining a fact: edit the same file and bump `updated`. Before creating, check
  `grep -rl "name: <slug>" "$BRAIN_PATH"` and similar descriptions in INDEX.md.
- Outdated: rewrite or delete. Do not keep a history of contradictions.
- After any write: `python3 $BRAIN_PATH/reindex.py`.

## Closing is also a write
New things get written down; finished things often do not. When the chat shows a
noted item changed ("paid", "rotated the key", "no longer needed"), update the
note in the same turn: strike the plan, rewrite the fact, bump `updated`,
reindex. Do not wait for the end of the conversation; context gets compressed.

## Owner plans: `journal/notes.md`
When the owner states an intention ("tomorrow I need to", "this week"), add it
right away under `## Owner plans` as `### For YYYY-MM-DD` with checkboxes.
The morning briefing shows today's block; the evening review checks it.
- `[x]` only for confirmed completion. Partial or unknown stays open.
- Do not carry a plan to the next day unless the owner says so.
- Processed dated blocks move to `## Plan history` at the end of the file,
  after `## Closed`, so reminders do not pick them up again.

Topics and ideas go under `## Open` as `### Title`, a line `Appeared: date,
source`, then why it matters. Done topics move to `## Closed`. In a briefing,
surface one relevant topic, not the whole list.

## Sections
- `facts/` stable facts: servers, accounts, habits, agreements.
- `people/` one file per person.
- `projects/` one file per project: what it is, current state, next step.
- `journal/` dated notes `YYYY-MM-DD-topic.md`, day reviews, `notes.md`.

## Never store
Secrets, tokens, passwords. Anything that already lives in code or git history.
