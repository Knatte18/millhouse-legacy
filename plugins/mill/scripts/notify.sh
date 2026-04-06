#!/usr/bin/env bash
# notify.sh — Best-effort desktop notification for mill skills.
# Called by mill-go and mill-merge at specific trigger points.
# Reads _millhouse/config.yaml to decide whether toast is enabled.
# Always exits 0 — failures warn on stderr, never block the caller.

set -u

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
    *) echo "[mill-notify] unknown argument: $1" >&2; shift ;;
  esac
done

if [[ -z "$EVENT" ]]; then
  echo "[mill-notify] warning: --event is required" >&2
  exit 0
fi

# --- Resolve config ---
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo "[mill-notify] warning: not in a git repo, skipping notification" >&2
  exit 0
}

CONFIG="$REPO_ROOT/_millhouse/config.yaml"
TOAST_ENABLED=true  # default: enabled when config missing or toast key absent

if [[ -f "$CONFIG" ]]; then
  TOAST_BLOCK=$(awk '/^  toast:/{ found=1; next } found && /^  [a-zA-Z]/{ exit } found{ print }' "$CONFIG")
  if [[ -n "$TOAST_BLOCK" ]]; then
    if echo "$TOAST_BLOCK" | grep -qE 'enabled:\s+false\s*$'; then
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
  printf '%s' "$1" | tr -d "\"\$'\`\\\\"  # strips: " $ ' ` \
}

SAFE_EVENT=$(sanitize "$EVENT")
SAFE_BRANCH=$(sanitize "$BRANCH")
SAFE_DETAIL=$(sanitize "$DETAIL")

TITLE="[mill] $SAFE_BRANCH $SAFE_EVENT"

# --- Platform detection & toast ---
send_toast() {
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*|Windows_NT)
      powershell -NoProfile -Command "New-BurntToastNotification -Text '$TITLE', '$SAFE_DETAIL'" 2>/dev/null || {
        echo "[mill-notify] warning: BurntToast notification failed (module installed?)" >&2
      }
      ;;
    Darwin)
      osascript -e "display notification \"$SAFE_DETAIL\" with title \"$TITLE\"" 2>/dev/null || {
        echo "[mill-notify] warning: osascript notification failed" >&2
      }
      ;;
    Linux)
      notify-send "$TITLE" "$SAFE_DETAIL" 2>/dev/null || {
        echo "[mill-notify] warning: notify-send failed (libnotify installed?)" >&2
      }
      ;;
    *)
      echo "[mill-notify] warning: unsupported platform $(uname -s)" >&2
      ;;
  esac
}

send_toast

# --- Slack (TODO) ---
# URGENCY is intentionally a no-op until Slack is implemented.
# When enabled, info-level events (completion) skip Slack; high-urgency
# events (blocked) post to the webhook.
# if [[ "$URGENCY" == "high" ]]; then
#   curl -s -X POST "$SLACK_WEBHOOK" ...
# fi

exit 0
