# Centralized Calendar Sync System

A master-agent calendar synchronization system that collects calendars from multiple isolated networks and consolidates them into a single destination calendar. Perfect for organizations with calendars scattered across different networks, VPNs, and Exchange servers.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    CENTRALIZED OFFICE SERVER                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              MASTER CALENDAR SERVICE                        │ │
│  │  • Collects from all remote agents                         │ │
│  │  • Consolidates into unified calendar                      │ │
│  │  • Runs on Docker (port 8008)                             │ │
│  │  • Connects to Mailcow/Exchange destination               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│              ↕ HTTP API Connections                              │
└─────────────────────────────────────────────────────────────────┘
                                   ↕
    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │   REMOTE AGENT   │  │   REMOTE AGENT   │  │   REMOTE AGENT   │
    │  ┌──────────────┐ │  │  ┌──────────────┐ │  │  ┌──────────────┐ │
    │  │Windows PC #1 │ │  │  │Windows PC #2 │ │  │  │  VPN Network │ │
    │  │+ Outlook     │ │  │  │+ Exchange    │ │  │  │+ Exchange    │ │
    │  │+ Local Cal   │ │  │  │+ Team Cals   │ │  │  │+ Remote Cals │ │
    │  └──────────────┘ │  │  └──────────────┘ │  │  └──────────────┘ │
    └──────────────────┘  └──────────────────┘  └──────────────────┘
```

## What Gets Deployed Where

### 🏢 MASTER SERVER (Your Centralized Office Server)
**Purpose**: Central hub that receives and consolidates all calendar data
**Deployment**: Single Docker container on your office server

**What it does**:
- Receives calendar events from remote agents
- Consolidates all calendars into one unified destination
- Provides management interface and APIs
- Connects to your Mailcow/Exchange server as the destination

**What you need**:
- Docker and docker-compose
- Network access to your Mailcow server
- Port 8008 accessible to remote agents

### 📱 REMOTE AGENTS (Individual Computers/Networks)
**Purpose**: Lightweight clients that extract calendar data from local sources
**Deployment**: 3 simple files on each Windows computer with calendars

**What they do**:
- Connect to local Outlook, Exchange, or other calendar sources
- Extract calendar events and send to master server
- Run continuously in background
- No configuration of destination calendars needed

**What you need**:
- Python installed on Windows machine
- Network access to master server
- Outlook or Exchange access

## Quick Start Guide

### Step 1: Deploy Master Server

1. **On your centralized office server**, clone this repository:
```bash
git clone <this-repo>
cd calendar_microservice
```

2. **Create environment configuration**:
```bash
cp .env.example .env
```

3. **Edit `.env` file** with your Mailcow server details:
```bash
# Master server settings
DEBUG=false
CORS_ORIGINS=*

# Mailcow Exchange destination (ON SEPARATE SERVER - where ALL calendars sync TO)
EXCHANGE_SERVER_URL=https://192.168.1.50/ews/exchange.asmx
EXCHANGE_USERNAME=unified-calendar@yourdomain.com
EXCHANGE_PASSWORD=your-mailcow-password

# Redis for caching (runs locally in Docker)
REDIS_HOST=redis
REDIS_PORT=6379

