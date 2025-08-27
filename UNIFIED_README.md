# Unified Lunch Menu Sync

A unified Python script that syncs lunch menus from multiple school APIs with Google Calendar. Supports both elementary (NutriSlice) and high school (FDMealPlanner) menu systems.

## Features

- **Multi-System Support**: Elementary (NutriSlice) and High School (FDMealPlanner) APIs
- **Configurable**: Command-line and environment variable configuration
- **Reliable**: Error handling, retry logic, and rate limiting
- **Flexible**: Dry-run mode, custom date ranges, and configurable colors/prefixes
- **Automated**: Perfect for cronjobs and scheduled execution

## Quick Start

### 1. Setup Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Google Calendar Setup
1. Create a Google Cloud Project and enable Calendar API
2. Download `credentials.json` to project directory
3. Run once interactively to generate `token.json`

### 3. Basic Usage

**Elementary School Menu:**
```bash
./run_unified_sync.sh elementary --dry-run  # Test first
./run_unified_sync.sh elementary            # Live sync
```

**High School Menu:**
```bash
./run_unified_sync.sh highschool --dry-run  # Test first
./run_unified_sync.sh highschool            # Live sync
```

## Configuration

### Default Settings

| Menu Type   | Prefix  | Color   | API Source     |
|------------|---------|---------|----------------|
| elementary | `FRHL: ` | Grape (3) | NutriSlice    |
| highschool | `LTHSS: ` | Peacock (7) | FDMealPlanner |

### Environment Variables

**High School API Configuration:**
```bash
export HS_ACCOUNT_ID="10091"      # FDMealPlanner account ID
export HS_LOCATION_ID="10320"    # School location ID
export HS_MEAL_PERIOD_ID="2"     # Meal period (lunch)
export HS_TENANT_ID="4"          # Tenant ID
```

**Event Customization:**
```bash
export MENU_EVENT_PREFIX="CUSTOM: "  # Override default prefix
export MENU_EVENT_COLOR_ID="5"       # Override default color
```

## Command Reference

### Direct Script Usage

```bash
python unified_lunch_menu_sync.py --menu-type <type> [options]
```

**Required Arguments:**
- `--menu-type`: `elementary` or `highschool`

**Optional Arguments:**
- `--calendar-id ID`: Google Calendar ID (required unless `--dry-run`)
- `--event-prefix PREFIX`: Custom event prefix
- `--event-color-id ID`: Google Calendar color ID (1-11)
- `--start-date YYYY-MM-DD`: Start date (default: today)
- `--max-weeks N`: Maximum weeks to sync (default: 8)
- `--dry-run`: Collection only, no calendar changes
- `--log-level LEVEL`: DEBUG, INFO, WARNING, ERROR
- `--log-dir DIR`: Log file directory

### Wrapper Script Usage

```bash
./run_unified_sync.sh <menu-type> [options]
```

**Options:**
- `--dry-run`: Test mode only
- `--weeks N`: Number of weeks to sync
- `--date YYYY-MM-DD`: Start date
- `--help`: Show help

**Examples:**
```bash
# Test elementary menu collection
./run_unified_sync.sh elementary --dry-run

# Sync high school menu for 2 weeks
./run_unified_sync.sh highschool --weeks 2

# Start elementary sync from specific date
./run_unified_sync.sh elementary --date 2025-09-01
```

## Google Calendar Colors

| ID | Color Name | Hex Code |
|----|------------|----------|
| 1  | Lavender   | #7986CB  |
| 2  | Sage       | #33B679  |
| 3  | Grape      | #8E24AA  |
| 4  | Flamingo   | #E67C73  |
| 5  | Banana     | #F6BF26  |
| 6  | Tangerine  | #F4511E  |
| 7  | Peacock    | #039BE5  |
| 8  | Graphite   | #616161  |
| 9  | Blueberry  | #3F51B5  |
| 10 | Basil      | #0B8043  |
| 11 | Tomato     | #D50000  |

## Deployment

### Cronjob Setup

```bash
# Edit crontab
crontab -e

# Add entries for both menu types (runs at 11 PM daily)
0 23 * * * /path/to/D102-Lunch-Sync/run_unified_sync.sh elementary
0 23 * * * /path/to/D102-Lunch-Sync/run_unified_sync.sh highschool
```

### GitHub Integration

```bash
# Initial commit
git add .
git commit -m "Add unified lunch menu sync"
git push origin main

# Server deployment
git clone https://github.com/username/D102-Lunch-Sync.git
cd D102-Lunch-Sync
./run_unified_sync.sh elementary --dry-run  # Test
```

## Architecture

### Menu Parser Classes

The system uses an abstract `MenuParser` base class with specific implementations:

- **`ElementaryMenuParser`**: NutriSlice API (weekly JSON endpoints)
- **`HighSchoolMenuParser`**: FDMealPlanner API (monthly JSON endpoints)

### Data Flow

1. **Collection**: Parser-specific API calls retrieve raw menu data
2. **Parsing**: Extract menu items using type-specific logic
3. **Standardization**: Return unified `(date, menu_item)` tuples
4. **Synchronization**: Google Calendar API creates/updates events

### Error Handling

- Retry logic with exponential backoff
- Rate limiting for API calls
- Graceful handling of holidays and missing data
- Comprehensive logging at multiple levels

## Troubleshooting

### Common Issues

**"No menu items found"**
- Check API endpoints are accessible
- Verify date range (menus may not be published far in advance)
- Run with `--log-level DEBUG` for detailed info

**"Calendar API 404 errors"**
- Verify calendar ID is correct
- Check Google Calendar API permissions
- Ensure `credentials.json` and `token.json` are valid

**"High school API errors"**
- Verify environment variables are set correctly
- Check network connectivity to FDMealPlanner API

### Debug Commands

```bash
# Test elementary API only
./run_unified_sync.sh elementary --dry-run --weeks 1

# Test high school API only  
./run_unified_sync.sh highschool --dry-run --weeks 1

# Debug with verbose logging
python unified_lunch_menu_sync.py --menu-type elementary --dry-run --log-level DEBUG
```

## Migration from Individual Scripts

The unified script replaces:
- `lunch_menu_sync.py` (elementary)
- `hs_lunch_menu_sync.py` (high school)

**Benefits:**
- Single codebase to maintain
- Consistent error handling and logging
- Unified configuration system
- Easier deployment and updates

**Migration Steps:**
1. Test unified script with both menu types
2. Update cronjobs to use unified script
3. Remove old individual scripts
4. Update deployment documentation

## License

MIT License - see LICENSE file for details.
