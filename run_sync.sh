#!/bin/bash
# Lunch Menu Sync Wrapper Script
# This script activates the virtual environment and runs the menu sync

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load configuration from environment or config file
if [ -f "./config.sh" ]; then
    source ./config.sh
else
    # Use example config as fallback
    source ./example_config.sh
fi

# Ensure log directory exists
mkdir -p "$LUNCH_SYNC_LOG_DIR"

# Activate virtual environment
if [ ! -d "./venv" ]; then
    echo "ERROR: Virtual environment not found. Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

source ./venv/bin/activate

# Run the sync with logging
echo "$(date): Starting lunch menu sync..." >> "$LUNCH_SYNC_LOG_DIR/cron.log"

python3 lunch_menu_sync.py \
  --calendar-id "$CALENDAR_ID" \
  --log-level "$LUNCH_SYNC_LOG_LEVEL" \
  --log-dir "$LUNCH_SYNC_LOG_DIR" \
  --start-date "$LUNCH_SYNC_START_DATE" \
  --max-weeks "$LUNCH_SYNC_MAX_WEEKS" \
  2>&1 | tee -a "$LUNCH_SYNC_LOG_DIR/cron.log"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "$(date): Lunch menu sync completed successfully" >> "$LUNCH_SYNC_LOG_DIR/cron.log"
else
    echo "$(date): Lunch menu sync failed with exit code $exit_code" >> "$LUNCH_SYNC_LOG_DIR/cron.log"
fi

echo "----------------------------------------" >> "$LUNCH_SYNC_LOG_DIR/cron.log"

exit $exit_code
