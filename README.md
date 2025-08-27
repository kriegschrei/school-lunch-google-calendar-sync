# School Lunch Menu to Google Calendar Sync

A Python application that automatically syncs school lunch menus from various menu service APIs to Google Calendar. The system automatically detects the menu service type and applies the appropriate parsing logic.

## Features

- **Automatic Parser Detection**: Identifies menu service type from URL (NutriSlice, FDMealPlanner)
- **Google Calendar Integration**: Creates all-day events with detailed menu descriptions
- **Multiple Menu Sources**: Supports NutriSlice and FDMealPlanner APIs
- **Flexible Configuration**: Environment-based configuration with easy setup scripts
- **Calendar Color Management**: Named color mapping for Google Calendar events
- **Text Customization**: Configurable text replacements and formatting

## Supported Menu Services

### NutriSlice
- **URL Pattern**: `*.nutrislice.com`
- **Data Source**: Weekly JSON API calls
- **Menu Structure**: Simple food items with position-based sorting

### FDMealPlanner
- **URL Pattern**: `*.fdmealplanner.com`
- **Data Source**: Monthly JSON API calls
- **Menu Structure**: Complex categorized items with parent-child relationships
- **Required Parameters**: `account_id`, `location_id`, `meal_period_id`, `tenant_id`

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/kriegschrei/school-lunch-google-calendar-sync.git
cd school-lunch-google-calendar-sync
```

### 2. Set Up Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Google Calendar API Setup

#### Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Calendar API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Calendar API"
   - Click "Enable"

#### Create OAuth Credentials
1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth 2.0 Client IDs"
3. Choose "Desktop application"
4. Download the `credentials.json` file
5. Place `credentials.json` in the project directory

#### First Run Authentication
```bash
# Run the script once to authenticate
python3 school_lunch_menu_google_calendar_sync.py \
  -u "https://your-menu-api-url.com" \
  -c "your-calendar-id@group.calendar.google.com" \
  -x
```
This will open a browser window for OAuth authentication and create `token.json`.

### 4. Configuration Setup

#### Create Environment Files
```bash
# Copy example files
cp .elementary_env.example .elementary_env
cp .highschool_env.example .highschool_env

# Edit with your actual values
nano .elementary_env
nano .highschool_env
```

#### Elementary School Configuration (`.elementary_env`)
```bash
CALENDAR_ID="your-calendar-id@group.calendar.google.com"
BASE_URL="https://your-school.nutrislice.com/menu/api/weeks/school/district/menu-type/elementary"
EVENT_PREFIX="EL: "
EVENT_COLOR="grape"
MAX_WEEKS=4
REPLACE_WG="--replace-wg"
```

#### High School Configuration (`.highschool_env`)
```bash
CALENDAR_ID="your-calendar-id@group.calendar.google.com"
BASE_URL="https://your-school.fdmealplanner.com/api/v1/data-locator-webapi/tenant/meals"
EVENT_PREFIX="HS: "
EVENT_COLOR="peacock"
MAX_WEEKS=4

# FDMealPlanner API Parameters
ACCOUNT_ID="your_account_id"
LOCATION_ID="your_location_id"
MEAL_PERIOD_ID="your_meal_period_id"
TENANT_ID="your_tenant_id"
```

### 5. Update Script Paths
Edit both wrapper scripts to set the correct working directory:
```bash
# In run_elementary_sync.sh and run_highschool_sync.sh
cd /path/to/script  # Change to your actual project path
```

## Usage

### Simple Wrapper Scripts (Recommended)

```bash
# Elementary school (NutriSlice API)
./run_elementary_sync.sh -x          # Dry run
./run_elementary_sync.sh -w 8        # Sync 8 weeks
./run_elementary_sync.sh -s 2025-01-01  # Start from specific date

