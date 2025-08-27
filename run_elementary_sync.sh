#!/bin/bash
# Elementary School Lunch Menu Sync (NutriSlice API)

# Set working directory
cd /Users/jpohl/git/personal/D102-Lunch-Sync

# Activate virtual environment
source ./venv/bin/activate

# Load configuration from environment file
if [ ! -f .elementary_env ]; then
    echo "Error: .elementary_env file not found!"
    echo "Please copy .elementary_env and update it with your configuration."
    exit 1
fi

source .elementary_env

# Validate required configuration
if [ "$CALENDAR_ID" = "YOUR_CALENDAR_ID_HERE" ]; then
    echo "Error: Please update CALENDAR_ID in .elementary_env"
    exit 1
fi

# Execute the sync
python3 school_lunch_menu_google_calendar_sync.py \
  -u "$BASE_URL" \
  -c "$CALENDAR_ID" \
  -p "$EVENT_PREFIX" \
  -o "$EVENT_COLOR" \
  -l INFO \
  -d ./logs \
  -w "$MAX_WEEKS" \
  $REPLACE_WG \
  "$@"