# API settings (master server listens on this port)
API_PORT=8008
```

**Example Network Setup**:
- **Master Server**: `192.168.1.100:8008` (this Docker container)
- **Mailcow Server**: `192.168.1.50:443` (separate server)
- **Remote Agents**: Point to `192.168.1.100:8008`

4. **Deploy with Docker**:
```bash
docker-compose up -d
```

5. **Verify master server is running**:
```bash
curl http://your-office-server-ip:8008/health
```

The master server is now ready to receive calendar data from remote agents.

### Step 2: Deploy Remote Agents

For each computer/network with calendars you want to sync:

1. **On the Windows machine**, create a new folder (e.g., `C:\CalendarAgent\`)

2. **Copy these 3 files** to the folder:
   - `src/sync/remote_agent.py`
   - `src/sync/outlook_config.json` 
   - `src/sync/run_agent.bat`

3. **Install Python** if not already installed:
   - Download from [python.org](https://python.org/downloads/)
   - ✅ Check "Add Python to PATH" during installation

4. **Edit `outlook_config.json`**:
```json
{
  "agent_id": "unique-agent-name",
  "agent_name": "Office Computer 1",
  "environment": "Main Office",
  "central_api_url": "http://your-office-server-ip:8008",
  "sync_interval_minutes": 30,
  "calendar_sources": [
    {
      "type": "outlook",
      "name": "John's Work Calendar",
      "calendar_name": "Calendar"
    }
  ]
}
```

5. **Start the agent**:
   - Double-click `run_agent.bat`
   - Click "Allow" when Outlook asks for permission
   - Agent will start syncing automatically

6. **Optional - Auto-start on boot**:
   - Right-click `run_agent.bat` → Create shortcut
   - Press Win+R, type `shell:startup`, press Enter
   - Move shortcut to this folder

### Step 3: Verify Synchronization

1. **Check master server logs**:
```bash
docker-compose logs -f calendar-service
```

2. **Check agent logs** on Windows machines:
   - Look for `calendar_agent.log` in the agent folder

3. **Verify calendars in Mailcow**:
   - Log into your Mailcow webmail
   - Check the unified calendar account for synchronized events

## Configuration Details

### Master Server Environment Variables

```bash
# Required - Mailcow/Exchange destination (ON SEPARATE SERVER)
EXCHANGE_SERVER_URL=https://192.168.1.50/ews/exchange.asmx
EXCHANGE_USERNAME=calendar@yourdomain.com
EXCHANGE_PASSWORD=strong-password

# Optional - Redis caching (runs in same Docker network as master)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=

# Optional - API settings (master server configuration)
DEBUG=false
CORS_ORIGINS=*
API_PORT=8008
SYNC_INTERVAL_MINUTES=60
```

**Multi-Server Network Configuration**:
```
┌─────────────────────┐    ┌─────────────────────┐
│   MASTER SERVER     │    │   MAILCOW SERVER    │
│  192.168.1.100      │◄──►│  192.168.1.50       │
│  ┌─────────────────┐│    │  ┌─────────────────┐ │
│  │Calendar Service ││    │  │Mailcow Exchange │ │
│  │Port 8008        ││    │  │Port 443/80      │ │
│  │+ Redis          ││    │  │EWS Endpoint     │ │
│  └─────────────────┘│    │  └─────────────────┘ │
└─────────────────────┘    └─────────────────────┘
        ▲
        │ Remote Agents connect here
        │ (192.168.1.100:8008)
```

### Remote Agent Configuration

Each agent needs a unique `outlook_config.json`:

```json
{
  "agent_id": "office-pc-1",
  "agent_name": "John's Office Computer",
  "environment": "Main Office Network",
  "central_api_url": "http://192.168.1.100:8008",
  "sync_interval_minutes": 30,
  "calendar_sources": [
    {
      "type": "outlook",
      "name": "Primary Calendar",
      "calendar_name": "Calendar"
    },
    {
      "type": "outlook", 
      "name": "Team Calendar",
      "calendar_name": "Shared Team Calendar"
    }
  ]
}
```

**Configuration Options**:
- `agent_id`: Unique identifier for this agent
- `central_api_url`: URL of your master server
- `sync_interval_minutes`: How often to sync (15-60 minutes recommended)
- `calendar_sources`: List of local calendars to sync

### Multiple Calendar Sources per Agent

To sync multiple calendars from one computer:

```json
"calendar_sources": [
  {
    "type": "outlook",
    "name": "Personal Calendar",
    "calendar_name": "Calendar"
  },
  {
    "type": "outlook",
    "name": "Work Projects",
    "calendar_name": "Project Calendar"
  },
  {
    "type": "exchange",
    "name": "Exchange Calendar",
    "exchange_url": "https://exchange.company.com/ews/exchange.asmx",
    "username": "user@company.com",
    "password": "password"
  }
]
```

## Network Requirements

### Master Server (192.168.1.100)
- **Inbound**: Port 8008 (from remote agents)
- **Outbound**: Port 443/80 (to Mailcow server at 192.168.1.50)
- **Internal**: Port 6379 (Redis within Docker network)

### Mailcow Server (192.168.1.50)
- **Inbound**: Port 443/80 (from master server)
- **EWS Endpoint**: `/ews/exchange.asmx` must be accessible

### Remote Agents  
- **Outbound**: HTTP access to master server on port 8008 (192.168.1.100:8008)
- **Local**: Access to Outlook/Exchange on local network

### Firewall Rules
```bash
# On master server (192.168.1.100)
sudo ufw allow 8008/tcp  # For remote agents
sudo ufw allow out 443/tcp  # To Mailcow server

