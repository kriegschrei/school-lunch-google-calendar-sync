# Forest Road Lunch Menu to Google Calendar Sync

This Python script automatically scrapes the school lunch menu from the Forest Road cafeteria website and syncs it with your Google Family Calendar as all-day events.

## Features

- 🍎 Scrapes daily lunch menus from the school website
- 📅 Syncs with Google Family Calendar as all-day events
- 🔄 Automatically updates changed menus
- 🏖️ Skips weekends to avoid unnecessary requests
- 📊 Comprehensive logging with multiple levels
- 🔄 Retry logic for network failures
- ⏰ Designed for daily automated execution

## Requirements

- Python 3.7 or higher
- Google account with access to Google Calendar
- Google Cloud Project with Calendar API enabled

## Installation

1. **Clone or download this repository**
   ```bash
   cd /path/to/your/directory
   # Copy the files: lunch_menu_sync.py, requirements.txt, README.md
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Google Calendar Setup

### Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Create Project" or select an existing project
3. Note your project ID for later reference

### Step 2: Enable the Google Calendar API

1. In the Google Cloud Console, go to **APIs & Services > Library**
2. Search for "Google Calendar API"
3. Click on it and press **Enable**

### Step 3: Create OAuth 2.0 Credentials

1. Go to **APIs & Services > Credentials**
2. Click **Create Credentials > OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - Choose **External** user type (unless you have a Google Workspace account)
   - Fill in required fields:
     - App name: "Lunch Menu Sync"
     - User support email: your email
     - Developer contact information: your email
   - Add your email to test users
   - Save and continue through the scopes and test users sections
4. Choose **Desktop application** as the application type
5. Name it "Lunch Menu Sync Client"
6. Download the credentials JSON file
7. Rename it to `credentials.json` and place it in the same directory as the script

### Step 4: Get Your Calendar ID

Your Family calendar ID is: `ZmFtaWx5MTQ0NTE1NDA2MTA5NzQ3Nzg3OTFAZ3JvdXAuY2FsZW5kYXIuZ29vZ2xlLmNvbQ`

(This was extracted from the URL you provided)

### Step 5: Calendar Permissions

Ensure your Google account has edit access to the Family calendar:

1. Go to [Google Calendar](https://calendar.google.com)
2. Find your "Family" calendar in the left sidebar
3. Click the three dots next to it and select "Settings and sharing"
4. Under "Share with specific people", make sure your account has "Make changes to events" permission or higher

## Configuration

### Environment Variables (Optional)

You can set these environment variables to avoid command-line arguments:

```bash
export CALENDAR_ID="ZmFtaWx5MTQ0NTE1NDA2MTA5NzQ3Nzg3OTFAZ3JvdXAuY2FsZW5kYXIuZ29vZ2xlLmNvbQ"
export LUNCH_SYNC_LOG_LEVEL="INFO"
export LUNCH_SYNC_LOG_DIR="/var/log/lunch-sync"
```

## Usage

### Basic Usage

```bash
python lunch_menu_sync.py --calendar-id "ZmFtaWx5MTQ0NTE1NDA2MTA5NzQ3Nzg3OTFAZ3JvdXAuY2FsZW5kYXIuZ29vZ2xlLmNvbQ"
```

### Command Line Options

```bash
python lunch_menu_sync.py [OPTIONS]

Required:
  --calendar-id TEXT        Google Calendar ID

Optional:
  --credentials FILE        OAuth credentials file (default: credentials.json)
  --token FILE             OAuth token file (default: token.json)
  --log-level LEVEL        Logging level: DEBUG, VERBOSE, INFO, WARNING, ERROR (default: INFO)
  --log-dir DIRECTORY      Directory for log files (optional)
  --no-stdout              Disable stdout logging
  --max-days INTEGER       Maximum days to check (default: 60)
  --start-date YYYY-MM-DD  Start date (defaults to today)
```

### Examples

**Basic sync with INFO logging:**
```bash
python lunch_menu_sync.py --calendar-id "ZmFtaWx5MTQ0NTE1NDA2MTA5NzQ3Nzg3OTFAZ3JvdXAuY2FsZW5kYXIuZ29vZ2xlLmNvbQ"
```

**Debug mode with file logging:**
```bash
python lunch_menu_sync.py \
  --calendar-id "ZmFtaWx5MTQ0NTE1NDA2MTA5NzQ3Nzg3OTFAZ3JvdXAuY2FsZW5kYXIuZ29vZ2xlLmNvbQ" \
  --log-level DEBUG \
  --log-dir /var/log/lunch-sync
```

**Start from specific date:**
```bash
python lunch_menu_sync.py \
  --calendar-id "ZmFtaWx5MTQ0NTE1NDA2MTA5NzQ3Nzg3OTFAZ3JvdXAuY2FsZW5kYXIuZ29vZ2xlLmNvbQ" \
  --start-date 2024-01-15
