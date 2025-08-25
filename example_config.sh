#!/bin/bash
# Example configuration script for lunch menu sync
# Copy this file and modify for your setup

# Set your calendar ID (get this from your Google Calendar settings)
# To find your calendar ID:
# 1. Go to calendar.google.com
# 2. Click the three dots next to your calendar name
# 3. Select "Settings and sharing"
# 4. Scroll down to "Calendar ID" section
# Example: "your-email@gmail.com" or "family123@group.calendar.google.com"
export CALENDAR_ID="YOUR_ACTUAL_CALENDAR_ID_HERE"

# Set log level (DEBUG, VERBOSE, INFO, WARNING, ERROR)
export LUNCH_SYNC_LOG_LEVEL="INFO"

# Set log directory (optional)
export LUNCH_SYNC_LOG_DIR="./logs"

# Set start date (YYYY-MM-DD, defaults to today if not set)
export LUNCH_SYNC_START_DATE="2025-08-24"

# Set max weeks to sync (default: 8)
export LUNCH_SYNC_MAX_WEEKS=1

# Create log directory if it doesn't exist
mkdir -p "$LUNCH_SYNC_LOG_DIR"

# Run the sync script
python3 lunch_menu_sync.py \
  --calendar-id "$CALENDAR_ID" \
  --log-level "$LUNCH_SYNC_LOG_LEVEL" \
  --log-dir "$LUNCH_SYNC_LOG_DIR" \
  --start-date "$LUNCH_SYNC_START_DATE" \
  --max-weeks "$LUNCH_SYNC_MAX_WEEKS"
