"""
Sync Storage Manager

This module provides storage functionality for calendar synchronization data,
including configuration, events, and sync state.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
import aioredis
from datetime import datetime, timedelta

from utils.config import settings

# Set up logging
logger = logging.getLogger(__name__)

class SyncStorageManager:
    """
    Manages storage for calendar synchronization data.
    Supports both Redis and file-based storage.
    """
    
    def __init__(self, use_redis: bool = True):
        """Initialize the storage manager"""
        self.use_redis = use_redis and settings.REDIS_HOST
        self.redis = None
        self.file_storage_path = os.environ.get("STORAGE_PATH", "./storage")
        
        # Create storage directory if it doesn't exist
        if not self.use_redis and not os.path.exists(self.file_storage_path):
            os.makedirs(self.file_storage_path)
    
    async def initialize(self):
        """Initialize storage connections"""
        if self.use_redis:
            try:
                self.redis = await aioredis.from_url(
                    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                    password=settings.REDIS_PASSWORD or None,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info("Redis connection established for sync storage")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.use_redis = False
                logger.info("Falling back to file-based storage")
    
    async def close(self):
        """Close storage connections"""
        if self.use_redis and self.redis:
            await self.redis.close()
    
    async def get_sync_configuration(self) -> Optional[Dict[str, Any]]:
        """Get the current synchronization configuration"""
        if self.use_redis and self.redis:
            config_str = await self.redis.get("sync:configuration")
            return json.loads(config_str) if config_str else None
        else:
            config_path = os.path.join(self.file_storage_path, "sync_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    return json.load(f)
            return None
    
    async def save_sync_configuration(self, config: Dict[str, Any]) -> None:
        """Save the synchronization configuration"""
        if self.use_redis and self.redis:
            await self.redis.set("sync:configuration", json.dumps(config))
        else:
            config_path = os.path.join(self.file_storage_path, "sync_config.json")
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2, default=str)
    
    async def get_agent_events(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get events from an agent's cache"""
        if self.use_redis and self.redis:
            events_str = await self.redis.get(f"sync:agent:{agent_id}:events")
            return json.loads(events_str) if events_str else []
        else:
            events_path = os.path.join(self.file_storage_path, f"agent_{agent_id}_events.json")
            if os.path.exists(events_path):
                with open(events_path, "r") as f:
                    return json.load(f)
            return []
    
    async def save_agent_events(self, agent_id: str, events: List[Dict[str, Any]]) -> None:
        """Save events from an agent to cache"""
        if self.use_redis and self.redis:
            await self.redis.set(f"sync:agent:{agent_id}:events", json.dumps(events))
            # Set expiration to avoid stale data
            await self.redis.expire(f"sync:agent:{agent_id}:events", 60 * 60 * 24)  # 24 hours
        else:
            events_path = os.path.join(self.file_storage_path, f"agent_{agent_id}_events.json")
            with open(events_path, "w") as f:
                json.dump(events, f, indent=2, default=str)
    
    async def get_import_data(self, source_id: str) -> List[Dict[str, Any]]:
        """Get import data for a source"""
        if self.use_redis and self.redis:
            data_str = await self.redis.get(f"sync:import:{source_id}")
            return json.loads(data_str) if data_str else []
        else:
            import_path = os.path.join(self.file_storage_path, f"import_{source_id}.json")
            if os.path.exists(import_path):
                with open(import_path, "r") as f:
                    return json.load(f)
            return []
    
    async def save_import_data(self, source_id: str, data: List[Dict[str, Any]]) -> None:
        """Save import data for a source"""
        if self.use_redis and self.redis:
            await self.redis.set(f"sync:import:{source_id}", json.dumps(data))
            # Set expiration to avoid stale data
            await self.redis.expire(f"sync:import:{source_id}", 60 * 60 * 24)  # 24 hours
        else:
            import_path = os.path.join(self.file_storage_path, f"import_{source_id}.json")
            with open(import_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
    
    async def save_sync_result(self, result: Dict[str, Any]) -> None:
        """Save the result of a sync operation"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        
        if self.use_redis and self.redis:
            # Save latest result
            await self.redis.set("sync:latest_result", json.dumps(result))
            
            # Save to history with timestamp
            await self.redis.lpush("sync:history", json.dumps({
                "timestamp": timestamp,
                "result": result
            }))
            
            # Trim history to last 100 entries
            await self.redis.ltrim("sync:history", 0, 99)
        else:
            # Save latest result
            latest_path = os.path.join(self.file_storage_path, "latest_sync.json")
            with open(latest_path, "w") as f:
                json.dump(result, f, indent=2, default=str)
            
            # Save to history with timestamp
            history_dir = os.path.join(self.file_storage_path, "history")
            if not os.path.exists(history_dir):
                os.makedirs(history_dir)
            
            history_path = os.path.join(history_dir, f"sync_{timestamp}.json")
            with open(history_path, "w") as f:
                json.dump(result, f, indent=2, default=str)
            
            # Clean up old history files (keep last 100)
            history_files = sorted([f for f in os.listdir(history_dir) if f.startswith("sync_")])
            if len(history_files) > 100:
                for old_file in history_files[:-100]:
                    os.remove(os.path.join(history_dir, old_file))
    
    async def save_source_sync_result(self, source_id: str, result: Dict[str, Any]) -> None:
        """Save the result of a sync operation for a specific source"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        
        if self.use_redis and self.redis:
            # Save latest result for this source
            await self.redis.set(f"sync:source:{source_id}:latest_result", json.dumps(result))
            
            # Save to source history with timestamp
            await self.redis.lpush(f"sync:source:{source_id}:history", json.dumps({
                "timestamp": timestamp,
                "result": result
            }))
            
            # Trim history to last 50 entries
            await self.redis.ltrim(f"sync:source:{source_id}:history", 0, 49)
        else:
            # Save latest result for this source
            latest_path = os.path.join(self.file_storage_path, f"source_{source_id}_latest_sync.json")
            with open(latest_path, "w") as f:
                json.dump(result, f, indent=2, default=str)
            
            # Save to source history with timestamp
            history_dir = os.path.join(self.file_storage_path, "history", source_id)
            if not os.path.exists(history_dir):
                os.makedirs(history_dir)
            
            history_path = os.path.join(history_dir, f"sync_{timestamp}.json")
            with open(history_path, "w") as f:
                json.dump(result, f, indent=2, default=str)
            
            # Clean up old history files (keep last 50)
            history_files = sorted([f for f in os.listdir(history_dir) if f.startswith("sync_")])
            if len(history_files) > 50:
                for old_file in history_files[:-50]:
                    os.remove(os.path.join(history_dir, old_file))
    
    async def get_latest_sync_result(self) -> Optional[Dict[str, Any]]:
        """Get the latest sync result"""
        if self.use_redis and self.redis:
            result_str = await self.redis.get("sync:latest_result")
            return json.loads(result_str) if result_str else None
        else:
            latest_path = os.path.join(self.file_storage_path, "latest_sync.json")
            if os.path.exists(latest_path):
                with open(latest_path, "r") as f:
                    return json.load(f)
            return None
    
    async def get_latest_source_sync_result(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest sync result for a specific source"""
        if self.use_redis and self.redis:
            result_str = await self.redis.get(f"sync:source:{source_id}:latest_result")
            return json.loads(result_str) if result_str else None
        else:
            latest_path = os.path.join(self.file_storage_path, f"source_{source_id}_latest_sync.json")
            if os.path.exists(latest_path):
                with open(latest_path, "r") as f:
                    return json.load(f)
            return None