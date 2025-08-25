#!/usr/bin/env python3
"""
Cleanup Duplicate FRHL Events Script

This script finds and removes duplicate FRHL: events from your Google Calendar.
For each date, it keeps the first event and deletes any additional duplicates.
"""

import os
import sys
import warnings
import argparse
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List

# Suppress urllib3 OpenSSL warnings early
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL 1.1.1+')

from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

import urllib3
urllib3.disable_warnings()


class FRHLEventCleanup:
    """Cleans up duplicate FRHL events from Google Calendar."""
    
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    EVENT_PREFIX = "FRHL: "
    
    def __init__(self, calendar_id: str, credentials_file: str = "credentials.json", 
                 token_file: str = "token.json"):
        """Initialize the cleanup tool."""
        self.calendar_id = calendar_id
        self.credentials_file = credentials_file
        self.token_file = token_file
        
        # Initialize Google Calendar service
        self.calendar_service = None
        self._authenticate()
        
        print(f"✅ Connected to Google Calendar: {calendar_id}")
    
    def _authenticate(self):
        """Authenticate with Google Calendar API."""
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("🔄 Refreshing expired credentials...")
                creds.refresh(Request())
            else:
                print("🔐 Starting new OAuth flow...")
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.calendar_service = build('calendar', 'v3', credentials=creds)
    
    def get_all_frhl_events(self, start_date: datetime = None, end_date: datetime = None) -> List[Dict]:
        """Get all FRHL events from the calendar."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=365)  # Last year
        if end_date is None:
            end_date = datetime.now() + timedelta(days=365)   # Next year
        
        print(f"🔍 Searching for FRHL events from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Handle pagination to get all events
        all_events = []
        page_token = None
        
        while True:
            try:
                events_result = self.calendar_service.events().list(
                    calendarId=self.calendar_id,
                    timeMin=f"{start_date.isoformat()}Z",
                    timeMax=f"{end_date.isoformat()}Z",
                    singleEvents=True,
                    orderBy='startTime',
                    pageToken=page_token,
                    maxResults=2500  # Get more events per page
                ).execute()
                
                events = events_result.get('items', [])
                all_events.extend(events)
                
                page_token = events_result.get('nextPageToken')
                if not page_token:
                    break
                    
                print(f"📄 Fetching next page... (found {len(all_events)} events so far)")
                time.sleep(0.1)  # Brief pause between API calls
                
            except HttpError as e:
                print(f"❌ Error fetching events: {e}")
                return []
        
        # Filter for FRHL events only
        frhl_events = []
        for event in all_events:
            summary = event.get('summary', '')
            if summary.startswith(self.EVENT_PREFIX):
                frhl_events.append(event)
        
        print(f"📊 Found {len(frhl_events)} FRHL events out of {len(all_events)} total events")
        return frhl_events
    
    def find_duplicates(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """Group events by date and find duplicates."""
        events_by_date = defaultdict(list)
        
        for event in events:
            start = event.get('start', {})
            if 'date' in start:  # All-day event
                event_date = start['date']
                events_by_date[event_date].append(event)
        
        # Find dates with multiple events
        duplicates = {}
        for date, date_events in events_by_date.items():
            if len(date_events) > 1:
                duplicates[date] = date_events
        
        return duplicates
    
    def show_duplicates(self, duplicates: Dict[str, List[Dict]]):
        """Display duplicate events for review."""
        if not duplicates:
            print("🎉 No duplicate FRHL events found!")
            return
        
        print(f"\n🔍 Found duplicates for {len(duplicates)} dates:")
        print("=" * 80)
        
        total_duplicates = 0
        for date, events in duplicates.items():
            print(f"\n📅 Date: {date} ({len(events)} events)")
            for i, event in enumerate(events):
                summary = event.get('summary', 'No title')
                event_id = event.get('id', 'No ID')
                created = event.get('created', 'Unknown')
                color = event.get('colorId', 'default')
                
                marker = "🟢 KEEP" if i == 0 else "🗑️  DELETE"
                print(f"   {marker} {summary}")
                print(f"      ID: {event_id}")
                print(f"      Created: {created}")
                print(f"      Color: {color}")
            
            total_duplicates += len(events) - 1
        
        print(f"\n📊 Summary: {total_duplicates} duplicate events to remove")
        return total_duplicates
    
    def delete_duplicates(self, duplicates: Dict[str, List[Dict]], dry_run: bool = True) -> int:
        """Delete duplicate events (keeps the first one for each date)."""
        if not duplicates:
            return 0
        
        deleted_count = 0
        
        for date, events in duplicates.items():
            # Keep the first event, delete the rest
            events_to_delete = events[1:]  # Skip first event
            
            print(f"\n📅 Processing {date}: keeping 1, deleting {len(events_to_delete)}")
            
            for event in events_to_delete:
                event_id = event.get('id')
                summary = event.get('summary', 'No title')
                
                if dry_run:
                    print(f"   🔍 DRY RUN: Would delete '{summary}' (ID: {event_id})")
                else:
                    try:
                        self.calendar_service.events().delete(
                            calendarId=self.calendar_id,
                            eventId=event_id
                        ).execute()
                        
                        print(f"   ✅ Deleted '{summary}'")
                        deleted_count += 1
                        time.sleep(0.5)  # Rate limiting
                        
                    except HttpError as e:
                        print(f"   ❌ Error deleting '{summary}': {e}")
        
        return deleted_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Clean up duplicate FRHL calendar events')
    parser.add_argument('--calendar-id', required=True, help='Google Calendar ID')
    parser.add_argument('--credentials', default='credentials.json', help='OAuth credentials file')
    parser.add_argument('--token', default='token.json', help='OAuth token file')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Show what would be deleted without actually deleting (default)')
    parser.add_argument('--delete', action='store_true', 
                       help='Actually delete duplicates (CAUTION: this is permanent!)')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD) for search range')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD) for search range')
    
    args = parser.parse_args()
    
    # Parse dates if provided
    start_date = None
    end_date = None
    
    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        except ValueError:
            print(f"❌ Invalid start date format: {args.start_date}")
            sys.exit(1)
    
    if args.end_date:
        try:
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        except ValueError:
            print(f"❌ Invalid end date format: {args.end_date}")
            sys.exit(1)
    
    # Determine mode
    dry_run = not args.delete
    
    if dry_run:
        print("🔍 DRY RUN MODE: No events will be deleted")
    else:
        print("⚠️  DELETE MODE: Duplicate events will be permanently deleted!")
        response = input("Are you sure you want to proceed? (type 'yes' to confirm): ")
        if response.lower() != 'yes':
            print("❌ Operation cancelled")
            sys.exit(0)
    
    try:
        # Initialize cleanup tool
        cleanup = FRHLEventCleanup(
            calendar_id=args.calendar_id,
            credentials_file=args.credentials,
            token_file=args.token
        )
        
        # Get all FRHL events
        events = cleanup.get_all_frhl_events(start_date, end_date)
        
        if not events:
            print("ℹ️  No FRHL events found")
            sys.exit(0)
        
        # Find duplicates
        duplicates = cleanup.find_duplicates(events)
        
        # Show duplicates
        total_to_delete = cleanup.show_duplicates(duplicates)
        
        if total_to_delete == 0:
            sys.exit(0)
        
        # Delete duplicates
        deleted = cleanup.delete_duplicates(duplicates, dry_run=dry_run)
        
        if dry_run:
            print(f"\n🔍 DRY RUN COMPLETE: {total_to_delete} events would be deleted")
            print("\nTo actually delete duplicates, run with --delete flag")
        else:
            print(f"\n✅ CLEANUP COMPLETE: {deleted} duplicate events deleted")
    
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
