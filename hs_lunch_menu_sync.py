#!/usr/bin/env python3
"""
High School Lunch Menu to Google Calendar Sync Script

This script fetches the high school lunch menu from the FDMealPlanner API and syncs it
with a Google Family Calendar as all-day events.
"""

import os
import sys
import warnings
import logging
import argparse
import time
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from calendar import monthrange

# Suppress urllib3 OpenSSL warnings early
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL 1.1.1+')

import requests
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

import urllib3
urllib3.disable_warnings()


class HSLunchMenuSyncer:
    """Syncs high school lunch menu with Google Calendar."""
    
    # Google Calendar API settings
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    # Calendar settings
    EVENT_PREFIX = "LTHSS: "  # Lyons Township High School South
    EVENT_COLOR_ID = "7"  # Peacock color in Google Calendar
    
    # API settings
    API_BASE_URL = "https://apiservicelocatorstenantquest.fdmealplanner.com/api/v1/data-locator-webapi/4/meals"
    REQUEST_TIMEOUT = 10
    MAX_RETRIES = 3
    
    def __init__(self, calendar_id: str, credentials_file: str = "credentials.json", 
                 token_file: str = "token.json", log_level: str = "INFO",
                 log_dir: str = None, enable_stdout_logging: bool = True, 
                 skip_auth: bool = False):
        """
        Initialize the HSLunchMenuSyncer.
        
        Args:
            calendar_id: Google Calendar ID
            credentials_file: Path to Google OAuth credentials file
            token_file: Path to store OAuth token
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            log_dir: Directory for log files (optional)
            enable_stdout_logging: Enable logging to stdout
            skip_auth: Skip Google Calendar authentication (for dry-run mode)
        """
        self.calendar_id = calendar_id
        self.credentials_file = credentials_file
        self.token_file = token_file
        
        # Setup logging
        self._setup_logging(log_level, log_dir, enable_stdout_logging)
        
        # Get API configuration from environment
        self.account_id = os.getenv('HS_ACCOUNT_ID', '10091')
        self.location_id = os.getenv('HS_LOCATION_ID', '10320')
        self.meal_period_id = os.getenv('HS_MEAL_PERIOD_ID', '2')
        self.tenant_id = os.getenv('HS_TENANT_ID', '4')
        
        # Initialize Google Calendar service
        self.calendar_service = None
        if not skip_auth:
            self._authenticate()
        
        # Request session for API calls
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.logger.info("HSLunchMenuSyncer initialized successfully")
    
    def _setup_logging(self, log_level: str, log_dir: str, enable_stdout_logging: bool):
        """Setup logging configuration."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Add stdout handler if enabled
        if enable_stdout_logging:
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setFormatter(formatter)
            self.logger.addHandler(stdout_handler)
        
        # Add file handler if log_dir is specified
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"hs_lunch_menu_sync_{datetime.now().strftime('%Y%m%d')}.log")
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def _authenticate(self):
        """Authenticate with Google Calendar API."""
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self.logger.info("Refreshing expired credentials")
                creds.refresh(Request())
            else:
                self.logger.info("Starting new OAuth flow")
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.calendar_service = build('calendar', 'v3', credentials=creds)
        self.logger.info("Google Calendar authentication successful")
    
    def _is_weekend(self, date: datetime) -> bool:
        """Check if the given date is a weekend."""
        return date.weekday() >= 5  # Saturday=5, Sunday=6
    
    def _get_monthly_menu_data(self, year: int, month: int) -> Optional[Dict]:
        """
        Fetch monthly menu data from FDMealPlanner API.
        
        Args:
            year: Year (e.g., 2025)
            month: Month (1-12)
            
        Returns:
            JSON response dict or None if error
        """
        # Get first and last day of the month
        first_day = datetime(year, month, 1)
        last_day_num = monthrange(year, month)[1]
        last_day = datetime(year, month, last_day_num)
        
        from_date = first_day.strftime('%Y%%2F%m%%2F%d')
        end_date = last_day.strftime('%Y%%2F%m%%2F%d')
        
        # Generate timestamp-like parameter
        timestamp = int(time.time() * 1000)
        
        params = {
            'menuId': '0',
            'accountId': self.account_id,
            'locationId': self.location_id,
            'mealPeriodId': self.meal_period_id,
            'tenantId': self.tenant_id,
            'monthId': str(month),
            'fromDate': from_date,
            'endDate': end_date,
            'timeOffset': '360',
            '_': str(timestamp)
        }
        
        self.logger.debug(f"Fetching menu data for {year}-{month:02d} from FDMealPlanner API")
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(self.API_BASE_URL, params=params, timeout=self.REQUEST_TIMEOUT)
                response.raise_for_status()
                
                json_data = response.json()
                self.logger.debug(f"Successfully fetched monthly menu data for {year}-{month:02d}")
                return json_data
                
            except requests.exceptions.Timeout:
                self.logger.warning(f"Timeout for monthly data {year}-{month:02d}, attempt {attempt + 1}/{self.MAX_RETRIES}")
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error for monthly data {year}-{month:02d}, attempt {attempt + 1}/{self.MAX_RETRIES}: {e}")
                if attempt == self.MAX_RETRIES - 1:
                    self.logger.fatal(f"Failed to fetch menu data after {self.MAX_RETRIES} attempts: {e}")
                    sys.exit(1)
            except ValueError as e:
                self.logger.error(f"JSON decode error for monthly data {year}-{month:02d}, attempt {attempt + 1}/{self.MAX_RETRIES}: {e}")
                if attempt == self.MAX_RETRIES - 1:
                    self.logger.fatal(f"Invalid JSON response: {e}")
                    sys.exit(1)
            
            if attempt < self.MAX_RETRIES - 1:
                time.sleep(1)  # Brief delay between retries
        
        return None
    
    def _extract_menu_from_day(self, day_data: Dict) -> Optional[str]:
        """
        Extract menu item name from a day's menu data.
        
        Args:
            day_data: Single day data from the API response
            
        Returns:
            Menu item name or None if no menu found
        """
        str_menu_date = day_data.get('strMenuForDate', 'unknown')
        menu_recipes_data = day_data.get('menuRecipiesData', [])
        
        if not menu_recipes_data:
            self.logger.debug(f"No menu recipe data for {str_menu_date}")
            return None
        
        # Step 1: Discard/ignore any items with category "Side"
        non_side_items = []
        for item in menu_recipes_data:
            category = item.get('category', '').strip()
            if category.lower() not in ['side', 'condiment']:
                non_side_items.append(item)
        
        if not non_side_items:
            self.logger.warning(f"No non-side menu items found for {str_menu_date}")
            return None
        
        # Step 2: Check for special categories (not "Side" or "Lunch Entrée")
        special_categories = []
        lunch_entrees = []
        
        for item in non_side_items:
            category = item.get('category', '').strip()
            if category and category.lower() not in ['side', 'lunch entrée', 'entree']:
                special_categories.append(category)
            elif category.lower() in ['lunch entrée', 'entree']:
                lunch_entrees.append(item)
        
        # If we have special categories, use them
        if special_categories:
            # Remove duplicates and join with pipe
            unique_categories = list(dict.fromkeys(special_categories))  # Preserve order, remove dupes
            menu_name = ' | '.join(unique_categories)
            self.logger.debug(f"Found special category menu for {str_menu_date}: {menu_name}")
            return menu_name
        
        # Step 3: Find lunch entree with highest sequenceNumber where parentComponentId = 0
        if not lunch_entrees:
            self.logger.warning(f"No lunch entree items found for {str_menu_date}")
            return None
        
        # Filter for items with parentComponentId = 0
        parent_items = [item for item in lunch_entrees if item.get('parentComponentId', -1) == 0]
        
        if not parent_items:
            self.logger.warning(f"No parent lunch entree items (parentComponentId=0) found for {str_menu_date}")
            return None
        
        # Find items with highest sequence number
        max_sequence = max(item.get('sequenceNumber', 0) for item in parent_items)
        best_items = [item for item in parent_items if item.get('sequenceNumber', 0) == max_sequence]
        
        # Extract names from best items
        menu_names = []
        for item in best_items:
            english_name = item.get('componentEnglishName', '').strip()
            component_name = item.get('componentName', '').strip()
            
            name_to_use = english_name if english_name else component_name
            if name_to_use:
                menu_names.append(name_to_use)
        
        if not menu_names:
            self.logger.warning(f"No valid menu names found for {str_menu_date}")
            return None
        
        # Remove duplicates and join with pipe if multiple
        unique_names = list(dict.fromkeys(menu_names))  # Preserve order, remove dupes
        final_name = ' | '.join(unique_names)
        
        self.logger.debug(f"Found menu item for {str_menu_date}: {final_name}")
        return final_name
    
    def collect_menus(self, start_date: datetime = None, max_weeks: int = 8) -> List[Tuple[datetime, str]]:
        """
        Collect menu items from start_date using monthly JSON API calls.
        
        Args:
            start_date: Date to start from (defaults to today)
            max_weeks: Maximum weeks to check (converted to months)
            
        Returns:
            List of (date, menu_item) tuples
        """
        if start_date is None:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        menus = []
        max_months = (max_weeks // 4) + 2  # Convert weeks to months with buffer
        
        self.logger.info(f"Starting menu collection from {start_date.strftime('%Y-%m-%d')}")
        
        current_date = start_date
        processed_months = set()
        
        for month_num in range(max_months):
            year = current_date.year
            month = current_date.month
            
            # Skip if we've already processed this month
            month_key = (year, month)
            if month_key in processed_months:
                current_date = current_date.replace(day=1) + timedelta(days=32)  # Move to next month
                current_date = current_date.replace(day=1)  # First day of next month
                continue
            
            # Fetch monthly data
            monthly_data = self._get_monthly_menu_data(year, month)
            processed_months.add(month_key)
            
            if not monthly_data:
                self.logger.error(f"Failed to fetch monthly data for {year}-{month:02d}")
                break
            
            # Check if results array is empty (month not available yet)
            results = monthly_data.get('result', [])
            if not results:
                self.logger.info(f"No menu data available for {year}-{month:02d}, stopping")
                break
            
            month_menus_found = 0
            
            # Process each day in the month
            for day_data in results:
                day_date_str = day_data.get('strMenuForDate')
                if not day_date_str:
                    continue
                
                try:
                    day_date = datetime.strptime(day_date_str, '%Y-%m-%d')
                except ValueError:
                    self.logger.warning(f"Invalid date format: {day_date_str}")
                    continue
                
                # Only process dates from our start date forward
                if day_date < start_date:
                    continue
                
                # Skip weekends
                if self._is_weekend(day_date):
                    continue
                
                # Extract menu for this day
                menu_item = self._extract_menu_from_day(day_data)
                if menu_item:
                    menus.append((day_date, menu_item))
                    month_menus_found += 1
                    self.logger.info(f"Collected menu for {day_date.strftime('%Y-%m-%d')}: {menu_item}")
            
            self.logger.debug(f"Month {year}-{month:02d}: found {month_menus_found} menu items")
            
            # Move to next month
            current_date = current_date.replace(day=1) + timedelta(days=32)
            current_date = current_date.replace(day=1)  # First day of next month
            
            # Rate limiting - 1 request per month
            time.sleep(1)
        
        self.logger.info(f"Menu collection complete. Found {len(menus)} menu items")
        return menus
    
    def _get_existing_frhl_events(self, start_date: datetime, end_date: datetime) -> Dict[str, Dict]:
        """
        Get existing LTHSS events from Google Calendar.
        
        Args:
            start_date: Start date for search
            end_date: End date for search
            
        Returns:
            Dict mapping date strings to event details
        """
        try:
            # Rate limiting for Google Calendar API
            time.sleep(1)
            
            self.logger.debug(f"Fetching existing events from {start_date.isoformat()}Z to {end_date.isoformat()}Z")
            
            # Handle pagination to get all events
            all_events = []
            page_token = None
            
            while True:
                events_result = self.calendar_service.events().list(
                    calendarId=self.calendar_id,
                    timeMin=f"{start_date.isoformat()}Z",
                    timeMax=f"{end_date.isoformat()}Z",
                    singleEvents=True,
                    orderBy='startTime',
                    pageToken=page_token
                ).execute()
                
                events = events_result.get('items', [])
                all_events.extend(events)
                
                page_token = events_result.get('nextPageToken')
                if not page_token:
                    break
                    
                self.logger.debug(f"Fetching next page of events (token: {page_token[:20]}...)")
            
            self.logger.debug(f"Total events fetched from Google Calendar: {len(all_events)}")
            frhl_events = {}
            
            for event in all_events:
                summary = event.get('summary', '')
                if summary.startswith(self.EVENT_PREFIX):
                    # Extract date from event
                    start = event['start']
                    if 'date' in start:  # All-day event
                        event_date = start['date']
                        frhl_events[event_date] = event
                        self.logger.debug(f"Found existing LTHSS event for {event_date}: {summary}")
            
            return frhl_events
            
        except HttpError as e:
            self.logger.error(f"Error fetching calendar events: {e}")
            return {}
    
    def _create_calendar_event(self, date: datetime, menu_item: str) -> bool:
        """
        Create a new calendar event.
        
        Args:
            date: Date for the event
            menu_item: Menu item name
            
        Returns:
            True if successful, False otherwise
        """
        event_title = f"{self.EVENT_PREFIX}{menu_item}"
        date_str = date.strftime('%Y-%m-%d')
        
        event = {
            'summary': event_title,
            'start': {'date': date_str},
            'end': {'date': date_str},
            'colorId': self.EVENT_COLOR_ID
        }
        
        try:
            # Rate limiting for Google Calendar API
            time.sleep(1)
            
            created_event = self.calendar_service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            self.logger.info(f"Created event for {date_str}: {event_title}")
            return True
            
        except HttpError as e:
            self.logger.error(f"Error creating event for {date_str}: {e}")
            return False
    
    def _update_calendar_event(self, event_id: str, date: datetime, menu_item: str) -> bool:
        """
        Update an existing calendar event.
        
        Args:
            event_id: Google Calendar event ID
            date: Date for the event
            menu_item: Menu item name
            
        Returns:
            True if successful, False otherwise
        """
        event_title = f"{self.EVENT_PREFIX}{menu_item}"
        date_str = date.strftime('%Y-%m-%d')
        
        event = {
            'summary': event_title,
            'start': {'date': date_str},
            'end': {'date': date_str},
            'colorId': self.EVENT_COLOR_ID
        }
        
        try:
            # Rate limiting for Google Calendar API
            time.sleep(1)
            
            updated_event = self.calendar_service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            self.logger.info(f"Updated event for {date_str}: {event_title}")
            return True
            
        except HttpError as e:
            self.logger.error(f"Error updating event for {date_str}: {e}")
            return False
    
    def sync_calendar(self, menus: List[Tuple[datetime, str]]) -> Dict[str, int]:
        """
        Sync menu items with Google Calendar.
        
        Args:
            menus: List of (date, menu_item) tuples
            
        Returns:
            Dict with counts of actions taken
        """
        if not menus:
            self.logger.info("No menus to sync")
            return {'added': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        # Get date range
        start_date = min(menu[0] for menu in menus)
        end_date = max(menu[0] for menu in menus) + timedelta(days=1)
        
        self.logger.debug(f"Syncing calendar events from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        self.logger.debug(f"Total menus to sync: {len(menus)}")
        
        # Get existing LTHSS events
        existing_events = self._get_existing_frhl_events(start_date, end_date)
        self.logger.debug(f"Found {len(existing_events)} existing LTHSS events in date range")
        
        stats = {'added': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        for date, menu_item in menus:
            date_str = date.strftime('%Y-%m-%d')
            expected_title = f"{self.EVENT_PREFIX}{menu_item}"
            
            if date_str in existing_events:
                existing_event = existing_events[date_str]
                existing_title = existing_event.get('summary', '')
                existing_color = existing_event.get('colorId', '')
                
                # Check if title or color needs updating
                title_matches = existing_title == expected_title
                color_matches = existing_color == self.EVENT_COLOR_ID
                
                if title_matches and color_matches:
                    self.logger.debug(f"Event already exists and matches for {date_str}")
                    stats['skipped'] += 1
                else:
                    # Update existing event
                    changes = []
                    if not title_matches:
                        changes.append(f"title: '{existing_title}' -> '{expected_title}'")
                    if not color_matches:
                        changes.append(f"color: '{existing_color}' -> '{self.EVENT_COLOR_ID}'")
                    
                    self.logger.info(f"Updating event for {date_str}: {', '.join(changes)}")
                    
                    if self._update_calendar_event(existing_event['id'], date, menu_item):
                        stats['updated'] += 1
                    else:
                        stats['errors'] += 1
            else:
                # Create new event
                if self._create_calendar_event(date, menu_item):
                    stats['added'] += 1
                else:
                    stats['errors'] += 1
        
        self.logger.info(f"Calendar sync complete: {stats}")
        return stats
    
    def run(self, start_date: datetime = None, max_weeks: int = 8) -> Dict[str, int]:
        """
        Run the complete sync process.
        
        Args:
            start_date: Date to start from (defaults to today)
            max_weeks: Maximum weeks to check
            
        Returns:
            Dict with statistics of operations performed
        """
        self.logger.info("Starting high school lunch menu sync process")
        
        try:
            # Step 1: Collect menus
            menus = self.collect_menus(start_date, max_weeks)
            
            # Step 2: Sync with calendar
            stats = self.sync_calendar(menus)
            
            self.logger.info("High school lunch menu sync process completed successfully")
            return stats
            
        except Exception as e:
            self.logger.error(f"Sync process failed: {e}")
            raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Sync high school lunch menu with Google Calendar')
    parser.add_argument('--calendar-id', help='Google Calendar ID (required unless using --dry-run)')
    parser.add_argument('--credentials', default='credentials.json', help='OAuth credentials file')
    parser.add_argument('--token', default='token.json', help='OAuth token file')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'VERBOSE', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    parser.add_argument('--log-dir', help='Directory for log files')
    parser.add_argument('--no-stdout', action='store_true', help='Disable stdout logging')
    parser.add_argument('--max-weeks', type=int, default=8, help='Maximum weeks to check')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD), defaults to today')
    parser.add_argument('--dry-run', action='store_true', help='Only collect menus, skip calendar sync')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.dry_run and not args.calendar_id:
        parser.error("--calendar-id is required unless using --dry-run")
    
    # Parse start date if provided
    start_date = None
    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        except ValueError:
            print(f"Invalid start date format: {args.start_date}")
            sys.exit(1)
    
    try:
        if args.dry_run:
            # Dry run mode - only collect menus, skip calendar operations
            print("Running in dry-run mode (menu collection only)")
            
            # Initialize minimal syncer for menu collection only
            syncer = HSLunchMenuSyncer(
                calendar_id="dry-run",  # Placeholder
                credentials_file=args.credentials,
                token_file=args.token,
                log_level=args.log_level,
                log_dir=args.log_dir,
                enable_stdout_logging=not args.no_stdout,
                skip_auth=True  # Skip Google Calendar authentication
            )
            
            # Collect menus only
            menus = syncer.collect_menus(start_date=start_date, max_weeks=args.max_weeks)
            
            # Print results
            print(f"\nDry run completed: Found {len(menus)} menu items:")
            for date, menu_item in menus:
                print(f"  {date.strftime('%Y-%m-%d')}: {menu_item}")
            
            sys.exit(0)
        else:
            # Normal mode with calendar sync
            syncer = HSLunchMenuSyncer(
                calendar_id=args.calendar_id,
                credentials_file=args.credentials,
                token_file=args.token,
                log_level=args.log_level,
                log_dir=args.log_dir,
                enable_stdout_logging=not args.no_stdout
            )
            
            # Run sync
            stats = syncer.run(start_date=start_date, max_weeks=args.max_weeks)
            
            # Print summary
            print(f"Sync completed: {stats['added']} added, {stats['updated']} updated, "
                  f"{stats['skipped']} skipped, {stats['errors']} errors")
            
            # Exit with error code if there were errors
            sys.exit(1 if stats['errors'] > 0 else 0)
        
    except KeyboardInterrupt:
        print("\nSync interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
