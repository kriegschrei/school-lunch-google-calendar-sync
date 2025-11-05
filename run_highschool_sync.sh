#!/bin/bash
# High School Lunch Menu Sync (FDMealPlanner API)

# Set working directory
cd /path/to/script

# Activate virtual environment
source ./venv/bin/activate

# Load configuration from environment file
if [ ! -f .highschool_env ]; then
    echo "Error: .highschool_env file not found!"
    echo "Please copy .highschool_env and update it with your configuration."
    exit 1
fi

source .highschool_env

# Validate required configuration
if [ "$CALENDAR_ID" = "YOUR_CALENDAR_ID_HERE" ]; then
    echo "Error: Please update CALENDAR_ID in .highschool_env"
    exit 1
fi

if [ "$ACCOUNT_ID" = "YOUR_ACCOUNT_ID_HERE" ]; then
    echo "Error: Please update FDMealPlanner API parameters in .highschool_env"
    exit 1
fi

# Execute the sync
  -u "$BASE_URL" \
  -c "$CALENDAR_ID" \
  -p "$EVENT_PREFIX" \
  -o "$EVENT_COLOR" \
  -a "$ACCOUNT_ID" \
  -i "$LOCATION_ID" \
  -m "$MEAL_PERIOD_ID" \
  -e "$TENANT_ID" \
  -l INFO \
  -d ./logs \
  -w "$MAX_WEEKS" \
  --service-account-file  "d102-lunch-sync-853b892803c6.json" \
  "$@"
