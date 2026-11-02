---
name: home-server
description: Home server - what runs there, how to reach it, what not to touch
type: fact
tags: [infra]
updated: 2026-01-12
---
Small VPS `box-1` (Debian 12). Runs the agent, a Postgres for side projects and nightly backups.
Access: SSH alias `box-1` from the owner's laptop. Credentials live in the profile `.env`, never here.
Do not restart Postgres between 09:00 and 19:00 without asking: [[budget-tracker]] uses it.