```

## Automated Scheduling

### Using Cron (Linux/macOS)

1. **Create a wrapper script** (recommended for environment setup):

   Create `/usr/local/bin/lunch-sync.sh`:
   ```bash
   #!/bin/bash
   cd /path/to/lunch-menu-sync
   source venv/bin/activate  # if using virtual environment
   python lunch_menu_sync.py \
     --calendar-id "ZmFtaWx5MTQ0NTE1NDA2MTA5NzQ3Nzg3OTFAZ3JvdXAuY2FsZW5kYXIuZ29vZ2xlLmNvbQ" \
     --log-dir /var/log/lunch-sync \
     --log-level INFO
   ```

   Make it executable:
   ```bash
   chmod +x /usr/local/bin/lunch-sync.sh
   ```

2. **Add cron job**:
   ```bash
   crontab -e
   ```

   Add this line to run daily at 7:00 AM:
   ```bash
   0 7 * * * /usr/local/bin/lunch-sync.sh
   ```

### Using Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger to "Daily" at your preferred time
4. Set action to start the Python script with appropriate arguments

## First Run Authorization

When you run the script for the first time:

1. A web browser will open asking you to sign in to Google
2. Sign in with the account that has access to your Family calendar
3. Grant permission to the application
4. The browser will show "The authentication flow has completed"
5. The script will save your authorization token for future runs

## How It Works

### Menu Scraping Process

1. **Date Iteration**: Starts from today and checks each weekday
2. **URL Construction**: Builds URLs like `https://justadashcatering.nutrislice.com/menu/lagrange-sd-102/park-junior-high/2024-01-15`
3. **HTML Parsing**: Looks for the first `div.menu-item-wrapper` element
4. **Menu Extraction**: Gets the text from `span.food-name` within the wrapper
5. **Stop Conditions**: 
   - Finds `menus-empty-menu-day` element (menu not populated)
   - 7 consecutive network failures
   - Reaches maximum days limit

### Calendar Sync Process

1. **Fetch Existing Events**: Gets all "FRHL:" prefixed events from the calendar
2. **Compare and Update**: For each menu item:
   - **No existing event**: Creates new event
   - **Same event exists**: Skips (no action needed)
   - **Different event exists**: Deletes old event and creates new one

### Event Format

- **Title**: "FRHL: [Menu Item]" (e.g., "FRHL: Orange Chicken")
- **Type**: All-day event
- **Color**: Grape (purple)
- **Calendar**: Your Family calendar

## Logging

The script provides detailed logging with multiple levels:

- **ERROR**: Critical errors that prevent operation
- **WARNING**: Issues that don't stop execution
- **INFO**: General operation information
- **DEBUG**: Detailed debugging information
- **VERBOSE**: Same as DEBUG (for compatibility)

Log files are rotated daily and named with the date (e.g., `lunch_menu_sync_20240115.log`).

## Troubleshooting

### Common Issues

**1. "Credentials file not found"**
- Ensure `credentials.json` is in the script directory
- Verify the file was downloaded from Google Cloud Console

**2. "Calendar not found" or permission errors**
- Verify the calendar ID is correct
- Check that your Google account has edit access to the Family calendar
- Try re-running the OAuth flow by deleting `token.json`

**3. "Too many requests" errors**
- The script includes rate limiting, but if you see this error, increase delays
- Google Calendar API allows 1,000 requests per 100 seconds per user

**4. Network timeouts**
- Check your internet connection
- The script retries failed requests up to 7 times
- School website may be temporarily down

**5. "No menu items found"**
- The website structure may have changed
- Enable DEBUG logging to see detailed HTML parsing information
- Website may be showing a different layout

### Debug Mode

Run with debug logging to see detailed information:

```bash
python lunch_menu_sync.py \
  --calendar-id "ZmFtaWx5MTQ0NTE1NDA2MTA5NzQ3Nzg3OTFAZ3JvdXAuY2FsZW5kYXIuZ29vZ2xlLmNvbQ" \
  --log-level DEBUG
```

### Manual Testing

Test the script with a specific date:

```bash
python lunch_menu_sync.py \
  --calendar-id "ZmFtaWx5MTQ0NTE1NDA2MTA5NzQ3Nzg3OTFAZ3JvdXAuY2FsZW5kYXIuZ29vZ2xlLmNvbQ" \
  --start-date 2024-01-15 \
  --max-days 5 \
  --log-level DEBUG
```

## Rate Limits and API Quotas

### Google Calendar API Limits

- **Per-user quota**: 1,000 requests per 100 seconds
- **Per-minute quota**: Varies, but typically 60 requests per minute
- **Daily quota**: 1,000,000 requests per day (more than sufficient)

The script implements conservative rate limiting (1 request per second) to stay well within these limits.

### School Website Rate Limiting

- **Request timeout**: 10 seconds per request
- **Retry policy**: Up to 7 attempts per URL
- **Request spacing**: 1 second between requests
- **User-Agent**: Set to avoid being blocked as a bot

## Security Considerations

- **Credentials**: Keep `credentials.json` secure and don't share it
- **Token**: The `token.json` file contains your access token - keep it private
- **Permissions**: The script only requests calendar access, not full Google account access

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Run with `--log-level DEBUG` to get detailed information
3. Check the log files for specific error messages
4. Verify your Google Cloud Console setup

## License

This script is provided as-is for personal use. Please respect the school website's terms of service and don't overload their servers with excessive requests.
