#!/usr/bin/env bash
# ASI Builders Leaderboard — cron setup
# Run once to register the weekly job.
# Adjust PYTHON and PROJECT_DIR as needed.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
LOG_FILE="$PROJECT_DIR/logs/cron.log"

mkdir -p "$PROJECT_DIR/logs"

# Weekly on Monday at 08:00 UTC
CRON_SCHEDULE="0 8 * * 1"
CRON_CMD="cd $PROJECT_DIR && $PYTHON main.py run >> $LOG_FILE 2>&1"
CRON_LINE="$CRON_SCHEDULE $CRON_CMD"

echo "Installing cron job:"
echo "  $CRON_LINE"

# Add only if not already present
(crontab -l 2>/dev/null | grep -qF "asi-builders" && echo "→ Cron already installed (skipping)") || \
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -

echo "Done. Verify with: crontab -l"
echo ""
echo "To run manually:  cd $PROJECT_DIR && python main.py run"
echo "To check status:  cd $PROJECT_DIR && python main.py status"
