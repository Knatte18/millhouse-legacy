#!/usr/bin/env bash
# notify.sh — Best-effort desktop notification for helm skills.
# Called by helm-go and helm-merge at specific trigger points.
# Reads _helm/config.yaml to decide whether toast is enabled.
# Always exits 0 — failures warn on stderr, never block the caller.

set -euo pipefail

# --- Argument parsing ---
EVENT=""
BRANCH=""
DETAIL=""
URGENCY="high"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --event)  EVENT="$2";  shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --detail) DETAIL="$2"; shift 2 ;;
    --urgency) URGENCY="$2"; shift 2 ;;
    *) echo "[helm-notify] unknown argument: $1" >&2; shift ;;
  esac
done

if [[ -z "$EVENT" ]]; then
  echo "[helm-notify] warning: --event is required" >&2
  exit 0
fi

# --- Resolve config ---
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo "[helm-notify] warning: not in a git repo, skipping notification" >&2
  exit 0
}

CONFIG="$REPO_ROOT/_helm/config.yaml"
TOAST_ENABLED=true  # default: enabled when config missing or toast key absent

if [[ -f "$CONFIG" ]]; then
  TOAST_BLOCK=$(awk '/^  toast:/,/^  [a-zA-Z]/' "$CONFIG" | tail -n +2)
  if [[ -n "$TOAST_BLOCK" ]]; then
    if echo "$TOAST_BLOCK" | grep -q 'enabled: false'; then
      TOAST_ENABLED=false
    fi
  fi
fi

if [[ "$TOAST_ENABLED" != "true" ]]; then
  exit 0
fi

# --- Sanitize inputs ---
# Strip characters that break shell quoting in platform commands: " $ ' ` \
sanitize() {
  echo "$1" | tr -d "\"\$'\`\\\\"
}

SAFE_BRANCH=$(sanitize "$BRANCH")
SAFE_DETAIL=$(sanitize "$DETAIL")

TITLE="[helm] $SAFE_BRANCH $EVENT"

# --- Platform detection & toast ---
send_toast() {
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*|Windows_NT)
      powershell -NoProfile -Command "New-BurntToastNotification -Text '$TITLE', '$SAFE_DETAIL'" 2>/dev/null || {
        echo "[helm-notify] warning: BurntToast notification failed (module installed?)" >&2
      }
      ;;
    Darwin)
      osascript -e "display notification \"$SAFE_DETAIL\" with title \"$TITLE\"" 2>/dev/null || {
        echo "[helm-notify] warning: osascript notification failed" >&2
      }
      ;;
    Linux)
      notify-send "$TITLE" "$SAFE_DETAIL" 2>/dev/null || {
        echo "[helm-notify] warning: notify-send failed (libnotify installed?)" >&2
      }
      ;;
    *)
      echo "[helm-notify] warning: unsupported platform $(uname -s)" >&2
      ;;
  esac
}

send_toast

# --- Slack (TODO) ---
# Future: if notifications.slack.enabled is true and webhook is non-empty,
# post to Slack. Use --urgency to gate: info-level events skip Slack.
# if [[ "$URGENCY" == "high" ]]; then
#   curl -s -X POST "$SLACK_WEBHOOK" ...
# fi

exit 0
