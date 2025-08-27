# School Lunch Menu to Google Calendar Sync

A flexible, general-purpose system for syncing lunch menus from various menu service APIs to Google Calendar. The system automatically detects the menu service type based on the URL and applies the appropriate parsing logic.

## 📚 Table of Contents

- [Features](#features)
- [Supported Menu Services](#supported-menu-services)
- [Installation](#installation)
- [Security Configuration](#security-configuration)
- [Usage](#usage)
- [Enhanced Menu Features](#enhanced-menu-features)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## 🎯 Features

- **URL-based Parser Detection**: Automatically selects the correct parser based on the menu API URL
- **Multiple Menu Sources**: Supports NutriSlice and FDMealPlanner APIs
- **Flexible Configuration**: All parameters are configurable via command line or environment variables
- **Calendar Color Management**: Named color mapping for Google Calendar event colors
- **Detailed Menu Descriptions**: Includes full menu details in calendar event descriptions
- **Global Configuration**: Centralized timeout, retry, and rate limiting settings
- **Extensible Design**: Easy to add new menu service parsers
- **Secure Configuration**: Environment files protect sensitive information
- **Simple Wrapper Scripts**: Easy-to-use dedicated scripts for common configurations

## 🍎 Supported Menu Services

### NutriSlice
- **URL Pattern**: `*.nutrislice.com`
- **Data Source**: Weekly JSON API calls
- **Menu Structure**: Simple food items with position-based sorting
- **Example**: School district lunch menus

### FDMealPlanner  
- **URL Pattern**: `*.fdmealplanner.com`
- **Data Source**: Monthly JSON API calls
- **Menu Structure**: Complex categorized items with parent-child relationships
- **Required Parameters**: `account_id`, `location_id`, `meal_period_id`, `tenant_id`
- **Example**: High school cafeteria menus

## 📦 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/D102-Lunch-Sync.git
cd D102-Lunch-Sync
```

### 2. Set Up Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Set Up Google Calendar API
1. Create a Google Cloud Project and enable Calendar API
2. Follow the [Google Calendar API setup guide](https://developers.google.com/calendar/api/quickstart/python)
3. Download `credentials.json` to the project directory
4. Run the script once to generate `token.json`

### 4. Configure Environment Files
```bash
# Copy example files and update with your values
cp .elementary_env.example .elementary_env
cp .highschool_env.example .highschool_env

# Edit the files with your actual calendar ID and API parameters
nano .elementary_env
nano .highschool_env
```

## 🔒 Security Configuration

### What We're Protecting

**Sensitive Information:**
- **Google Calendar ID**: Personal calendar identifier
- **API URLs**: May contain school-specific identifiers  
- **FDMealPlanner Parameters**: Account, location, meal period, and tenant IDs

**Why This Matters:**
- **Privacy**: Calendar IDs can reveal personal information
- **Security**: API parameters might be considered internal/private
- **Best Practice**: Never commit credentials or sensitive config to public repositories

### Security Implementation

#### Environment Files
We use `.env` files to store sensitive configuration:

```
.elementary_env    # Elementary school configuration (git-ignored)
.highschool_env    # High school configuration (git-ignored)
```

#### Template Files
Safe template files are committed to Git:

```
.elementary_env.example    # Template with placeholder values
.highschool_env.example    # Template with placeholder values
```

#### Git Protection
The `.gitignore` file ensures sensitive files are never committed:

```gitignore
# Sensitive configuration and credentials
credentials.json
token.json
.elementary_env
.highschool_env
*.env
```

### Setup Process

1. **Copy Templates**:
   ```bash
   cp .elementary_env.example .elementary_env
   cp .highschool_env.example .highschool_env
   ```

2. **Update Configuration**:
   Edit the copied files with your actual values:
   ```bash
   # Update elementary school config
   nano .elementary_env
   
   # Update high school config  
   nano .highschool_env
   ```

3. **Validation**:
   The wrapper scripts validate configuration on startup and check for placeholder values.

### Security Checklist

- ✅ **Environment files are git-ignored**
- ✅ **Template files contain only placeholders**
- ✅ **Scripts validate configuration on startup**
- ✅ **No sensitive data in committed code**
- ✅ **Google credentials stored separately**

## 🚀 Usage

### Simple Wrapper Scripts (Recommended)

For common configurations, use the dedicated wrapper scripts:

```bash
# Elementary school (NutriSlice API)
./run_elementary_sync.sh -x          # Dry run
./run_elementary_sync.sh -w 8        # Sync 8 weeks
./run_elementary_sync.sh -s 2025-09-01  # Start from specific date

# High school (FDMealPlanner API)  
./run_highschool_sync.sh -x          # Dry run
./run_highschool_sync.sh -w 8        # Sync 8 weeks
./run_highschool_sync.sh -s 2025-09-01  # Start from specific date
```

**Important**: Before using the wrapper scripts, make sure you've set up the environment files with your actual calendar ID and API parameters.

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

### Command Line Options

| Short | Long | Description | Default |
|-------|------|-------------|---------|
| `-u` | `--base-url` | Base URL for the menu API | *Required* |
| `-c` | `--calendar-id` | Google Calendar ID | *Required unless dry-run* |
| `-p` | `--event-prefix` | Event title prefix | `""` |
| `-o` | `--event-color` | Calendar color name or ID | `grape` |
| `-r` | `--credentials` | OAuth credentials file | `credentials.json` |
| `-t` | `--token` | OAuth token file | `token.json` |
| `-l` | `--log-level` | Logging level | `INFO` |
| `-d` | `--log-dir` | Directory for log files | `None` |
| `-n` | `--no-stdout` | Disable stdout logging | `False` |
| `-w` | `--max-weeks` | Maximum weeks to check | `8` |
| `-s` | `--start-date` | Start date (YYYY-MM-DD) | Today |
| `-x` | `--dry-run` | Only collect menus, skip sync | `False` |

#### FDMealPlanner Specific Options

| Short | Long | Description |
|-------|------|-------------|
| `-a` | `--account-id` | FDMealPlanner account ID |
| `-i` | `--location-id` | FDMealPlanner location ID |
| `-m` | `--meal-period-id` | FDMealPlanner meal period ID |
| `-e` | `--tenant-id` | FDMealPlanner tenant ID |

## 📋 Enhanced Menu Features

### Detailed Menu Descriptions

Each calendar event now includes comprehensive menu details in the event description field:

#### Elementary School Menus (NutriSlice)
- **Format**: Simple "MENU ITEMS" header with bulleted list
- **Content**: All menu items sorted by position (lowest to highest)
- **Source**: `menu_items[x].food.name` field from API

**Example:**
```
FRHL: Orange Chicken

MENU ITEMS

- Orange Chicken
- WG Popcorn Chicken
- Orange Sauce
- Vegetable Fried Rice WG
- Fresh Broccoli Bites
- Seasonal Fruit
- Fat Free Milk
- Milk 1%, low fat, 8 fl oz.
- Chocolate Low Fat Milk
- Strawberry Milk
```

#### High School Menus (FDMealPlanner)
- **Format**: Category headers in ALL CAPS with organized sections
- **Content**: Items sorted by sequence number, grouped by category
- **Hierarchy**: Parent items with indented child items
- **Source**: `englishAlternateName` (preferred) or `componentName`

**Example:**
```
LTHSS: Baked Potato Bar

BAKED POTATO BAR

- Baked Potato
- Chili Con Carne
- Broccoli, Florets, 1" inch (MTO)
- Cheese Sauce, quick
- Cheese, Monterey Jack, Shredded 4/5#
- Bacon, crumbled, 1 Tbsp. (MTO)

ENTREE

- Cheese Pizza - 6 slice
- Pepperoni Pizza - 6 slices
- Fried Spicy Chicken Sandwich
- Hamburger
- Cheeseburger
- Bosco Sticks - 6"

SIDE

- Red Grape Cup
- Rice Krispie Treats
- Quest Chocolate Chip Cookie
- Fudge Brownies - Box Mix
```

## ⚙️ Configuration

### Calendar Colors

The system supports named colors that map to Google Calendar color IDs:

| Color Name | ID | Color Name | ID |
|------------|----|------------|----|
| lavender   | 1  | tangerine  | 6  |
| sage       | 2  | peacock    | 7  |
| grape      | 3  | graphite   | 8  |
| flamingo   | 4  | blueberry  | 9  |
| banana     | 5  | basil      | 10 |
|            |    | tomato     | 11 |

### Global Configuration

The system uses centralized configuration in the `GlobalConfig` class:

```python
class GlobalConfig:
    REQUEST_TIMEOUT = 10        # API request timeout (seconds)
    MAX_RETRIES = 7            # Maximum retry attempts
    RATE_LIMIT_DELAY = 1       # Delay between requests (seconds)
```

### Environment Configuration Files

#### `.elementary_env`
```bash
CALENDAR_ID="your-actual-calendar-id@group.calendar.google.com"
BASE_URL="https://justadashcatering.api.nutrislice.com/menu/api/weeks/school/lagrange-sd-102/menu-type/park-junior-high"
EVENT_PREFIX="FRHL: "
EVENT_COLOR="grape"
MAX_WEEKS=4
```

#### `.highschool_env`
```bash
CALENDAR_ID="your-actual-calendar-id@group.calendar.google.com"
BASE_URL="https://apiservicelocatorstenantquest.fdmealplanner.com/api/v1/data-locator-webapi/4/meals"
EVENT_PREFIX="LTHSS: "
EVENT_COLOR="peacock"
MAX_WEEKS=4

# FDMealPlanner API Parameters
ACCOUNT_ID="10091"
LOCATION_ID="10320"
MEAL_PERIOD_ID="2"
TENANT_ID="4"
```

## 🚀 Deployment

### Server Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/D102-Lunch-Sync.git
   cd D102-Lunch-Sync
   ```

2. **Set up Python virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Set up Google Calendar API credentials**:
   - Follow the README instructions to get `credentials.json`
   - Place it in the project directory
   - Copy your working `token.json` from development environment

4. **Configure environment files**:
   ```bash
   cp .elementary_env.example .elementary_env
   cp .highschool_env.example .highschool_env
   # Edit with your actual values
   ```

5. **Test the setup**:
   ```bash
   ./run_elementary_sync.sh -x  # Test elementary
   ./run_highschool_sync.sh -x  # Test high school
   ```

### Scheduled Execution

#### Cronjob Setup

```bash
# Edit crontab
crontab -e

# Add entries for both menu types (runs at 11 PM daily)
0 23 * * * cd /path/to/D102-Lunch-Sync && ./run_elementary_sync.sh
30 23 * * * cd /path/to/D102-Lunch-Sync && ./run_highschool_sync.sh
```

#### GitHub Integration

```bash
# Initial commit
git add .
git commit -m "Add lunch menu sync system"
git push origin main

# Server deployment
git clone https://github.com/username/D102-Lunch-Sync.git
cd D102-Lunch-Sync
./run_elementary_sync.sh -x  # Test
```

### File Structure
```
D102-Lunch-Sync/
├── school_lunch_menu_google_calendar_sync.py  # Main application
├── run_elementary_sync.sh                     # Elementary wrapper script
├── run_highschool_sync.sh                     # High school wrapper script
├── .elementary_env                            # Elementary configuration (create from example)
├── .highschool_env                            # High school configuration (create from example)
├── .elementary_env.example                    # Elementary template
├── .highschool_env.example                    # High school template
├── requirements.txt                           # Python dependencies
├── credentials.json                           # Google API credentials (you provide)
├── token.json                                # OAuth token (auto-generated)
├── venv/                                     # Python virtual environment
└── logs/                                     # Log files
    └── school_lunch_menu_google_calendar_sync_*.log  # Daily application logs
```

## 🔧 Troubleshooting

### Common Issues

1. **Missing Required Parameters**: Ensure all required parameters for your menu service are provided
2. **Invalid URL**: Verify the URL matches a supported service pattern
3. **Calendar 404 Errors**: Check that the calendar ID is correct and accessible
4. **Environment File Errors**: Ensure `.env` files exist and contain valid configuration
5. **API Rate Limits**: The system includes built-in rate limiting, but some services may have stricter limits
6. **SSL Warnings**: These are suppressed automatically but indicate OpenSSL version compatibility issues

### Debug Mode

Enable debug logging to see detailed operation information:

```bash
python3 school_lunch_menu_google_calendar_sync.py -u "..." -l DEBUG -x
```

This will show:
- API request/response details
- Menu parsing logic
- Calendar event comparison
- Error details and retry attempts

### Testing Commands

```bash
# Test elementary API only
./run_elementary_sync.sh -x -w 1

# Test high school API only  
./run_highschool_sync.sh -x -w 1

# Debug with verbose logging
python3 school_lunch_menu_google_calendar_sync.py \
  -u "https://school.nutrislice.com/..." \
  -p "Test: " -o "grape" -x -l DEBUG
```

## 🔧 Extending the System

### Adding a New Menu Parser

1. **Create Parser Class**:
   ```python
   class NewServiceParser(MenuParser):
       def _validate_config(self):
           # Validate required parameters
           pass
       
       def collect_menus(self, start_date, max_weeks, logger, session):
           # Implement menu collection logic
           pass
   ```

2. **Update Factory**:
   ```python
   @staticmethod
   def create_parser(base_url: str, **kwargs) -> MenuParser:
       url_lower = base_url.lower()
       
       if 'newservice.com' in url_lower:
           return NewServiceParser(base_url, **kwargs)
       # ... existing conditions
   ```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new parsers
4. Submit a pull request

When adding new menu service support:
- Follow the existing parser pattern
- Include comprehensive error handling
- Add appropriate URL pattern matching
- Document any required parameters
- Test with dry-run mode first

## 📄 License

MIT License - see LICENSE file for details.

---

## 📞 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Run with `-l DEBUG` to get detailed information
3. Check the log files for specific error messages
4. Verify your Google Cloud Console setup
5. Ensure environment files are properly configured

This script is provided as-is for personal use. Please respect the school website's terms of service and don't overload their servers with excessive requests.