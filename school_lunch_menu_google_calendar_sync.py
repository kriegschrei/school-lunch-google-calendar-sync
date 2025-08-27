#!/usr/bin/env python3
"""
General Purpose Lunch Menu to Google Calendar Sync Script

This script fetches lunch menus from various menu service APIs and syncs them
with a Google Calendar as all-day events. Supports multiple menu sources
including NutriSlice and FDMealPlanner APIs.
"""

import os
import sys
import warnings
import logging
import argparse
import time
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Type
from calendar import monthrange
from abc import ABC, abstractmethod
from collections import defaultdict
from urllib.parse import urlparse

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


# Global configuration
class GlobalConfig:
    """Global configuration settings."""
    
    # API request settings
    REQUEST_TIMEOUT = 10
    MAX_RETRIES = 7
    RATE_LIMIT_DELAY = 1
    
    # Google Calendar settings
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    # Google Calendar color IDs mapping
    CALENDAR_COLORS = {
        'lavender': '1',
        'sage': '2', 
        'grape': '3',
        'flamingo': '4',
        'banana': '5',
        'tangerine': '6',
        'peacock': '7',
        'graphite': '8',
        'blueberry': '9',
        'basil': '10',
        'tomato': '11'
    }


class MenuParser(ABC):
    """Abstract base class for menu parsers."""
    
    def __init__(self, base_url: str, **kwargs):
        """
        Initialize the menu parser.
        
        Args:
            base_url: Base URL for the menu API
            **kwargs: Additional configuration parameters
        """
        self.base_url = base_url
        self.config = kwargs
        
        # Setup text replacements
        self.text_replacements = self._parse_replacements(kwargs.get('text_replacements', []))
        
        # Validate required parameters
        self._validate_config()
    
    def _parse_replacements(self, replacements):
        """
        Parse text replacement configuration.
        
        Args:
            replacements: List of replacement strings in format "find->replace" or dict
            
        Returns:
            List of (find, replace) tuples
        """
        if not replacements:
            return []
        
        parsed = []
        
        # Handle different input formats
        if isinstance(replacements, str):
            # Single replacement string
            replacements = [replacements]
        elif isinstance(replacements, dict):
            # Dictionary format
            for find, replace in replacements.items():
                parsed.append((find, replace))
            return parsed
        
        # List of strings in "find->replace" format
        for replacement in replacements:
            if isinstance(replacement, str) and '->' in replacement:
                find, replace = replacement.split('->', 1)
                parsed.append((find, replace))
            elif isinstance(replacement, (list, tuple)) and len(replacement) == 2:
                parsed.append((replacement[0], replacement[1]))
        
        return parsed
    
    def _apply_text_replacements(self, text: str) -> str:
        """
        Apply configured text replacements to a string.
        
        Args:
            text: Text to process
            
        Returns:
            Text with replacements applied
        """
        if not text or not self.text_replacements:
            return text
        
        result = text
        for find, replace in self.text_replacements:
            result = result.replace(find, replace)
        
        # Clean up any double spaces that might result from replacements
        while '  ' in result:
            result = result.replace('  ', ' ')
        
        return result.strip()
    
    def _get_preferred_name(self, item: Dict, logger: logging.Logger, default_name: str = "Unknown Item") -> str:
        """
        Get the preferred name from a menu item, preferring englishAlternateName over componentName.
        
        Args:
            item: Menu item dictionary
            default_name: Default name to return if no valid names found
            
        Returns:
            Preferred name string
        """
        english_name = item.get('englishAlternateName', '').strip()
        logger.debug(f"english_name: {english_name}")
        component_name = item.get('componentName', '').strip()
        logger.debug(f"component_name: {component_name}")
        
        # Prefer englishAlternateName if it exists and is not "N/A"
        if english_name and english_name.lower() != 'n/a':
            return english_name
        elif component_name:
            return component_name
        else:
            return default_name
    
    @abstractmethod
    def _validate_config(self):
        """Validate parser-specific configuration."""
        pass
    
    @abstractmethod
    def collect_menus(self, start_date: datetime, max_weeks: int, logger: logging.Logger, session: requests.Session) -> List[Tuple[datetime, str, str]]:
        """
        Collect menu items from the API.
        
        Args:
            start_date: Date to start from
            max_weeks: Maximum weeks to check
            logger: Logger instance
            session: Requests session
            
        Returns:
            List of (date, menu_title, menu_details) tuples
        """
        pass


