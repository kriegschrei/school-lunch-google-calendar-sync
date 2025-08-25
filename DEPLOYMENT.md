# Deployment Guide

## Server Setup

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/D102-Lunch-Sync.git
cd D102-Lunch-Sync
```

### 2. Set up Python virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Create configuration file
```bash
# Copy example config and customize
cp example_config.sh config.sh
nano config.sh
```

Update `config.sh` with your settings:
- Set your actual Google Calendar ID
- Adjust log level, start date, max weeks as needed
- Set appropriate log directory path

### 4. Set up Google Calendar API credentials
1. Follow the README instructions to get `credentials.json`
2. Place it in the project directory
3. Run a test sync to authenticate and create `token.json`:
   ```bash
   ./run_sync.sh
   ```

### 5. Set up cron job
```bash
# Edit crontab
crontab -e

# Add this line to run at 11 PM every night
0 23 * * * /full/path/to/D102-Lunch-Sync/run_sync.sh
```

## Monitoring

### Check logs
```bash
# View recent sync activity
tail -f logs/cron.log

# View detailed application logs
tail -f logs/lunch_menu_sync_$(date +%Y%m%d).log
```

### Test the sync
```bash
# Manual test run
./run_sync.sh

# Dry run to test menu collection only
./venv/bin/python lunch_menu_sync.py --dry-run --max-weeks 2
```

## File Structure
```
D102-Lunch-Sync/
├── lunch_menu_sync.py      # Main application
├── run_sync.sh             # Wrapper script for cron
├── config.sh               # Your private configuration (create from example)
├── example_config.sh       # Template configuration
├── requirements.txt        # Python dependencies
├── credentials.json        # Google API credentials (you provide)
├── token.json             # OAuth token (auto-generated)
├── venv/                  # Python virtual environment
└── logs/                  # Log files
    ├── cron.log           # Cron execution logs
    └── lunch_menu_sync_*.log  # Daily application logs
```

## Security Notes
- Never commit `credentials.json`, `token.json`, or `config.sh` to version control
- The `.gitignore` file excludes these sensitive files
- Use `example_config.sh` as a template only
