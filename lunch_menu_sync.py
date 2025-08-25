#!/usr/bin/env python3
"""
Forest Road Lunch Menu to Google Calendar Sync Script

This script scrapes the school lunch menu from the specified URL and syncs it
with a Google Family Calendar as all-day events.
"""

import os
import sys
import warnings

# Suppress urllib3 OpenSSL warnings early
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL 1.1.1+')

import logging
import argparse
import time
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

import urllib3
urllib3.disable_warnings()


class LunchMenuSyncer:
    """Syncs school lunch menu with Google Calendar."""
    
    # Google Calendar API settings
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    # Menu API settings
    API_BASE_URL = "https://justadashcatering.api.nutrislice.com/menu/api/weeks/school/lagrange-sd-102/menu-type/park-junior-high"
    REQUEST_TIMEOUT = 10
    MAX_RETRIES = 7
    
    # Calendar settings
    EVENT_PREFIX = "FRHL: "
    EVENT_COLOR_ID = "3"  # Grape color in Google Calendar
    
    def __init__(self, calendar_id: str, credentials_file: str = "credentials.json", 
                 token_file: str = "token.json", log_level: str = "INFO",
                 log_dir: str = None, enable_stdout_logging: bool = True, 
                 skip_auth: bool = False):
        """
        Initialize the LunchMenuSyncer.
        
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
        
        # Initialize Google Calendar service
        self.calendar_service = None
        if not skip_auth:
            self._authenticate()
        
        # Request session for web scraping
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.logger.info("LunchMenuSyncer initialized successfully")
    
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
            log_file = os.path.join(log_dir, f"lunch_menu_sync_{datetime.now().strftime('%Y%m%d')}.log")
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
    
    def _get_sunday_for_week(self, date: datetime) -> datetime:
        """Get the Sunday date for the week containing the given date."""
        # Python weekday: Monday=0, Sunday=6
        # We want to find the Sunday that is <= the given date
        days_since_sunday = (date.weekday() + 1) % 7  # Convert to days since Sunday
        return date - timedelta(days=days_since_sunday)
    
    def _get_weekly_menu_data(self, sunday_date: datetime) -> Optional[Dict]:
        """
        Fetch weekly menu data from JSON API for the week starting on given Sunday.
        
        Args:
            sunday_date: Sunday date for the week to fetch
            
        Returns:
            JSON response dict or None if error
        """
        date_str = sunday_date.strftime('%Y/%m/%d')
        url = f"{self.API_BASE_URL}/{date_str}/"
        
        self.logger.debug(f"Fetching weekly menu data for week of {sunday_date.strftime('%Y-%m-%d')} from {url}")
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=self.REQUEST_TIMEOUT)
                response.raise_for_status()
                
                json_data = response.json()
                self.logger.debug(f"Successfully fetched weekly menu data for {sunday_date.strftime('%Y-%m-%d')}")
                return json_data
                
            except requests.exceptions.Timeout:
                self.logger.warning(f"Timeout for weekly data {sunday_date.strftime('%Y-%m-%d')}, attempt {attempt + 1}/{self.MAX_RETRIES}")
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Request error for weekly data {sunday_date.strftime('%Y-%m-%d')}, attempt {attempt + 1}/{self.MAX_RETRIES}: {e}")
            except ValueError as e:
                self.logger.warning(f"JSON decode error for weekly data {sunday_date.strftime('%Y-%m-%d')}, attempt {attempt + 1}/{self.MAX_RETRIES}: {e}")
            
            if attempt < self.MAX_RETRIES - 1:
                time.sleep(1)  # Brief delay between retries
        
        self.logger.error(f"Failed to fetch weekly menu data for {sunday_date.strftime('%Y-%m-%d')} after {self.MAX_RETRIES} attempts")
        return None
    
    def _extract_menu_from_day(self, day_data: Dict) -> Optional[str]:
        """
        Extract menu item name from a day's data.
        
        Args:
            day_data: Single day data from the API response
            
        Returns:
            Menu item name or None if no menu/holiday/error
        """
        date_str = day_data.get('date', 'unknown')
        menu_items = day_data.get('menu_items', [])
        
        # Skip if no menu items
        if not menu_items:
            self.logger.debug(f"No menu items for {date_str}")
            return None
        
        # Iterate through menu items to find a valid menu name
        for i, menu_item in enumerate(menu_items):
            # Skip if holiday
            if menu_item.get('is_holiday', False):
                self.logger.info(f"Holiday detected for {date_str}, skipping")
                return None
            
            # First try to get text field
            text_value = menu_item.get('text', '').strip()
            if text_value:
                self.logger.debug(f"Found menu item (text) for {date_str}: {text_value}")
                return text_value
            
            # If text is null/empty, try food.name
            food_data = menu_item.get('food')
            if food_data:
                food_name = food_data.get('name', '').strip()
                if food_name:
                    self.logger.debug(f"Found menu item (food.name) for {date_str}: {food_name}")
                    return food_name
            
            # Continue to next menu item if both text and food.name are null/empty
            self.logger.debug(f"Menu item {i} for {date_str} has no text or food.name, trying next item")
        
        # If we get here, all menu items had null text and no food entries
        self.logger.debug(f"No valid menu items found for {date_str} - all items have null text and no food entries")
        return None
    
    def collect_menus(self, start_date: datetime = None, max_weeks: int = 52) -> List[Tuple[datetime, str]]:
        """
        Collect menu items from start_date using weekly JSON API calls.
        
        Args:
            start_date: Date to start from (defaults to today)
            max_weeks: Maximum weeks to check
            
        Returns:
            List of (date, menu_item) tuples
        """
        if start_date is None:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        menus = []
        consecutive_empty_weeks = 0
        
        self.logger.info(f"Starting menu collection from {start_date.strftime('%Y-%m-%d')}")
        
        # Start from the Sunday of the week containing start_date
        current_sunday = self._get_sunday_for_week(start_date)
        
        for week_num in range(max_weeks):
            # Fetch weekly data
            weekly_data = self._get_weekly_menu_data(current_sunday)
            
            if not weekly_data:
                consecutive_empty_weeks += 1
                if consecutive_empty_weeks >= 3:
                    self.logger.error("Failed to fetch weekly data for 3 consecutive weeks, stopping")
                    break
                current_sunday += timedelta(days=7)  # Move to next week
                continue
            
            # Check if entire week is empty (no menu items published)
            days_data = weekly_data.get('days', [])
            week_has_menus = False
            week_menus_found = 0
            
            for day_data in days_data:
                day_date_str = day_data.get('date')
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
                
                # Check if this day has menu items
                if day_data.get('menu_items'):
                    week_has_menus = True
                
                # Extract menu for this day
                menu_item = self._extract_menu_from_day(day_data)
                if menu_item:
                    menus.append((day_date, menu_item))
                    week_menus_found += 1
                    self.logger.info(f"Collected menu for {day_date.strftime('%Y-%m-%d')}: {menu_item}")
            
            self.logger.debug(f"Week of {current_sunday.strftime('%Y-%m-%d')}: found {week_menus_found} menu items")
            
            # If entire week had no menu items, stop (menus not published yet)
            if not week_has_menus:
                self.logger.info(f"Reached week with no published menus (week of {current_sunday.strftime('%Y-%m-%d')}), stopping")
                break
            
            consecutive_empty_weeks = 0  # Reset counter on successful week
            current_sunday += timedelta(days=7)  # Move to next week
            
            # Rate limiting - 1 request per week
            time.sleep(1)
        
        self.logger.info(f"Menu collection complete. Found {len(menus)} menu items")
        return menus
    
    def _get_existing_frhl_events(self, start_date: datetime, end_date: datetime) -> Dict[str, Dict]:
        """
        Get existing FRHL events from Google Calendar.
        
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
                        self.logger.debug(f"Found existing FRHL event for {event_date}: {summary}")
            
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

    def _delete_calendar_event(self, event_id: str, date_str: str) -> bool:
        """
        Delete a calendar event.
        
        Args:
            event_id: Google Calendar event ID
            date_str: Date string for logging
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Rate limiting for Google Calendar API
            time.sleep(1)
            
            self.calendar_service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            self.logger.info(f"Deleted event for {date_str}")
            return True
            
        except HttpError as e:
            self.logger.error(f"Error deleting event for {date_str}: {e}")
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
        
        # Get existing FRHL events
        existing_events = self._get_existing_frhl_events(start_date, end_date)
        self.logger.debug(f"Found {len(existing_events)} existing FRHL events in date range")
        
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
        self.logger.info("Starting lunch menu sync process")
        
        try:
            # Step 1: Collect menus
            menus = self.collect_menus(start_date, max_weeks)
            
            # Step 2: Sync with calendar
            stats = self.sync_calendar(menus)
            
            self.logger.info("Lunch menu sync process completed successfully")
            return stats
            
        except Exception as e:
            self.logger.error(f"Sync process failed: {e}")
            raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Sync school lunch menu with Google Calendar')
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
            syncer = LunchMenuSyncer(
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
            syncer = LunchMenuSyncer(
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
