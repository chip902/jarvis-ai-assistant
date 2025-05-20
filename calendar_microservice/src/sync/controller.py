"""
Calendar Synchronization Controller

This module defines the main controller for synchronizing calendars from multiple sources
into a single destination calendar.
"""

import logging
import asyncio
import json
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from fastapi import HTTPException, status

from services.unified_calendar import UnifiedCalendarService
from services.calendar_event import CalendarEvent, CalendarProvider
from sync.architecture import (
    SyncConfiguration, SyncSource, SyncDestination, SyncAgentConfig,
    SyncDirection, SyncFrequency, SyncMethod, ConflictResolution
)
from sync.storage import SyncStorageManager

# Set up logging
logger = logging.getLogger(__name__)

class CalendarSyncController:
    """
    Controller for synchronizing calendars from multiple sources into a unified calendar
    """
    
    def __init__(self, storage_manager: SyncStorageManager):
        """Initialize the calendar sync controller"""
        self.storage = storage_manager
        self.unified_service = UnifiedCalendarService()
        self.active_syncs = set()  # Track active sync operations
        
    async def load_configuration(self) -> SyncConfiguration:
        """Load synchronization configuration from storage"""
        config_data = await self.storage.get_sync_configuration()
        if not config_data:
            raise ValueError("No synchronization configuration found")
        
        return SyncConfiguration.parse_obj(config_data)
    
    async def save_configuration(self, config: SyncConfiguration) -> None:
        """Save synchronization configuration to storage"""
        await self.storage.save_sync_configuration(config.dict())
    
    async def add_sync_source(self, source: SyncSource) -> SyncSource:
        """Add a new synchronization source"""
        config = await self.load_configuration()
        
        # Check for duplicate IDs
        if any(s.id == source.id for s in config.sources):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Source with ID {source.id} already exists"
            )
        
        # Add the new source
        config.sources.append(source)
        await self.save_configuration(config)
        return source
    
    async def update_sync_source(self, source_id: str, updates: Dict[str, Any]) -> SyncSource:
        """Update an existing synchronization source"""
        config = await self.load_configuration()
        
        # Find the source to update
        for i, source in enumerate(config.sources):
            if source.id == source_id:
                # Update the source
                source_dict = source.dict()
                source_dict.update(updates)
                updated_source = SyncSource.parse_obj(source_dict)
                config.sources[i] = updated_source
                await self.save_configuration(config)
                return updated_source
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID {source_id} not found"
        )
    
    async def remove_sync_source(self, source_id: str) -> None:
        """Remove a synchronization source"""
        config = await self.load_configuration()
        
        # Find and remove the source
        for i, source in enumerate(config.sources):
            if source.id == source_id:
                config.sources.pop(i)
                await self.save_configuration(config)
                return
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID {source_id} not found"
        )
    
    async def configure_destination(self, destination: SyncDestination) -> SyncDestination:
        """Configure the synchronization destination"""
        config = await self.load_configuration()
        config.destination = destination
        await self.save_configuration(config)
        return destination
    
    async def add_sync_agent(self, agent: SyncAgentConfig) -> SyncAgentConfig:
        """Add a new synchronization agent"""
        config = await self.load_configuration()
        
        # Check for duplicate IDs
        if any(a.id == agent.id for a in config.agents):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Agent with ID {agent.id} already exists"
            )
        
        # Add the new agent
        config.agents.append(agent)
        await self.save_configuration(config)
        return agent
    
    async def sync_all_calendars(self) -> Dict[str, Any]:
        """
        Synchronize all calendars from all sources to the destination calendar
        """
        if "sync_all" in self.active_syncs:
            return {"status": "in_progress", "message": "Sync already in progress"}
        
        try:
            self.active_syncs.add("sync_all")
            
            # Load configuration
            config = await self.load_configuration()
            
            # Check if destination is configured
            if not config.destination:
                raise ValueError("Destination calendar not configured")
            
            # Results container
            results = {
                "status": "completed",
                "sources_synced": 0,
                "events_synced": 0,
                "errors": [],
                "start_time": datetime.utcnow().isoformat(),
                "end_time": None
            }
            
            # Process each source
            for source in config.sources:
                if not source.enabled:
                    continue
                
                try:
                    # Sync this source
                    source_result = await self.sync_single_source(source.id)
                    results["sources_synced"] += 1
                    results["events_synced"] += source_result.get("events_synced", 0)
                except Exception as e:
                    error_msg = f"Error syncing source {source.id}: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            # Update completion time
            results["end_time"] = datetime.utcnow().isoformat()
            
            # Store sync results
            await self.storage.save_sync_result(results)
            
            return results
        
        finally:
            self.active_syncs.remove("sync_all")
    
    async def sync_single_source(self, source_id: str) -> Dict[str, Any]:
        """
        Synchronize a single source to the destination calendar
        """
        if source_id in self.active_syncs:
            return {"status": "in_progress", "message": f"Sync for source {source_id} already in progress"}
        
        try:
            self.active_syncs.add(source_id)
            
            # Load configuration
            config = await self.load_configuration()
            
            # Find the source
            source = next((s for s in config.sources if s.id == source_id), None)
            if not source:
                raise ValueError(f"Source with ID {source_id} not found")
            
            # Check if source is enabled
            if not source.enabled:
                return {"status": "skipped", "message": "Source is disabled"}
            
            # Check if destination is configured
            if not config.destination:
                raise ValueError("Destination calendar not configured")
            
            # Results container
            results = {
                "source_id": source_id,
                "status": "completed",
                "events_synced": 0,
                "events_failed": 0,
                "errors": [],
                "start_time": datetime.utcnow().isoformat(),
                "end_time": None
            }
            
            # Get events from the source
            if source.sync_method == SyncMethod.API:
                # Direct API synchronization
                events = await self._get_events_from_api_source(source)
            elif source.sync_method == SyncMethod.AGENT:
                # Get events from agent cache
                events = await self._get_events_from_agent_cache(source)
            elif source.sync_method in (SyncMethod.FILE, SyncMethod.EMAIL):
                # Get events from file or email
                events = await self._get_events_from_import(source)
            else:
                raise ValueError(f"Unsupported sync method: {source.sync_method}")
            
            # Write events to destination
            if events:
                write_results = await self._write_events_to_destination(events, config.destination, source)
                results["events_synced"] = write_results.get("success_count", 0)
                results["events_failed"] = write_results.get("failure_count", 0)
                results["errors"].extend(write_results.get("errors", []))
            
            # Update source last sync time
            source.last_sync = datetime.utcnow()
            await self.update_sync_source(source_id, {"last_sync": source.last_sync})
            
            # Update completion time
            results["end_time"] = datetime.utcnow().isoformat()
            
            # Store sync results
            await self.storage.save_source_sync_result(source_id, results)
            
            return results
        
        except Exception as e:
            logger.error(f"Error syncing source {source_id}: {e}")
            raise
        
        finally:
            self.active_syncs.remove(source_id)
    
    async def _get_events_from_api_source(self, source: SyncSource) -> List[CalendarEvent]:
        """Get events from a source using direct API access"""
        events = []
        
        # Determine date range for sync
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=90)  # Sync 90 days by default
        
        # Get events from the provider
        if source.provider_type == CalendarProvider.GOOGLE.value:
            # Use Google Calendar service
            for calendar_id in source.calendars:
                sync_token = source.sync_tokens.get(calendar_id)
                try:
                    result = await self.unified_service.google_service.get_events(
                        token_info=source.credentials,
                        calendar_id=calendar_id,
                        start_date=start_date,
                        end_date=end_date,
                        sync_token=sync_token
                    )
                    events.extend(result.get('events', []))
                    
                    # Update sync token
                    if result.get('nextSyncToken'):
                        source.sync_tokens[calendar_id] = result['nextSyncToken']
                except Exception as e:
                    logger.error(f"Error getting events from Google calendar {calendar_id}: {e}")
                    # Continue with other calendars
        
        elif source.provider_type == CalendarProvider.MICROSOFT.value:
            # Use Microsoft Calendar service
            for calendar_id in source.calendars:
                delta_link = source.sync_tokens.get(calendar_id)
                try:
                    result = await self.unified_service.microsoft_service.get_events(
                        token_info=source.credentials,
                        calendar_id=calendar_id,
                        start_date=start_date,
                        end_date=end_date,
                        delta_link=delta_link
                    )
                    events.extend(result.get('events', []))
                    
                    # Update delta link
                    if result.get('deltaLink'):
                        source.sync_tokens[calendar_id] = result['deltaLink']
                except Exception as e:
                    logger.error(f"Error getting events from Microsoft calendar {calendar_id}: {e}")
                    # Continue with other calendars
        
        return events
    
    async def _get_events_from_agent_cache(self, source: SyncSource) -> List[CalendarEvent]:
        """Get events from an agent's cache in the storage manager"""
        events_data = await self.storage.get_agent_events(source.id)
        if not events_data:
            return []
        
        # Convert to CalendarEvent objects
        events = []
        for event_data in events_data:
            try:
                events.append(CalendarEvent.parse_obj(event_data))
            except Exception as e:
                logger.error(f"Error parsing event from agent cache: {e}")
                # Continue with other events
        
        return events
    
    async def _get_events_from_import(self, source: SyncSource) -> List[CalendarEvent]:
        """Get events from an import file or email"""
        import_data = await self.storage.get_import_data(source.id)
        if not import_data:
            return []
        
        # Parse the import data based on format
        # This would need custom parsers for different formats (iCal, CSV, etc.)
        # For simplicity, we'll assume the data is already in the right format
        events = []
        for event_data in import_data:
            try:
                events.append(CalendarEvent.parse_obj(event_data))
            except Exception as e:
                logger.error(f"Error parsing event from import: {e}")
                # Continue with other events
        
        return events
    
    async def _write_events_to_destination(
        self, 
        events: List[CalendarEvent], 
        destination: SyncDestination,
        source: SyncSource
    ) -> Dict[str, Any]:
        """Write events to the destination calendar"""
        results = {
            "success_count": 0,
            "failure_count": 0,
            "errors": []
        }
        
        # Get existing events from destination to check for conflicts
        existing_events = await self._get_existing_events(destination)
        existing_event_ids = {event.id for event in existing_events}
        
        # Process each event
        for event in events:
            try:
                # Skip if needed based on sync direction
                if source.sync_direction == SyncDirection.WRITE_ONLY:
                    # Skip read-only event (shouldn't happen but just in case)
                    continue
                
                # Check for conflict
                event_in_destination = event.id in existing_event_ids
                
                if event_in_destination:
                    # Handle conflict based on destination's conflict resolution setting
                    existing_event = next((e for e in existing_events if e.id == event.id), None)
                    resolved_event = self._resolve_conflict(event, existing_event, destination.conflict_resolution)
                    
                    # Update event if different
                    if resolved_event != existing_event:
                        success = await self._update_event_in_destination(resolved_event, destination)
                        if success:
                            results["success_count"] += 1
                        else:
                            results["failure_count"] += 1
                else:
                    # New event, create it
                    success = await self._create_event_in_destination(event, destination, source)
                    if success:
                        results["success_count"] += 1
                    else:
                        results["failure_count"] += 1
            
            except Exception as e:
                error_msg = f"Error processing event {event.id}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["failure_count"] += 1
        
        return results
    
    async def _get_existing_events(self, destination: SyncDestination) -> List[CalendarEvent]:
        """Get existing events from the destination calendar"""
        events = []
        
        # Determine date range for sync
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=90)  # Sync 90 days ahead
        
        try:
            if destination.provider_type == CalendarProvider.GOOGLE.value:
                # Use Google Calendar service
                result = await self.unified_service.google_service.get_events(
                    token_info=destination.credentials,
                    calendar_id=destination.calendar_id,
                    start_date=start_date,
                    end_date=end_date
                )
                events.extend(result.get('events', []))
            
            elif destination.provider_type == CalendarProvider.MICROSOFT.value:
                # Use Microsoft Calendar service
                result = await self.unified_service.microsoft_service.get_events(
                    token_info=destination.credentials,
                    calendar_id=destination.calendar_id,
                    start_date=start_date,
                    end_date=end_date
                )
                events.extend(result.get('events', []))
        
        except Exception as e:
            logger.error(f"Error getting existing events from destination: {e}")
        
        return events
    
    def _resolve_conflict(
        self, 
        source_event: CalendarEvent, 
        destination_event: CalendarEvent,
        resolution_strategy: ConflictResolution
    ) -> CalendarEvent:
        """Resolve conflict between source and destination events"""
        if resolution_strategy == ConflictResolution.SOURCE_WINS:
            return source_event
        
        elif resolution_strategy == ConflictResolution.DESTINATION_WINS:
            return destination_event
        
        elif resolution_strategy == ConflictResolution.LATEST_WINS:
            # Check which event was updated more recently
            source_updated = source_event.updated_at or source_event.created_at or datetime.min
            dest_updated = destination_event.updated_at or destination_event.created_at or datetime.min
            
            return source_event if source_updated > dest_updated else destination_event
        
        elif resolution_strategy == ConflictResolution.MANUAL:
            # For manual resolution, keep the destination event and log the conflict
            logger.warning(f"Manual conflict resolution needed for event {source_event.id}")
            # In a real system, you might store this conflict for manual resolution
            return destination_event
        
        # Default fallback
        return source_event
    
    async def _create_event_in_destination(
        self, 
        event: CalendarEvent, 
        destination: SyncDestination,
        source: SyncSource
    ) -> bool:
        """Create a new event in the destination calendar"""
        try:
            # Prepare event for destination
            # In a real implementation, you would need to convert the CalendarEvent
            # back to the format expected by the destination provider's API
            
            # For now, we'll just log a message
            logger.info(f"Would create event '{event.title}' in destination calendar {destination.calendar_id}")
            
            # Mark as successful for this demo
            return True
            
        except Exception as e:
            logger.error(f"Error creating event in destination: {e}")
            return False
    
    async def _update_event_in_destination(
        self, 
        event: CalendarEvent, 
        destination: SyncDestination
    ) -> bool:
        """Update an existing event in the destination calendar"""
        try:
            # Prepare event for destination
            # In a real implementation, you would need to convert the CalendarEvent
            # back to the format expected by the destination provider's API
            
            # For now, we'll just log a message
            logger.info(f"Would update event '{event.title}' in destination calendar {destination.calendar_id}")
            
            # Mark as successful for this demo
            return True
            
        except Exception as e:
            logger.error(f"Error updating event in destination: {e}")
            return False
    
    async def check_agent_heartbeats(self) -> Dict[str, Any]:
        """Check for active sync agents and their status"""
        config = await self.load_configuration()
        
        results = {
            "total_agents": len(config.agents),
            "active_agents": 0,
            "inactive_agents": 0,
            "agent_status": {}
        }
        
        for agent in config.agents:
            if not agent.enabled:
                continue
                
            # Check last check-in time
            is_active = False
            if agent.last_check_in:
                time_since_checkin = datetime.utcnow() - agent.last_check_in
                is_active = time_since_checkin.total_seconds() < (agent.interval_minutes * 60 * 2)
            
            status = "active" if is_active else "inactive"
            results["agent_status"][agent.id] = {
                "name": agent.name,
                "status": status,
                "last_check_in": agent.last_check_in.isoformat() if agent.last_check_in else None
            }
            
            if is_active:
                results["active_agents"] += 1
            else:
                results["inactive_agents"] += 1
        
        return results
    
    async def register_agent_heartbeat(self, agent_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a heartbeat from a sync agent"""
        config = await self.load_configuration()
        
        # Find the agent
        agent = next((a for a in config.agents if a.id == agent_id), None)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent with ID {agent_id} not found"
            )
        
        # Update last check-in time
        agent.last_check_in = datetime.utcnow()
        
        # Check if agent sent events
        if "events" in data:
            # Store events in cache
            await self.storage.save_agent_events(agent_id, data["events"])
        
        # Save updated agent config
        for i, a in enumerate(config.agents):
            if a.id == agent_id:
                config.agents[i] = agent
                break
        
        await self.save_configuration(config)
        
        return {
            "status": "success",
            "timestamp": agent.last_check_in.isoformat(),
            "message": "Heartbeat registered successfully"
        }