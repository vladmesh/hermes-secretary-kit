#!/usr/bin/env bash
# Night quiet hours: background results that arrive between NIGHT_QUIET_START and
# NIGHT_QUIET_END are queued here instead of pinging the owner. The morning
# briefing drains the queue into an "Overnight" block.
#   night-queue.sh add "<text>"   append an item with a timestamp (multi-line ok)
#   night-queue.sh is-quiet       exit 0 inside the quiet window, 1 outside
#   night-queue.sh peek           print queued items without clearing
#   night-queue.sh drain          print queued items and clear the file (backup kept)
set -euo pipefail
export TZ="${OWNER_TZ:-UTC}"
BRAIN="${BRAIN_PATH:-$HOME/brain}"
QUEUE="${NIGHT_QUEUE_FILE:-$BRAIN/journal/night-results.md}"
STATE_DIR="${HERMES_HOME:-$HOME/.hermes}"
BACKUP_DIR="${NIGHT_QUEUE_BACKUP_DIR:-$STATE_DIR/night-queue-backup}"
START="${NIGHT_QUIET_START:-01:00}"
END="${NIGHT_QUIET_END:-08:00}"
LOCK="${NIGHT_QUEUE_LOCK:-$STATE_DIR/night-queue.lock}"

header() {
  cat <<EOF
---
name: night-results
description: Night queue - background results held during quiet hours, drained by the morning briefing
type: journal
tags: [night-quiet, queue, briefing]
updated: $(date +%F)
---
# Night queue

Written by night-queue.sh. Do not edit by hand; the morning briefing clears it.

EOF
}

ensure() {
  mkdir -p "$(dirname "$QUEUE")"
  [[ -s "$QUEUE" ]] || header > "$QUEUE"
}

items() {
  # Everything from the first "- [" item line on, including continuation lines.
  awk 'f || /^- \[/{f=1; print}' "$QUEUE" 2>/dev/null || true
}

minutes() {
  local h=${1%%:*} m=${1##*:}
  echo $((10#$h * 60 + 10#$m))
}

case "${1:-}" in
  add)
    shift
    text="${*:-}"
    [[ -n "${text//[[:space:]]/}" ]] || { echo 'usage: night-queue.sh add "<text>"' >&2; exit 2; }
    mkdir -p "$(dirname "$LOCK")"
    exec 9>"$LOCK"
    flock 9
    ensure
    sed -i "s/^updated: .*/updated: $(date +%F)/" "$QUEUE"
    first=1
    while IFS= read -r line || [[ -n "$line" ]]; do
      if [[ $first == 1 ]]; then
        printf -- '- [%s] %s\n' "$(date '+%Y-%m-%d %H:%M')" "$line" >> "$QUEUE"
        first=0
      else
        printf '  %s\n' "$line" >> "$QUEUE"
      fi
    done <<< "$text"
    echo "queued: $QUEUE"
    ;;
  is-quiet)
    now=$(minutes "$(date +%H:%M)")
    s=$(minutes "$START")
    e=$(minutes "$END")
    if [[ $s -le $e ]]; then
      [[ $now -ge $s && $now -lt $e ]]
    else
      [[ $now -ge $s || $now -lt $e ]]
    fi
    ;;
  peek)
    items
    ;;
  drain)
    mkdir -p "$(dirname "$LOCK")"
    exec 9>"$LOCK"
    flock 9
    body=$(items)
    [[ -n "$body" ]] || exit 0
    mkdir -p "$BACKUP_DIR"
    cp "$QUEUE" "$BACKUP_DIR/night-results-$(date +%Y%m%dT%H%M%S).md"
    find "$BACKUP_DIR" -maxdepth 1 -name 'night-results-*.md' -printf '%T@ %p\n' \
      | sort -rn | tail -n +31 | cut -d' ' -f2- | xargs -r rm -f
    printf '%s\n' "$body"
    tmp="$QUEUE.tmp.$$"
    header > "$tmp"
    mv "$tmp" "$QUEUE"
    ;;
  *)
    sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2
    ;;
esac
