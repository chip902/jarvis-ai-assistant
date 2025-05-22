"""
Remote Calendar Synchronization Agent

This module provides a standalone agent that can run in isolated environments
to synchronize calendar data with the central calendar service.
"""

import os
import sys
import json
import asyncio
import logging
import argparse
import aiohttp
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import platform
import socket

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("calendar_agent.log")
    ]
)
logger = logging.getLogger("calendar_agent")


class RemoteCalendarAgent:
    """
    Agent for synchronizing calendars from isolated environments

    This agent can:
    1. Connect to calendar services in isolated environments
    2. Collect calendar data and events
    3. Send data to the central calendar service
    4. Operate in various synchronization modes (API, file, etc.)
    """

    def __init__(self, config_path: str, central_api_url: str = None):
        """Initialize the calendar agent"""
        self.config_path = config_path
        self.config = None
        self.central_api_url = central_api_url
        self.agent_id = None
        self.agent_name = None
        self.environment = platform.node()
        self.running = False
        self.sync_interval = 60  # Default to 60 minutes
        self.http_session = None

        # Store last sync tokens for incremental sync
        self.sync_tokens = {}

    async def initialize(self):
        """Initialize the agent"""
        # Load configuration
        await self.load_config()

        # Create HTTP session
        self.http_session = aiohttp.ClientSession()

        # Register with central service if needed
        if not self.agent_id:
            await self.register_with_central_service()

    async def load_config(self):
        """Load agent configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    self.config = json.load(f)

                # Extract agent details
                self.agent_id = self.config.get("agent_id")
                self.agent_name = self.config.get(
                    "agent_name", f"Agent-{socket.gethostname()}")
                self.environment = self.config.get(
                    "environment", self.environment)
                self.central_api_url = self.config.get(
                    "central_api_url", self.central_api_url)
                self.sync_interval = self.config.get(
                    "sync_interval_minutes", 60)

                # Load any saved sync tokens
                self.sync_tokens = self.config.get("sync_tokens", {})

                logger.info(
                    f"Configuration loaded: Agent ID: {self.agent_id}, Name: {self.agent_name}")
            else:
                # Create initial config
                self.config = {
                    "agent_id": str(uuid.uuid4()),
                    "agent_name": f"Agent-{socket.gethostname()}",
                    "environment": self.environment,
                    "central_api_url": self.central_api_url,
                    "sync_interval_minutes": self.sync_interval,
                    "sync_tokens": {},
                    "calendar_sources": []
                }
                self.agent_id = self.config["agent_id"]
                await self.save_config()

                logger.info(
                    f"Created new configuration with Agent ID: {self.agent_id}")

        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    async def save_config(self):
        """Save agent configuration to file"""
        try:
            # Update sync tokens in config
            self.config["sync_tokens"] = self.sync_tokens

            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2, default=str)

            logger.debug("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    async def register_with_central_service(self):
        """Register this agent with the central calendar service"""
        if not self.central_api_url:
            logger.warning("Cannot register: central_api_url not configured")
            return

        try:
            # Prepare registration data
            agent_data = {
                "id": self.agent_id,
                "name": self.agent_name,
                "environment": self.environment,
                "agent_type": "python",
                "communication_method": "api",
                "api_endpoint": None,  # Will be assigned by central service
                "interval_minutes": self.sync_interval,
                "sources": []  # Will be configured later
            }

            # Register with central service
            url = f"{self.central_api_url}/sync/agents"
            async with self.http_session.post(url, json=agent_data) as response:
                if response.status == 200:
                    result = await response.json()

                    # Update agent ID if it was assigned by the central service
                    if "id" in result and result["id"] != self.agent_id:
                        self.agent_id = result["id"]
                        self.config["agent_id"] = self.agent_id
                        await self.save_config()

                    logger.info(
                        f"Agent registered successfully with ID: {self.agent_id}")
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Failed to register agent: {response.status} - {error_text}")

        except Exception as e:
            logger.error(f"Error registering with central service: {e}")

    async def send_heartbeat(self, include_events: bool = False):
        """Send heartbeat to central service"""
        if not self.central_api_url or not self.agent_id:
            logger.warning(
                "Cannot send heartbeat: missing central_api_url or agent_id")
            return

        try:
            # Prepare heartbeat data
            heartbeat_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": "active",
                "environment": self.environment
            }

            # Include events if requested
            if include_events:
                events = await self.collect_all_events()
                if events:
                    heartbeat_data["events"] = events

            # Send heartbeat to central service
            url = f"{self.central_api_url}/sync/agents/{self.agent_id}/heartbeat"
            async with self.http_session.post(url, json=heartbeat_data) as response:
                if response.status == 200:
                    logger.info("Heartbeat sent successfully")
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Failed to send heartbeat: {response.status} - {error_text}")

        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")

    async def collect_all_events(self) -> List[Dict[str, Any]]:
        """Collect events from all configured calendar sources"""
        all_events = []

        for source in self.config.get("calendar_sources", []):
            try:
                source_type = source.get("type")

                if source_type == "google":
                    events = await self.collect_google_events(source)
                elif source_type == "microsoft":
                    events = await self.collect_microsoft_events(source)
                elif source_type == "exchange":
                    events = await self.collect_exchange_events(source)
                elif source_type == "ical":
                    events = await self.collect_ical_events(source)
                elif source_type == "outlook":
                    events = await self.collect_outlook_events(source)
                elif source_type == "custom":
                    events = await self.collect_custom_events(source)
                else:
                    logger.warning(f"Unknown source type: {source_type}")
                    events = []

                # Add events from this source
                all_events.extend(events)

                # Update last sync time for this source
                source["last_sync"] = datetime.utcnow().isoformat()

            except Exception as e:
                logger.error(
                    f"Error collecting events from source {source.get('name', 'unknown')}: {e}")

        # Save updated configuration
        await self.save_config()

        return all_events

    async def collect_google_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from a Google Calendar source"""
        try:
            # This is a placeholder for real implementation
            # In a real agent, this would use the Google Calendar API client
            logger.info(
                f"Would collect events from Google Calendar: {source.get('name')}")

            # Example implementation:
            # from googleapiclient.discovery import build
            # credentials = get_credentials_from_source(source)
            # service = build('calendar', 'v3', credentials=credentials)
            # events_result = service.events().list(calendarId=source.get('calendar_id'), ...).execute()

            # For now, return empty list
            return []

        except Exception as e:
            logger.error(f"Error collecting Google events: {e}")
            return []

    async def collect_microsoft_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from a Microsoft Calendar source"""
        try:
            # This is a placeholder for real implementation
            # In a real agent, this would use the Microsoft Graph SDK
            logger.info(
                f"Would collect events from Microsoft Calendar: {source.get('name')}")

            # Example implementation:
            # import msal
            # from msgraph.core import GraphClient
            # app = msal.ConfidentialClientApplication(...)
            # graph_client = GraphClient(credentials=...)
            # response = await graph_client.get('/me/calendars/{id}/events')

            # For now, return empty list
            return []

        except Exception as e:
            logger.error(f"Error collecting Microsoft events: {e}")
            return []

    async def collect_exchange_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from an Exchange server"""
        try:
            # This is a placeholder for real implementation
            # In a real agent, this would use the Exchange Web Services API
            logger.info(
                f"Would collect events from Exchange: {source.get('name')}")

            # Example implementation:
            # from exchangelib import Credentials, Account
            # credentials = Credentials(username=source.get('username'), password=source.get('password'))
            # account = Account(primary_smtp_address=source.get('email'), credentials=credentials, ...)
            # events = list(account.calendar.filter(...))

            # For now, return empty list
            return []

        except Exception as e:
            logger.error(f"Error collecting Exchange events: {e}")
            return []

    async def collect_ical_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from an iCal file or URL"""
        try:
            # This is a placeholder for real implementation
            # In a real agent, this would parse iCal files
            logger.info(
                f"Would collect events from iCal: {source.get('name')}")

            # Example implementation:
            # from icalendar import Calendar
            # ical_data = get_ical_data_from_source(source)
            # cal = Calendar.from_ical(ical_data)
            # events = [e for e in cal.walk('VEVENT')]

            # For now, return empty list
            return []

        except Exception as e:
            logger.error(f"Error collecting iCal events: {e}")
            return []

    async def collect_outlook_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events directly from Outlook using COM interface (Windows only)"""
        try:
            # Import the required libraries
            import win32com.client
            from datetime import datetime, timedelta

            logger.info(
                f"Collecting events from Outlook calendar: {source.get('name')}")

            # Define date range
            start_date = datetime.now() - timedelta(days=30)  # Past 30 days
            end_date = datetime.now() + timedelta(days=90)    # Next 90 days

            # Connect to Outlook
            outlook = win32com.client.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")

            # Access the calendar folder
            # Default to main Calendar folder
            calendar_name = source.get('calendar_name', 'Calendar')
            folder_index = 9  # 9 = olFolderCalendar

            # Try to get the specified calendar or default to main Calendar
            try:
                calendar = namespace.GetDefaultFolder(folder_index)
                # If a specific calendar is requested, try to find it
                if calendar_name != 'Calendar':
                    found = False
                    for folder in calendar.Folders:
                        if folder.Name == calendar_name:
                            calendar = folder
                            found = True
                            break
                    if not found:
                        logger.warning(
                            f"Calendar '{calendar_name}' not found, using default Calendar")
            except Exception as e:
                logger.error(f"Error accessing Outlook calendar: {e}")
                return []

            # Format date restriction for Outlook
            restriction = f"[Start] >= '{start_date.strftime('%m/%d/%Y')}' AND [End] <= '{end_date.strftime('%m/%d/%Y')}'"
            appointments = calendar.Items.Restrict(restriction)
            appointments.Sort("[Start]")

            # Process appointments
            events = []
            for appointment in appointments:
                try:
                    # Create normalized event
                    event = {
                        "id": f"outlook_{appointment.EntryID}",
                        "provider": "outlook",
                        "provider_id": appointment.EntryID,
                        "title": appointment.Subject,
                        "description": appointment.Body,
                        "location": appointment.Location,
                        "start_time": appointment.Start.isoformat(),
                        "end_time": appointment.End.isoformat(),
                        "all_day": appointment.AllDayEvent,
                        "organizer": {
                            "email": getattr(appointment, "Organizer", None),
                            "name": getattr(appointment, "OrganizerName", None),
                        },
                        "participants": [],
                        "recurring": appointment.RecurrenceState != 0,
                        "calendar_id": calendar_name,
                        "calendar_name": calendar_name,
                        "status": "confirmed" if appointment.MeetingStatus == 0 else "tentative",
                        "created_at": appointment.CreationTime.isoformat() if hasattr(appointment, "CreationTime") else None,
                        "updated_at": appointment.LastModificationTime.isoformat() if hasattr(appointment, "LastModificationTime") else None,
                    }

                    # Add attendees if available
                    if hasattr(appointment, "Recipients"):
                        for recipient in appointment.Recipients:
                            participant = {
                                "email": recipient.Address if hasattr(recipient, "Address") else None,
                                "name": recipient.Name if hasattr(recipient, "Name") else None,
                                "response_status": "accepted" if recipient.MeetingResponseStatus == 3 else "tentative"
                            }
                            event["participants"].append(participant)

                    events.append(event)
                except Exception as e:
                    logger.error(f"Error processing appointment: {e}")
                    continue

            logger.info(
                f"Collected {len(events)} events from Outlook calendar '{calendar_name}'")
            return events

        except ImportError:
            logger.error(
                "win32com package not available - required for Outlook integration")
            return []
        except Exception as e:
            logger.error(f"Error collecting Outlook events: {e}")
            return []

    async def collect_custom_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from a custom source"""
        try:
            # This is a placeholder for custom implementations
            logger.info(
                f"Would collect events from custom source: {source.get('name')}")

            # Custom sources could be anything:
            # - Database queries
            # - Web scraping
            # - Custom APIs
            # - Local files

            # For now, return empty list
            return []

        except Exception as e:
            logger.error(f"Error collecting custom events: {e}")
            return []

    async def run_sync_cycle(self):
        """Run a complete synchronization cycle"""
        try:
            logger.info("Starting sync cycle")

            # Collect events from all sources
            events = await self.collect_all_events()
            logger.info(f"Collected {len(events)} events from all sources")

            # Send events to central service via heartbeat
            result = await self.send_heartbeat(include_events=True)

            if result:
                logger.info(
                    f"Sync cycle completed: {result.get('message', 'Success')}")
            else:
                logger.warning(
                    "Sync cycle completed but no result from central service")

            return True

        except Exception as e:
            logger.error(f"Error in sync cycle: {e}")
            return False

    async def run(self):
        """Run the agent in continuous mode"""
        try:
            self.running = True
            logger.info(
                f"Agent started. Sync interval: {self.sync_interval} minutes")

            while self.running:
                # Run a sync cycle
                await self.run_sync_cycle()

                # Send a simple heartbeat
                await self.send_heartbeat(include_events=False)

                # Wait for next cycle
                logger.info(
                    f"Waiting {self.sync_interval} minutes until next sync")
                await asyncio.sleep(self.sync_interval * 60)

        except asyncio.CancelledError:
            logger.info("Agent stopping due to cancellation")
            self.running = False

        except Exception as e:
            logger.error(f"Error in agent run loop: {e}")
            self.running = False

        finally:
            # Clean up
            if self.http_session:
                await self.http_session.close()

            logger.info("Agent stopped")

    async def stop(self):
        """Stop the agent"""
        self.running = False
        logger.info("Agent stopping")

        # Clean up
        if self.http_session:
            await self.http_session.close()


async def main():
    """Main function for running the agent"""
    parser = argparse.ArgumentParser(
        description="Remote Calendar Synchronization Agent")
    parser.add_argument("--config", default="agent_config.json",
                        help="Path to configuration file")
    parser.add_argument("--central-api", default=None,
                        help="URL of central calendar service API")
    parser.add_argument("--once", action="store_true",
                        help="Run sync once and exit")
    parser.add_argument("--interval", type=int, default=None,
                        help="Sync interval in minutes")

    args = parser.parse_args()

    try:
        # Create and initialize agent
        agent = RemoteCalendarAgent(
            config_path=args.config, central_api_url=args.central_api)
        await agent.initialize()

        # Override sync interval if specified
        if args.interval:
            agent.sync_interval = args.interval
            agent.config["sync_interval_minutes"] = args.interval
            await agent.save_config()

        if args.once:
            # Run one sync cycle and exit
            await agent.run_sync_cycle()
        else:
            # Run continuously
            await agent.run()

    except KeyboardInterrupt:
        logger.info("Agent interrupted by user")

    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    asyncio.run(main())