# On Mailcow server (192.168.1.50) 
sudo ufw allow from 192.168.1.100 to any port 443  # From master server

# On remote agent networks
# Ensure outbound access to 192.168.1.100:8008
```

## Troubleshooting

### Master Server Issues

**Service won't start**:
```bash
# Check logs
docker-compose logs calendar-service

# Check if port is in use
netstat -tlnp | grep 8008

# Restart services
docker-compose down && docker-compose up -d
```

**Can't connect to Mailcow**:
```bash
# Test EWS endpoint
curl -k https://your-mailcow-server/ews/exchange.asmx

# Check credentials
# Verify Exchange authentication in Mailcow admin panel
```

### Remote Agent Issues

**Agent won't connect to master**:
- Check `central_api_url` in config
- Verify network connectivity: `telnet master-server-ip 8008`
- Check firewall rules

**Outlook permission denied**:
- Run as administrator
- Check Outlook security settings
- Restart Outlook and try again

**Calendar not found**:
- Check exact calendar name in Outlook
- Case-sensitive matching required
- Use calendar display name, not folder name

**Python not found**:
- Reinstall Python with "Add to PATH" checked
- Restart command prompt after installation

### Common Issues

**Events not appearing in destination**:
- Check master server logs for sync errors
- Verify Exchange credentials and permissions
- Check date ranges (default: past 30 days, future 90 days)

**Duplicate events**:
- Each agent should have unique `agent_id`
- Check for multiple agents syncing same calendar

**Performance issues**:
- Increase `sync_interval_minutes` for large calendars
- Monitor Redis memory usage
- Check network latency between components

## Security Considerations

### Master Server
- Run Docker containers as non-root user
- Use strong Exchange/Mailcow passwords
- Enable TLS for Mailcow connections
- Regular security updates

### Remote Agents
- Store configuration files in secure locations
- Use service accounts for Exchange connections
- Limit network access to master server only
- Regular Python security updates

### Network
- Use VPN for remote agent connections if possible
- Enable HTTPS for master server (use reverse proxy)
- Monitor API access logs
- Implement rate limiting if needed

## Monitoring and Maintenance

### Health Checks
```bash
# Master server health
curl http://master-server:8008/health

# View sync status
curl http://master-server:8008/api/sync/status

# Agent connectivity
grep "Connected to central API" /path/to/agent/calendar_agent.log
```

### Log Locations
- **Master server**: `docker-compose logs calendar-service`
- **Remote agents**: `calendar_agent.log` in agent folder
- **Redis**: `docker-compose logs redis`

### Backup and Recovery
```bash
# Backup Redis data
docker-compose exec redis redis-cli BGSAVE

# Backup configuration
tar -czf calendar-backup.tar.gz .env docker-compose.yml

# Restore
docker-compose down
# Restore files
docker-compose up -d
```

## Advanced Configuration

### Custom Calendar Sources

Extend agents to support additional calendar types:

```python
# In remote_agent.py
class CustomCalendarSource:
    def get_events(self, start_date, end_date):
        # Your custom implementation
        return events
```

### Load Balancing Multiple Masters

For high availability, deploy multiple master servers:

```yaml
# docker-compose.yml
version: '3.8'
services:
  calendar-service-1:
    # ... configuration
  calendar-service-2:
    # ... configuration
  nginx:
    image: nginx
    # Load balancer configuration
```

### Integration with Next.js/React

Use the provided client libraries:

```typescript
// Next.js integration
import { CalendarClient } from './CalendarClient';

const client = new CalendarClient('http://master-server:8008');
const events = await client.getEvents(startDate, endDate);
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request

## License

MIT License - see LICENSE file for details