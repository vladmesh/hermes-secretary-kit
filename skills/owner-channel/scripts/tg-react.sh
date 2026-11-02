#!/usr/bin/env bash
# React to the current owner message, or to a verified earlier one.
#   tg-react.sh 👌                                  current message
#   tg-react.sh --find --search "text" --days 7     list candidates (read-only)
#   tg-react.sh 👌 --db-message-id 1234             react to the picked one
set -euo pipefail
# Hermes may rewrite HOME for tools, so resolve the profile explicitly.
PROFILE_DIR="${HERMES_HOME:-$HOME/.hermes}"
ENV_FILE="${SECRETARY_ENV_FILE:-$PROFILE_DIR/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi
export HERMES_HOME="$PROFILE_DIR"
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/tg_react.py" "$@"