# High school (FDMealPlanner API)
./run_highschool_sync.sh -x          # Dry run
./run_highschool_sync.sh -w 8        # Sync 8 weeks
./run_highschool_sync.sh -s 2025-01-01  # Start from specific date
```

### Direct Command Line Usage

```bash
# NutriSlice API example
python3 school_lunch_menu_google_calendar_sync.py \
  -u "https://school.api.nutrislice.com/menu/api/weeks/school/district/menu-type/elementary" \
  -c "your-calendar-id@group.calendar.google.com" \
  -p "Elementary: " \
  -o "grape" \
  -w 4

# FDMealPlanner API example
python3 school_lunch_menu_google_calendar_sync.py \
  -u "https://api.fdmealplanner.com/api/v1/data-locator-webapi/4/meals" \
  -c "your-calendar-id@group.calendar.google.com" \
  -p "High School: " \
  -o "peacock" \
  -a "10091" -i "10320" -m "2" -e "4" \
  -w 4
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-u, --base-url` | Base URL for the menu API | *Required* |
| `-c, --calendar-id` | Google Calendar ID | *Required unless dry-run* |
| `-p, --event-prefix` | Event title prefix | `""` |
| `-o, --event-color` | Calendar color name or ID | `grape` |
| `-w, --max-weeks` | Maximum weeks to check | `8` |
| `-s, --start-date` | Start date (YYYY-MM-DD) | Today |
| `-x, --dry-run` | Only collect menus, skip sync | `False` |
| `-l, --log-level` | Logging level | `INFO` |
| `-d, --log-dir` | Directory for log files | `None` |

### FDMealPlanner Specific Options
| Option | Description |
|--------|-------------|
| `-a, --account-id` | FDMealPlanner account ID |
| `-i, --location-id` | FDMealPlanner location ID |
| `-m, --meal-period-id` | FDMealPlanner meal period ID |
| `-e, --tenant-id` | FDMealPlanner tenant ID |

### Text Customization Options
| Option | Description |
|--------|-------------|
| `--replace-wg` | Remove WG (Whole Grain) abbreviations |
| `-R, --text-replacements` | Custom text replacements (find->replace) |

## Calendar Colors

Available color names: `lavender`, `sage`, `grape`, `flamingo`, `banana`, `tangerine`, `peacock`, `graphite`, `blueberry`, `basil`, `tomato`

## Deployment

### Automated Execution (Cron)
```bash
# Edit crontab
crontab -e

# Add entries (runs daily at 11 PM)
0 23 * * * cd /path/to/project && ./run_elementary_sync.sh
30 23 * * * cd /path/to/project && ./run_highschool_sync.sh
```

### Testing
```bash
# Test elementary API
./run_elementary_sync.sh -x -w 1

# Test high school API
./run_highschool_sync.sh -x -w 1

# Debug with verbose logging
./run_elementary_sync.sh -x -l DEBUG
```

## File Structure
```
project/
├── school_lunch_menu_google_calendar_sync.py  # Main application
├── run_elementary_sync.sh                     # Elementary wrapper script
├── run_highschool_sync.sh                     # High school wrapper script
├── .elementary_env                            # Elementary configuration
├── .highschool_env                            # High school configuration
├── .elementary_env.example                    # Elementary template
├── .highschool_env.example                    # High school template
├── requirements.txt                           # Python dependencies
├── credentials.json                           # Google API credentials
├── token.json                                # OAuth token (auto-generated)
└── venv/                                     # Python virtual environment
```

## Troubleshooting

### Common Issues
1. **Missing credentials.json**: Ensure you've downloaded OAuth credentials from Google Cloud Console
2. **Invalid calendar ID**: Verify the calendar ID is correct and accessible
3. **Environment file errors**: Check that `.env` files exist and contain valid configuration
4. **API errors**: Verify API URLs and parameters are correct

### Debug Mode
```bash
# Enable debug logging
python3 school_lunch_menu_google_calendar_sync.py -u "..." -l DEBUG -x
```

## Security Notes

- **Never commit** `credentials.json`, `token.json`, or `.env` files to version control
- These files are automatically ignored by `.gitignore`
- Use environment files to store sensitive configuration
- Keep your Google Cloud credentials secure

## License

MIT License - see LICENSE file for details.
