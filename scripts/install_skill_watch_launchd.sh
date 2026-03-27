#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_PATH="$HOME/Library/LaunchAgents/com.github-trend.using-superpowers-watch.plist"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
CONFIG_PATH="$PROJECT_DIR/config/skill_watch.yaml"
LOG_OUT="$PROJECT_DIR/logs/launchd.using_superpowers.out.log"
LOG_ERR="$PROJECT_DIR/logs/launchd.using_superpowers.err.log"

mkdir -p "$HOME/Library/LaunchAgents" "$PROJECT_DIR/logs"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Missing python interpreter: $PYTHON_BIN" >&2
  exit 1
fi

if [ ! -f "$CONFIG_PATH" ]; then
  echo "Missing config file: $CONFIG_PATH" >&2
  echo "Copy config/skill_watch.example.yaml to config/skill_watch.yaml first." >&2
  exit 1
fi

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.github-trend.using-superpowers-watch</string>
  <key>WorkingDirectory</key>
  <string>$PROJECT_DIR</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$PROJECT_DIR/skill_watch.py</string>
    <string>--config</string>
    <string>$CONFIG_PATH</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>1</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>$LOG_OUT</string>
  <key>StandardErrorPath</key>
  <string>$LOG_ERR</string>
</dict>
</plist>
PLIST

launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load "$PLIST_PATH"

echo "Installed: $PLIST_PATH"
echo "Schedule: daily at 01:00"
echo "Check status with: launchctl print gui/$(id -u)/com.github-trend.using-superpowers-watch"