class NutriSliceMenuParser(MenuParser):
    """Parser for NutriSlice menu APIs."""
    
    def _validate_config(self):
        """Validate NutriSlice-specific configuration."""
        # NutriSlice URLs should contain nutrislice.com
        if 'nutrislice.com' not in self.base_url:
            raise ValueError(f"Invalid NutriSlice URL: {self.base_url}")
    
    def _is_weekend(self, date: datetime) -> bool:
        """Check if the given date is a weekend."""
        return date.weekday() >= 5  # Saturday=5, Sunday=6
    
    def _get_sunday_for_week(self, date: datetime) -> datetime:
        """Get the Sunday date for the week containing the given date."""
        # Python weekday: Monday=0, Sunday=6
        # We want to find the Sunday that is <= the given date
        days_since_sunday = (date.weekday() + 1) % 7  # Convert to days since Sunday
        return date - timedelta(days=days_since_sunday)
    
    def _get_weekly_menu_data(self, sunday_date: datetime, logger: logging.Logger, session: requests.Session) -> Optional[Dict]:
        """
        Fetch weekly menu data from JSON API for the week starting on given Sunday.
        
        Args:
            sunday_date: Sunday date for the week to fetch
            logger: Logger instance
            session: Requests session
            
        Returns:
            JSON response dict or None if error
        """
        date_str = sunday_date.strftime('%Y/%m/%d')
        url = f"{self.base_url}/{date_str}/"
        
        logger.debug(f"Fetching weekly menu data for week of {sunday_date.strftime('%Y-%m-%d')} from {url}")
        
        for attempt in range(GlobalConfig.MAX_RETRIES):
            try:
                response = session.get(url, timeout=GlobalConfig.REQUEST_TIMEOUT)
                response.raise_for_status()
                
                json_data = response.json()
                logger.debug(f"Successfully fetched weekly menu data for {sunday_date.strftime('%Y-%m-%d')}")
                return json_data
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout for weekly data {sunday_date.strftime('%Y-%m-%d')}, attempt {attempt + 1}/{GlobalConfig.MAX_RETRIES}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error for weekly data {sunday_date.strftime('%Y-%m-%d')}, attempt {attempt + 1}/{GlobalConfig.MAX_RETRIES}: {e}")
            except ValueError as e:
                logger.warning(f"JSON decode error for weekly data {sunday_date.strftime('%Y-%m-%d')}, attempt {attempt + 1}/{GlobalConfig.MAX_RETRIES}: {e}")
            
            if attempt < GlobalConfig.MAX_RETRIES - 1:
                time.sleep(GlobalConfig.RATE_LIMIT_DELAY)
        
        logger.error(f"Failed to fetch weekly menu data for {sunday_date.strftime('%Y-%m-%d')} after {GlobalConfig.MAX_RETRIES} attempts")
        return None
    
    def _extract_menu_from_day(self, day_data: Dict, logger: logging.Logger) -> Optional[Tuple[str, str]]:
        """
        Extract menu item name and details from a day's data.
        
        Args:
            day_data: Single day data from the API response
            logger: Logger instance
            
        Returns:
            Tuple of (menu_title, menu_details) or None if no menu/holiday/error
        """
        date_str = day_data.get('date', 'unknown')
        menu_items = day_data.get('menu_items', [])
        
        # Skip if no menu items
        if not menu_items:
            logger.debug(f"No menu items for {date_str}")
            return None
        
        # Check for holiday first
        for menu_item in menu_items:
            if menu_item.get('is_holiday', False):
                logger.info(f"Holiday detected for {date_str}, skipping")
                return None
        
        # Get main menu title (first valid item)
        main_title = None
        for i, menu_item in enumerate(menu_items):
            # First try to get text field
            text_value = menu_item.get('text', '').strip()
            if text_value:
                main_title = self._apply_text_replacements(text_value)
                logger.debug(f"Found menu title (text) for {date_str}: {text_value} -> {main_title}")
                break
            
            # If text is null/empty, try food.name
            food_data = menu_item.get('food')
            if food_data:
                food_name = food_data.get('name', '').strip()
                if food_name:
                    main_title = self._apply_text_replacements(food_name)
                    logger.debug(f"Found menu title (food.name) for {date_str}: {food_name} -> {main_title}")
                    break
            
            # Continue to next menu item if both text and food.name are null/empty
            logger.debug(f"Menu item {i} for {date_str} has no text or food.name, trying next item")
        
        if not main_title:
            logger.debug(f"No valid menu title found for {date_str}")
            return None
        
        # Collect all menu items with food.name, sorted by position
        menu_details_items = []
        for menu_item in menu_items:
            food_data = menu_item.get('food')
            if food_data:
                food_name = food_data.get('name', '').strip()
                position = menu_item.get('position', 9999)  # Default high position for items without position
                if food_name:
                    cleaned_food_name = self._apply_text_replacements(food_name)
                    menu_details_items.append((position, cleaned_food_name))
        
        # Sort by position and create details
        menu_details_items.sort(key=lambda x: x[0])
        
        if menu_details_items:
            details_lines = ["MENU ITEMS"]
            for _, food_name in menu_details_items:
                details_lines.append(f"- {food_name}")
            menu_details = "\n".join(details_lines)
        else:
            menu_details = ""
        
        logger.debug(f"Found menu for {date_str}: title='{main_title}', details items={len(menu_details_items)}")
        return (main_title, menu_details)
    
    def collect_menus(self, start_date: datetime, max_weeks: int, logger: logging.Logger, session: requests.Session) -> List[Tuple[datetime, str, str]]:
        """
        Collect menu items from start_date using weekly JSON API calls.
        
        Args:
            start_date: Date to start from
            max_weeks: Maximum weeks to check
            logger: Logger instance
            session: Requests session
            
        Returns:
            List of (date, menu_title, menu_details) tuples
        """
        menus = []
        consecutive_empty_weeks = 0
        
        logger.info(f"Starting NutriSlice menu collection from {start_date.strftime('%Y-%m-%d')}")
        
        # Start from the Sunday of the week containing start_date
        current_sunday = self._get_sunday_for_week(start_date)
        
        for week_num in range(max_weeks):
            # Fetch weekly data
            weekly_data = self._get_weekly_menu_data(current_sunday, logger, session)
            
            if not weekly_data:
                consecutive_empty_weeks += 1
                if consecutive_empty_weeks >= 3:
                    logger.error("Failed to fetch weekly data for 3 consecutive weeks, stopping")
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
                    logger.warning(f"Invalid date format: {day_date_str}")
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
                menu_result = self._extract_menu_from_day(day_data, logger)
                if menu_result:
                    menu_title, menu_details = menu_result
                    menus.append((day_date, menu_title, menu_details))
                    week_menus_found += 1
                    logger.info(f"Collected menu for {day_date.strftime('%Y-%m-%d')}: {menu_title}")
            
            logger.debug(f"Week of {current_sunday.strftime('%Y-%m-%d')}: found {week_menus_found} menu items")
            
            # If entire week had no menu items, stop (menus not published yet)
            if not week_has_menus:
                logger.info(f"Reached week with no published menus (week of {current_sunday.strftime('%Y-%m-%d')}), stopping")
                break
            
            consecutive_empty_weeks = 0  # Reset counter on successful week
            current_sunday += timedelta(days=7)  # Move to next week
            
            # Rate limiting
            time.sleep(GlobalConfig.RATE_LIMIT_DELAY)
        
        logger.info(f"NutriSlice menu collection complete. Found {len(menus)} menu items")
        return menus


