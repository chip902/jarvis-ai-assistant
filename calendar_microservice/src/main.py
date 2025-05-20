#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "python-dotenv",
#   "fastapi",
#   "uvicorn",
#   "openai-agents",
#   "google-auth-oauthlib",
#   "google-api-python-client",
#   "msal",
#   "redis",
#   "aiohttp",
#   "aioredis",
#   "python-jose",
#   "tenacity"
# ]
# ///

import os
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from agents.mcp.server import MCPServerStdio

# Import local modules
from api.router import router as api_router
from api.sync_router import router as sync_router
from mcp.calendar_server import setup_calendar_mcp_server
from sync.storage import SyncStorageManager
from sync.controller import CalendarSyncController
from utils.config import settings

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Calendar Integration Microservice",
    description="Microservice for integrating multiple calendar providers",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(api_router, prefix="/api")
app.include_router(sync_router, prefix="/api")

# MCP server instance (will be initialized on startup)
calendar_mcp_server = None

# Sync storage and controller instances
sync_storage = None
sync_controller = None

# Background task for periodic sync
sync_task = None

async def periodic_sync(interval_minutes: int = 60):
    """Run periodic synchronization"""
    while True:
        try:
            # Wait for the specified interval
            await asyncio.sleep(interval_minutes * 60)
            
            # Run synchronization
            await sync_controller.sync_all_calendars()
        except asyncio.CancelledError:
            # Task is being cancelled, clean up and exit
            break
        except Exception as e:
            print(f"Error in periodic sync: {e}")
            # Continue with the loop after error

@app.on_event("startup")
async def startup_event():
    global calendar_mcp_server, sync_storage, sync_controller, sync_task
    
    # Initialize the Calendar MCP server
    calendar_mcp_server = await setup_calendar_mcp_server()
    print(f"Calendar MCP server started: {calendar_mcp_server.name}")
    
    # List available tools to verify connection
    tools = await calendar_mcp_server.list_tools()
    print(f"Found {len(tools)} tools available from Calendar MCP server")
    
    # Initialize sync storage
    sync_storage = SyncStorageManager()
    await sync_storage.initialize()
    print("Sync storage initialized")
    
    # Initialize sync controller
    sync_controller = CalendarSyncController(sync_storage)
    print("Sync controller initialized")
    
    # Start periodic sync task
    sync_interval = int(os.environ.get("SYNC_INTERVAL_MINUTES", "60"))
    sync_task = asyncio.create_task(periodic_sync(sync_interval))
    print(f"Periodic sync scheduled every {sync_interval} minutes")

@app.on_event("shutdown")
async def shutdown_event():
    # Cleanup resources
    global calendar_mcp_server, sync_storage, sync_task
    
    # Stop MCP server
    if calendar_mcp_server:
        await calendar_mcp_server.close()
        print("Calendar MCP server stopped")
    
    # Cancel periodic sync task
    if sync_task:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            print("Periodic sync task cancelled")
    
    # Close sync storage
    if sync_storage:
        await sync_storage.close()
        print("Sync storage closed")

# Route for health check
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Direct execution for development
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)