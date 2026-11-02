#!/usr/bin/env bash
# Install the kit into a Hermes profile.
#   ./install.sh                      skills into $HERMES_HOME/skills, brain template into $BRAIN_PATH
#   ./install.sh --with-cron          also create the evening review cron job
# Env: HERMES_HOME (default ~/.hermes), BRAIN_PATH (default ~/brain),
#      HERMES_PROFILE (optional, passed to `hermes -p`), REVIEW_TIME (default "30 22 * * *").
set -euo pipefail
KIT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
BRAIN_PATH="${BRAIN_PATH:-$HOME/brain}"
SKILLS_DIR="$HERMES_HOME/skills/secretary-kit"
WITH_CRON=0
[[ "${1:-}" == "--with-cron" ]] && WITH_CRON=1

mkdir -p "$SKILLS_DIR"
for skill in brain owner-channel deferred-tasks evening-review; do
  rm -rf "${SKILLS_DIR:?}/$skill"
  cp -r "$KIT/skills/$skill" "$SKILLS_DIR/$skill"
done
chmod +x "$SKILLS_DIR"/owner-channel/scripts/*
echo "skills -> $SKILLS_DIR"

if [[ -e "$BRAIN_PATH/INDEX.md" ]]; then
  echo "brain exists at $BRAIN_PATH, left untouched"
else
  mkdir -p "$BRAIN_PATH"
  cp -r "$KIT/brain-template/." "$BRAIN_PATH/"
  python3 "$BRAIN_PATH/reindex.py"
  echo "brain template -> $BRAIN_PATH (sample notes are fictional, delete them)"
fi

ENV_FILE="$HERMES_HOME/.env"
touch "$ENV_FILE"
for var in BRAIN_PATH OWNER_CHAT_ID OWNER_TZ; do
  if ! grep -q "^$var=" "$ENV_FILE"; then
    case "$var" in
      BRAIN_PATH) echo "BRAIN_PATH=$BRAIN_PATH" >> "$ENV_FILE" ;;
      *) echo "$var=" >> "$ENV_FILE"; echo "fill in $var in $ENV_FILE" ;;
    esac
  fi
done

if [[ $WITH_CRON == 1 ]]; then
  profile_args=()
  [[ -n "${HERMES_PROFILE:-}" ]] && profile_args=(-p "$HERMES_PROFILE")
  hermes "${profile_args[@]}" cron create "${REVIEW_TIME:-30 22 * * *}" \
    "$(cat "$SKILLS_DIR/evening-review/templates/evening-review-prompt.md")" \
    --name "Evening review" --skill evening-review --skill brain --deliver telegram
fi
echo "done. Restart the gateway so it picks up the new skills."