class FDMealPlannerParser(MenuParser):
    """Parser for FDMealPlanner menu APIs."""
    
    def _validate_config(self):
        """Validate FDMealPlanner-specific configuration."""
        # FDMealPlanner URLs should contain expected domain
        expected_domains = ['fdmealplanner.com', 'apiservicelocatorstenantquest.fdmealplanner.com']
        url_valid = any(domain in self.base_url for domain in expected_domains)
        
        if not url_valid:
            raise ValueError(f"Invalid FDMealPlanner URL: {self.base_url}")
        
        # Check for required parameters
        required_params = ['account_id', 'location_id', 'meal_period_id', 'tenant_id']
        missing_params = []
        
        for param in required_params:
            if param not in self.config or not self.config[param]:
                missing_params.append(param)
        
        if missing_params:
            raise ValueError(f"Missing required FDMealPlanner parameters: {missing_params}. "
                           f"Please provide: {', '.join(required_params)}")
    
    def _is_weekend(self, date: datetime) -> bool:
        """Check if the given date is a weekend."""
        return date.weekday() >= 5  # Saturday=5, Sunday=6
    
    def _get_monthly_menu_data(self, year: int, month: int, logger: logging.Logger, session: requests.Session) -> Optional[Dict]:
        """
        Fetch monthly menu data from FDMealPlanner API.
        
        Args:
            year: Year (e.g., 2025)
            month: Month (1-12)
            logger: Logger instance
            session: Requests session
            
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
            'accountId': self.config['account_id'],
            'locationId': self.config['location_id'],
            'mealPeriodId': self.config['meal_period_id'],
            'tenantId': self.config['tenant_id'],
            'monthId': str(month),
            'fromDate': from_date,
            'endDate': end_date,
            'timeOffset': '360',
            '_': str(timestamp)
        }
        
        logger.debug(f"Fetching menu data for {year}-{month:02d} from FDMealPlanner API")
        
        for attempt in range(GlobalConfig.MAX_RETRIES):
            try:
                response = session.get(self.base_url, params=params, timeout=GlobalConfig.REQUEST_TIMEOUT)
                response.raise_for_status()
                
                json_data = response.json()
                logger.debug(f"Successfully fetched monthly menu data for {year}-{month:02d}")
                return json_data
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout for monthly data {year}-{month:02d}, attempt {attempt + 1}/{GlobalConfig.MAX_RETRIES}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for monthly data {year}-{month:02d}, attempt {attempt + 1}/{GlobalConfig.MAX_RETRIES}: {e}")
                if attempt == GlobalConfig.MAX_RETRIES - 1:
                    logger.fatal(f"Failed to fetch menu data after {GlobalConfig.MAX_RETRIES} attempts: {e}")
                    sys.exit(1)
            except ValueError as e:
                logger.error(f"JSON decode error for monthly data {year}-{month:02d}, attempt {attempt + 1}/{GlobalConfig.MAX_RETRIES}: {e}")
                if attempt == GlobalConfig.MAX_RETRIES - 1:
                    logger.fatal(f"Invalid JSON response: {e}")
                    sys.exit(1)
            
            if attempt < GlobalConfig.MAX_RETRIES - 1:
                time.sleep(GlobalConfig.RATE_LIMIT_DELAY)
        
        return None
    
    def _extract_menu_from_day(self, day_data: Dict, logger: logging.Logger) -> Optional[Tuple[str, str]]:
        """
        Extract menu item name and details from a day's menu data.
        
        Args:
            day_data: Single day data from the API response
            logger: Logger instance
            
        Returns:
            Tuple of (menu_title, menu_details) or None if no menu found
        """
        str_menu_date = day_data.get('strMenuForDate', 'unknown')
        menu_recipes_data = day_data.get('menuRecipiesData', [])
        
        if not menu_recipes_data:
            logger.debug(f"No menu recipe data for {str_menu_date}")
            return None
        
        # Get menu title using original logic
        menu_title = self._get_menu_title(menu_recipes_data, str_menu_date, logger)
        if not menu_title:
            return None
        
        # Get detailed menu description
        menu_details = self._create_menu_details(menu_recipes_data, logger)
        
        logger.debug(f"Found menu for {str_menu_date}: title='{menu_title}', details chars={len(menu_details)}")
        return (menu_title, menu_details)
    
    def _get_menu_title(self, menu_recipes_data: List[Dict], str_menu_date: str, logger: logging.Logger) -> Optional[str]:
        """
        Extract the main menu title using the original logic.
        
        Args:
            menu_recipes_data: List of menu recipe items
            str_menu_date: Date string for logging
            logger: Logger instance
            
        Returns:
            Menu title or None if no menu found
        """
        # Step 1: Discard/ignore any items with category "Side" or "Condiment"
        non_side_items = []
        for item in menu_recipes_data:
            category = item.get('category', '').strip()
            if category.lower() not in ['side', 'condiment']:
                non_side_items.append(item)
        
        if not non_side_items:
            logger.warning(f"No non-side menu items found for {str_menu_date}")
            return None
        
        # Step 2: Check for special categories (not "Side" or "Lunch Entrée")
        special_categories = []
        lunch_entrees = []
        
        for item in non_side_items:
            category = item.get('category', '').strip()
            if category and category.lower() not in ['side', 'lunch entrée', 'entree', 'condiment']:
                special_categories.append(category)
            elif category.lower() in ['lunch entrée', 'entree']:
                lunch_entrees.append(item)
        
        # If we have special categories, use them
        if special_categories:
            # Remove duplicates and join with pipe
            unique_categories = list(dict.fromkeys(special_categories))  # Preserve order, remove dupes
            # Apply text replacements to each category
            cleaned_categories = [self._apply_text_replacements(cat) for cat in unique_categories]
            menu_name = ' | '.join(cleaned_categories)
            logger.debug(f"Found special category menu for {str_menu_date}: {menu_name}")
            return menu_name
        
        # Step 3: Find lunch entree with highest sequenceNumber where parentComponentId = 0
        if not lunch_entrees:
            logger.warning(f"No lunch entree items found for {str_menu_date}")
            return None
        
        # Filter for items with parentComponentId = 0
        parent_items = [item for item in lunch_entrees if item.get('parentComponentId', -1) == 0]
        
        if not parent_items:
            logger.warning(f"No parent lunch entree items (parentComponentId=0) found for {str_menu_date}")
            return None
        
        # Find items with highest sequence number
        max_sequence = max(item.get('sequenceNumber', 0) for item in parent_items)
        best_items = [item for item in parent_items if item.get('sequenceNumber', 0) == max_sequence]
        
        # Extract names from best items
        menu_names = []
        for item in best_items:
            name_to_use = self._get_preferred_name(item, logger)
            if name_to_use:
                cleaned_name = self._apply_text_replacements(name_to_use)
                menu_names.append(cleaned_name)
        
        if not menu_names:
            logger.warning(f"No valid menu names found for {str_menu_date}")
            return None
        
        # Remove duplicates and join with pipe if multiple
        unique_names = list(dict.fromkeys(menu_names))  # Preserve order, remove dupes
        final_name = ' | '.join(unique_names)
        
        logger.debug(f"Found menu item for {str_menu_date}: {final_name}")
        return final_name
    
    def _create_menu_details(self, menu_recipes_data: List[Dict], logger: logging.Logger) -> str:
        """
        Create detailed menu description from menu recipe data.
        
        Args:
            menu_recipes_data: List of menu recipe items
            logger: Logger instance
            
        Returns:
            Formatted menu details string
        """
        if not menu_recipes_data:
            return ""
        
        # Sort by sequenceNumber
        sorted_items = sorted(menu_recipes_data, key=lambda x: x.get('sequenceNumber', 0))
        
        # Group items by category and track parent relationships
        categories = {}
        parent_items = {}
        child_items = defaultdict(list)
        
        for item in sorted_items:
            category = item.get('category', '').strip()
            parent_id = item.get('parentComponentId', 0)
            
            if parent_id == 0:
                # This is a parent item
                if category not in categories:
                    categories[category] = []
                categories[category].append(item)
                parent_items[item.get('componentId')] = item
            else:
                # This is a child item
                child_items[parent_id].append(item)
        
        # Build description
        description_lines = []
        
        for category, items in categories.items():
            if not category:
                continue
                
            # Add category header in all caps
            description_lines.append(category.upper())
            
            for item in items:
                # Get preferred item name
                item_name = self._get_preferred_name(item, logger, default_name="Unknown Item")
                
                if item_name:
                    cleaned_item_name = self._apply_text_replacements(item_name)
                    description_lines.append(f"- {cleaned_item_name}")
                    
                    # Add any child items (indented)
                    component_id = item.get('componentId')
                    if component_id in child_items:
                        for child in child_items[component_id]:
                            # Get preferred child item name
                            child_name = self._get_preferred_name(child, logger, default_name="Unknown Item")
                            
                            if child_name:
                                cleaned_child_name = self._apply_text_replacements(child_name)
                                description_lines.append(f"  - {cleaned_child_name}")
            
            description_lines.append("")
        
        # Join and clean up
        description = "\n".join(description_lines).strip()
        return description
    
    def collect_menus(self, start_date: datetime, max_weeks: int, logger: logging.Logger, session: requests.Session) -> List[Tuple[datetime, str, str]]:
        """
        Collect menu items from start_date using monthly JSON API calls.
        
        Args:
            start_date: Date to start from
            max_weeks: Maximum weeks to check (converted to months)
            logger: Logger instance
            session: Requests session
            
        Returns:
            List of (date, menu_title, menu_details) tuples
        """
        menus = []
        max_months = (max_weeks // 4) + 2  # Convert weeks to months with buffer
        
        logger.info(f"Starting FDMealPlanner menu collection from {start_date.strftime('%Y-%m-%d')}")
        
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
            monthly_data = self._get_monthly_menu_data(year, month, logger, session)
            processed_months.add(month_key)
            
            if not monthly_data:
                logger.error(f"Failed to fetch monthly data for {year}-{month:02d}")
                break
            
            # Check if results array is empty (month not available yet)
            results = monthly_data.get('result', [])
            if not results:
                logger.info(f"No menu data available for {year}-{month:02d}, stopping")
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
                    logger.warning(f"Invalid date format: {day_date_str}")
                    continue
                
                # Only process dates from our start date forward
                if day_date < start_date:
                    continue
                
                # Skip weekends
                if self._is_weekend(day_date):
                    continue
                
                # Extract menu for this day
                menu_result = self._extract_menu_from_day(day_data, logger)
                if menu_result:
                    menu_title, menu_details = menu_result
                    menus.append((day_date, menu_title, menu_details))
                    month_menus_found += 1
                    logger.info(f"Collected menu for {day_date.strftime('%Y-%m-%d')}: {menu_title}")
            
            logger.debug(f"Month {year}-{month:02d}: found {month_menus_found} menu items")
            
            # Move to next month
            current_date = current_date.replace(day=1) + timedelta(days=32)
            current_date = current_date.replace(day=1)  # First day of next month
            
            # Rate limiting
            time.sleep(GlobalConfig.RATE_LIMIT_DELAY)
        
        logger.info(f"FDMealPlanner menu collection complete. Found {len(menus)} menu items")
        return menus


class MenuParserFactory:
    """Factory for creating menu parsers based on URL patterns."""
    
    @staticmethod
    def create_parser(base_url: str, **kwargs) -> MenuParser:
        """
        Create appropriate menu parser based on URL.
        
        Args:
            base_url: Base URL for the menu API
            **kwargs: Additional configuration parameters
            
        Returns:
            Appropriate MenuParser instance
            
        Raises:
            ValueError: If URL doesn't match any known parser patterns
        """
        url_lower = base_url.lower()
        
        if 'nutrislice.com' in url_lower:
            return NutriSliceMenuParser(base_url, **kwargs)
        elif 'fdmealplanner.com' in url_lower:
            return FDMealPlannerParser(base_url, **kwargs)
        else:
            raise ValueError(f"Unsupported menu API URL: {base_url}. "
                           f"Supported: NutriSlice (nutrislice.com), FDMealPlanner (fdmealplanner.com)")


class GeneralLunchMenuSyncer:
    """General purpose syncer for menu APIs with Google Calendar."""
    
    def __init__(self, calendar_id: str, base_url: str, event_prefix: str = "",
                 event_color: str = "grape", credentials_file: str = "credentials.json", 
                 token_file: str = "token.json", log_level: str = "INFO",
                 log_dir: str = None, enable_stdout_logging: bool = True, 
                 skip_auth: bool = False, reminder: str = None, **parser_config):
        """
        Initialize the GeneralLunchMenuSyncer.
        
        Args:
            calendar_id: Google Calendar ID
            base_url: Base URL for the menu API
            event_prefix: Event title prefix
            event_color: Calendar color name or ID
            credentials_file: Path to Google OAuth credentials file
            token_file: Path to store OAuth token
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            log_dir: Directory for log files (optional)
            enable_stdout_logging: Enable logging to stdout
            skip_auth: Skip Google Calendar authentication (for dry-run mode)
            reminder: Reminder string in format "Xm", "Xh", or "Xd" (e.g., "15m", "1h", "1d")
            **parser_config: Additional configuration for parser
        """
        self.calendar_id = calendar_id
        self.base_url = base_url
        self.credentials_file = credentials_file
        self.token_file = token_file
        
        # Setup event configuration
        self.event_prefix = event_prefix
        self.event_color_id = self._resolve_color(event_color)
        self.reminder = self._parse_reminder(reminder)
        
        # Setup logging
        self._setup_logging(log_level, log_dir, enable_stdout_logging)
        
        # Initialize menu parser
        try:
            self.menu_parser = MenuParserFactory.create_parser(base_url, **parser_config)
            parser_type = type(self.menu_parser).__name__
            self.logger.info(f"Using {parser_type} for URL: {base_url}")
        except ValueError as e:
            self.logger.error(str(e))
            sys.exit(1)
        
        # Initialize Google Calendar service
        self.calendar_service = None
        if not skip_auth:
            self._authenticate()
        
        # Request session for API calls
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.logger.info("GeneralLunchMenuSyncer initialized successfully")
        self.logger.info(f"Event prefix: '{self.event_prefix}', Color ID: '{self.event_color_id}'")
        if self.reminder:
            self.logger.info(f"Reminder configured: {self.reminder}")
        else:
            self.logger.info("No reminders configured")
    
    def _resolve_color(self, color: str) -> str:
        """
        Resolve color name to Google Calendar color ID.
        
        Args:
            color: Color name or ID
            
        Returns:
            Google Calendar color ID
        """
        # If it's already a number, return as-is
        if color.isdigit():
            return color
        
        # Try to resolve color name
        color_lower = color.lower()
        if color_lower in GlobalConfig.CALENDAR_COLORS:
            return GlobalConfig.CALENDAR_COLORS[color_lower]
        
        # Default to grape if unknown color
        self.logger.warning(f"Unknown color '{color}', defaulting to 'grape'")
        return GlobalConfig.CALENDAR_COLORS['grape']
    
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
            log_file = os.path.join(log_dir, f"general_lunch_menu_sync_{datetime.now().strftime('%Y%m%d')}.log")
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def _authenticate(self):
        """Authenticate with Google Calendar API."""
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, GlobalConfig.SCOPES)
        
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
                    self.credentials_file, GlobalConfig.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.calendar_service = build('calendar', 'v3', credentials=creds)
        self.logger.info("Google Calendar authentication successful")
    
    def _parse_reminder(self, reminder: Optional[str]) -> Optional[Dict[str, int]]:
        """
        Parse a reminder string (e.g., "15m", "1h", "1d") into a dictionary.
        
        Args:
            reminder: Reminder string (e.g., "15m", "1h", "1d")
            
        Returns:
            Dictionary with keys 'minutes', 'hours', 'days' or None if no reminder
        """
        if not reminder:
            return None
        
        reminder_lower = reminder.lower()
        if 'm' in reminder_lower:
            minutes = int(reminder_lower.replace('m', ''))
            return {'minutes': minutes}
        elif 'h' in reminder_lower:
            hours = int(reminder_lower.replace('h', ''))
            return {'hours': hours}
        elif 'd' in reminder_lower:
            days = int(reminder_lower.replace('d', ''))
            return {'days': days}
        else:
            self.logger.warning(f"Invalid reminder format: {reminder}. Expected 'Xm', 'Xh', or 'Xd'.")
            return None
    
    def _create_reminders_array(self) -> Optional[List[Dict[str, str]]]:
        """
        Create the reminders array for Google Calendar events.
        
        Returns:
            List of reminder dictionaries or None if no reminders
        """
        if not self.reminder:
            return None
        
        reminders = []
        
        if 'minutes' in self.reminder:
            reminders.append({
                'method': 'popup',
                'minutes': self.reminder['minutes']
            })
        elif 'hours' in self.reminder:
            reminders.append({
                'method': 'popup',
                'minutes': self.reminder['hours'] * 60
            })
        elif 'days' in self.reminder:
            reminders.append({
                'method': 'popup',
                'minutes': self.reminder['days'] * 24 * 60
            })
        
        return reminders if reminders else None
    
    def _reminders_match(self, existing_reminders: Dict, expected_reminders: Optional[List[Dict[str, str]]]) -> bool:
        """
        Check if existing reminders match expected reminders.
        
        Args:
            existing_reminders: Existing reminders from Google Calendar event
            expected_reminders: Expected reminders configuration
            
        Returns:
            True if reminders match, False otherwise
        """
        # If no expected reminders, check if existing reminders are also disabled
        if not expected_reminders:
            # Check if existing reminders are completely disabled
            if not existing_reminders:
                return True
            # For no reminders, we expect useDefault: false and empty overrides
            if (existing_reminders.get('useDefault') == False and 
                not existing_reminders.get('overrides')):
                return True
            return False
        
        # If we expect reminders but existing ones don't match
        if not existing_reminders:
            return False
        
        existing_overrides = existing_reminders.get('overrides', [])
        if len(existing_overrides) != len(expected_reminders):
            return False
        
        # Compare each reminder
        for i, expected in enumerate(expected_reminders):
            existing = existing_overrides[i]
            if (existing.get('method') != expected.get('method') or
                existing.get('minutes') != expected.get('minutes')):
                return False
        
        return True
    
    def collect_menus(self, start_date: datetime = None, max_weeks: int = 8) -> List[Tuple[datetime, str, str]]:
        """
        Collect menu items using the appropriate parser.
        
        Args:
            start_date: Date to start from (defaults to today)
            max_weeks: Maximum weeks to check
            
        Returns:
            List of (date, menu_title, menu_details) tuples
        """
        if start_date is None:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        return self.menu_parser.collect_menus(start_date, max_weeks, self.logger, self.session)
    
    def _get_existing_menu_events(self, start_date: datetime, end_date: datetime) -> Dict[str, Dict]:
        """
        Get existing menu events from Google Calendar.
        
        Args:
            start_date: Start date for search
            end_date: End date for search
            
        Returns:
            Dict mapping date strings to event details
        """
        try:
            # Rate limiting for Google Calendar API
            time.sleep(GlobalConfig.RATE_LIMIT_DELAY)
            
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
            menu_events = {}
            
            for event in all_events:
                summary = event.get('summary', '')
                if summary.startswith(self.event_prefix):
                    # Extract date from event
                    start = event['start']
                    if 'date' in start:  # All-day event
                        event_date = start['date']
                        menu_events[event_date] = event
                        self.logger.debug(f"Found existing menu event for {event_date}: {summary}")
            
            return menu_events
            
        except HttpError as e:
            self.logger.error(f"Error fetching calendar events: {e}")
            return {}
    
    def _create_calendar_event(self, date: datetime, menu_title: str, menu_details: str = "") -> bool:
        """
        Create a new calendar event.
        
        Args:
            date: Date for the event
            menu_title: Menu item title
            menu_details: Detailed menu description
            
        Returns:
            True if successful, False otherwise
        """
        event_title = f"{self.event_prefix}{menu_title}"
        start_date_str = date.strftime('%Y-%m-%d')
        # For all-day events, end date must be the day AFTER the start date (exclusive)
        end_date = date + timedelta(days=1)
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        event = {
            'summary': event_title,
            'start': {'date': start_date_str},
            'end': {'date': end_date_str},
            'colorId': self.event_color_id
        }
        
        # Add description if menu details are provided
        if menu_details:
            event['description'] = menu_details
        
        # Handle reminders - either set custom ones or disable all reminders
        reminders = self._create_reminders_array()
        if reminders:
            event['reminders'] = {'useDefault': False, 'overrides': reminders}
        else:
            # No reminders configured - explicitly disable ALL reminders (including defaults)
            event['reminders'] = {'useDefault': False, 'overrides': []}
        
        try:
            # Rate limiting for Google Calendar API
            time.sleep(GlobalConfig.RATE_LIMIT_DELAY)
            
            created_event = self.calendar_service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            self.logger.info(f"Created event for {start_date_str}: {event_title}")
            return True
            
        except HttpError as e:
            self.logger.error(f"Error creating event for {start_date_str}: {e}")
            return False
    
    def _update_calendar_event(self, event_id: str, date: datetime, menu_title: str, menu_details: str = "") -> bool:
        """
        Update an existing calendar event.
        
        Args:
            event_id: Google Calendar event ID
            date: Date for the event
            menu_title: Menu item title
            menu_details: Detailed menu description
            
        Returns:
            True if successful, False otherwise
        """
        event_title = f"{self.event_prefix}{menu_title}"
        start_date_str = date.strftime('%Y-%m-%d')
        # For all-day events, end date must be the day AFTER the start date (exclusive)
        end_date = date + timedelta(days=1)
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        event = {
            'summary': event_title,
            'start': {'date': start_date_str},
            'end': {'date': end_date_str},
            'colorId': self.event_color_id
        }
        
        # Add description if menu details are provided
        if menu_details:
            event['description'] = menu_details
        
        # Handle reminders - either set custom ones or disable all reminders
        reminders = self._create_reminders_array()
        if reminders:
            event['reminders'] = {'useDefault': False, 'overrides': reminders}
        else:
            # No reminders configured - explicitly disable ALL reminders (including defaults)
            event['reminders'] = {'useDefault': False, 'overrides': []}
        
        try:
            # Rate limiting for Google Calendar API
            time.sleep(GlobalConfig.RATE_LIMIT_DELAY)
            
            updated_event = self.calendar_service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            self.logger.info(f"Updated event for {start_date_str}: {event_title}")
            return True
            
        except HttpError as e:
            self.logger.error(f"Error updating event for {start_date_str}: {e}")
            return False
    
    def sync_calendar(self, menus: List[Tuple[datetime, str, str]]) -> Dict[str, int]:
        """
        Sync menu items with Google Calendar.
        
        Args:
            menus: List of (date, menu_title, menu_details) tuples
            
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
        
        # Get existing menu events
        existing_events = self._get_existing_menu_events(start_date, end_date)
        self.logger.debug(f"Found {len(existing_events)} existing menu events in date range")
        
        stats = {'added': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        for date, menu_title, menu_details in menus:
            date_str = date.strftime('%Y-%m-%d')
            expected_title = f"{self.event_prefix}{menu_title}"
            
            if date_str in existing_events:
                existing_event = existing_events[date_str]
                existing_title = existing_event.get('summary', '')
                existing_color = existing_event.get('colorId', '')
                existing_description = existing_event.get('description', '')
                
                # Check start and end dates
                existing_start = existing_event.get('start', {}).get('date', '')
                existing_end = existing_event.get('end', {}).get('date', '')
                expected_start = date.strftime('%Y-%m-%d')
                expected_end = (date + timedelta(days=1)).strftime('%Y-%m-%d')  # For all-day events, end date = start date + 1 day
                
                # Check reminders
                existing_reminders = existing_event.get('reminders', {})
                expected_reminders = self._create_reminders_array()
                
                # Check if any field needs updating
                title_matches = existing_title == expected_title
                color_matches = existing_color == self.event_color_id
                description_matches = existing_description == menu_details
                start_matches = existing_start == expected_start
                end_matches = existing_end == expected_end
                reminders_match = self._reminders_match(existing_reminders, expected_reminders)
                
                if (title_matches and color_matches and description_matches and 
                    start_matches and end_matches and reminders_match):
                    self.logger.debug(f"Event already exists and matches for {date_str}")
                    stats['skipped'] += 1
                else:
                    # Update existing event
                    changes = []
                    if not title_matches:
                        changes.append(f"title: '{existing_title}' -> '{expected_title}'")
                    if not color_matches:
                        changes.append(f"color: '{existing_color}' -> '{self.event_color_id}'")
                    if not description_matches:
                        changes.append("description updated")
                    if not start_matches:
                        changes.append(f"start date: '{existing_start}' -> '{expected_start}'")
                    if not end_matches:
                        changes.append(f"end date: '{existing_end}' -> '{expected_end}'")
                    if not reminders_match:
                        changes.append("reminders updated")
                    
                    self.logger.info(f"Updating event for {date_str}: {', '.join(changes)}")
                    
                    if self._update_calendar_event(existing_event['id'], date, menu_title, menu_details):
                        stats['updated'] += 1
                    else:
                        stats['errors'] += 1
            else:
                # Create new event
                if self._create_calendar_event(date, menu_title, menu_details):
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
        self.logger.info("Starting general lunch menu sync process")
        
        try:
            # Step 1: Collect menus
            menus = self.collect_menus(start_date, max_weeks)
            
            # Step 2: Sync with calendar
            stats = self.sync_calendar(menus)
            
            self.logger.info("General lunch menu sync process completed successfully")
            return stats
            
        except Exception as e:
            self.logger.error(f"Sync process failed: {e}")
            raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='General purpose lunch menu sync with Google Calendar')
    parser.add_argument('-u', '--base-url', required=True, help='Base URL for the menu API')
    parser.add_argument('-c', '--calendar-id', help='Google Calendar ID (required unless using --dry-run)')
    parser.add_argument('-p', '--event-prefix', default="", help='Event title prefix')
    parser.add_argument('-o', '--event-color', default='grape', help='Google Calendar color name or ID')
    parser.add_argument('-r', '--credentials', default='credentials.json', help='OAuth credentials file')
    parser.add_argument('-t', '--token', default='token.json', help='OAuth token file')
    parser.add_argument('-l', '--log-level', default='INFO', 
                       choices=['DEBUG', 'VERBOSE', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    parser.add_argument('-d', '--log-dir', help='Directory for log files')
    parser.add_argument('-n', '--no-stdout', action='store_true', help='Disable stdout logging')
    parser.add_argument('-w', '--max-weeks', type=int, default=8, help='Maximum weeks to check')
    parser.add_argument('-s', '--start-date', help='Start date (YYYY-MM-DD), defaults to today')
    parser.add_argument('-x', '--dry-run', action='store_true', help='Only collect menus, skip calendar sync')
    parser.add_argument('--reminder', help='Reminder in format "Xm", "Xh", or "Xd" (e.g., "15m", "1h", "1d")')
    
    # FDMealPlanner specific arguments
    parser.add_argument('-a', '--account-id', help='FDMealPlanner account ID')
    parser.add_argument('-i', '--location-id', help='FDMealPlanner location ID')
    parser.add_argument('-m', '--meal-period-id', help='FDMealPlanner meal period ID')
    parser.add_argument('-e', '--tenant-id', help='FDMealPlanner tenant ID')
    
    # Text replacement arguments
    parser.add_argument('-R', '--text-replacements', action='append', 
                       help='Text replacements in format "find->replace" (can be used multiple times)')
    parser.add_argument('--replace-wg', action='store_true', 
                       help='Apply common WG (Whole Grain) replacements for NutriSlice menus')
    
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
    
    # Prepare parser configuration
    parser_config = {}
    if args.account_id:
        parser_config['account_id'] = args.account_id
    if args.location_id:
        parser_config['location_id'] = args.location_id
    if args.meal_period_id:
        parser_config['meal_period_id'] = args.meal_period_id
    if args.tenant_id:
        parser_config['tenant_id'] = args.tenant_id
    
    # Handle text replacements
    text_replacements = []
    if args.text_replacements:
        text_replacements.extend(args.text_replacements)
    
    # Add common WG replacements if requested
    if args.replace_wg:
        text_replacements.extend([
            ' WG->',      # Remove " WG" at the end
            'WG ->',      # Remove "WG " at the beginning  
            ' WG -> '     # Replace " WG " in the middle with single space
        ])
    
    if text_replacements:
        parser_config['text_replacements'] = text_replacements
    
    try:
        if args.dry_run:
            # Dry run mode - only collect menus, skip calendar operations
            print(f"Running in dry-run mode (menu collection only)")
            print(f"Base URL: {args.base_url}")
            
            # Initialize minimal syncer for menu collection only
            syncer = GeneralLunchMenuSyncer(
                calendar_id="dry-run",  # Placeholder
                base_url=args.base_url,
                event_prefix=args.event_prefix,
                event_color=args.event_color,
                credentials_file=args.credentials,
                token_file=args.token,
                log_level=args.log_level,
                log_dir=args.log_dir,
                enable_stdout_logging=not args.no_stdout,
                skip_auth=True,  # Skip Google Calendar authentication
                reminder=args.reminder,
                **parser_config
            )
            
            # Collect menus only
            menus = syncer.collect_menus(start_date=start_date, max_weeks=args.max_weeks)
            
            # Print results
            print(f"\nDry run completed: Found {len(menus)} menu items:")
            for date, menu_title, menu_details in menus:
                print(f"  {date.strftime('%Y-%m-%d')}: {menu_title}")
                if menu_details:
                    # Indent the details for readability
                    detail_lines = menu_details.split('\n')
                    for line in detail_lines:
                        print(f"    {line}")
            
            sys.exit(0)
        else:
            # Normal mode with calendar sync
            syncer = GeneralLunchMenuSyncer(
                calendar_id=args.calendar_id,
                base_url=args.base_url,
                event_prefix=args.event_prefix,
                event_color=args.event_color,
                credentials_file=args.credentials,
                token_file=args.token,
                log_level=args.log_level,
                log_dir=args.log_dir,
                enable_stdout_logging=not args.no_stdout,
                reminder=args.reminder,
                **parser_config
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

