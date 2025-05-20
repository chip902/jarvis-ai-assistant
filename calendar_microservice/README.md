# Calendar Integration Microservice

A microservice for integrating multiple calendar providers (Google Calendar, Microsoft Graph, and custom sources) for use in Node.js, Next.js, and React applications. This solution specializes in cross-environment synchronization to handle calendars locked behind isolated networks.

## Features

- Multi-provider calendar integration (Google, Microsoft, Exchange, and custom sources)
- Cross-environment synchronization for calendars behind isolated networks
- Remote calendar agents for VPN/Remote Desktop environments
- Multi-tenant support for enterprise applications
- Normalized calendar events across providers
- Efficient incremental sync with delta tokens
- Conflict resolution for bidirectional synchronization
- MCP (Multi-call Protocol) support for AI agents
- FastAPI-based RESTful API
- OAuth2 authentication flow management
- Next.js integration components

## Synchronization Architecture

This microservice addresses the challenge of synchronizing calendars across different environments, including those on isolated networks accessible only via VPN or Remote Desktop.

### Key Components

1. **Central Calendar Service**
   - Core FastAPI microservice running on your Next.js application server
   - Manages authentication with calendar providers
   - Provides unified API for calendar operations
   - Coordinates synchronization between all calendar sources
   - Stores and maintains synchronized events

2. **Remote Calendar Agents**
   - Lightweight Python clients that run in isolated environments
   - Connect to calendars only accessible within their network
   - Collect and normalize calendar data
   - Securely transmit events to the central service
   - Support various synchronization methods (API, file-based, email)
   - Work with different calendar systems (Exchange, Outlook, iCal, etc.)

3. **Synchronization Controller**
   - Manages the synchronization workflow
   - Handles conflict resolution between calendars
   - Maintains sync state with incremental updates
   - Schedules periodic synchronization jobs

4. **Unified Calendar API**
   - Normalizes events from different providers
   - Provides a consistent interface for your Next.js app
   - React components for easy integration
   - TypeScript client library

## Project Structure

```
calendar_microservice/
├── src/
│   ├── auth/               # Authentication services
│   │   ├── google_auth.py  # Google OAuth implementation
│   │   └── microsoft_auth.py  # Microsoft OAuth implementation
│   ├── services/           # Core calendar services
│   │   ├── calendar_event.py  # Normalized event model
│   │   ├── google_calendar.py  # Google Calendar service
│   │   ├── microsoft_calendar.py  # Microsoft Graph calendar service
│   │   └── unified_calendar.py  # Combined provider service
│   ├── sync/               # Synchronization components
│   │   ├── architecture.py  # Sync architecture definitions
│   │   ├── controller.py    # Sync orchestration logic
│   │   ├── storage.py       # Sync state persistence
│   │   └── remote_agent.py  # Agent for isolated environments
│   ├── api/                # FastAPI routes and handlers
│   │   ├── router.py       # API endpoint definitions
│   │   └── sync_router.py  # Sync API endpoints
│   ├── mcp/                # MCP server implementation
│   │   └── calendar_server.py  # Calendar MCP server
│   ├── utils/              # Utility modules
│   │   └── config.py       # Configuration settings
│   └── main.py             # Application entry point
├── nextjs-client/          # Next.js integration
│   ├── CalendarClient.ts   # TypeScript client for the API
│   └── CalendarSyncComponent.tsx  # React component
├── tests/                  # Unit and integration tests
├── .env.example            # Example environment variables
└── requirements.txt        # Python dependencies
```

## Installation

### Central Service

1. Clone the repository
2. Create a virtual environment (optional but recommended)
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```
3. Install dependencies
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in the required values
   ```
   cp .env.example .env
   ```
5. Start the service
   ```
   uvicorn src.main:app --reload
   ```

### Remote Agent

To run the agent in isolated environments:

1. Copy the `src/sync/remote_agent.py` file to the isolated environment
2. Install the required dependencies
   ```
   pip install aiohttp uuid
   ```
3. Run the agent
   ```
   python remote_agent.py --central-api http://your-central-service-url
   ```

### Next.js Integration

1. Copy the files from `nextjs-client/` to your Next.js project
2. Import and use the components:

```tsx
import { CalendarClient } from './CalendarClient';
import CalendarSyncComponent from './CalendarSyncComponent';

// In your component:
return (
  <CalendarSyncComponent 
    onEventsLoaded={(events) => console.log('Loaded events:', events)}
    onSyncComplete={(result) => console.log('Sync completed:', result)}
  />
);
```

## OAuth Setup

### Google Calendar API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Calendar API
4. Create OAuth 2.0 credentials (Web application type)
5. Add authorized redirect URIs (e.g., `http://localhost:8000/api/auth/google/callback`)
6. Copy the Client ID and Client Secret to your `.env` file

### Microsoft Graph API

1. Go to [Azure Portal](https://portal.azure.com/)
2. Register a new application in Azure Active Directory
3. Add the following Microsoft Graph API permissions:
   - Calendars.Read
   - Calendars.Read.Shared
   - User.Read
4. Create a client secret
5. Add redirect URIs (e.g., `http://localhost:8000/api/auth/microsoft/callback`)
6. Copy the Application (Client) ID, Client Secret, and Tenant ID to your `.env` file

## Synchronization Setup

### Source Calendars

For each calendar you want to sync, you'll need to:

1. Authenticate with the provider (Google, Microsoft, etc.)
2. Select which specific calendars to include
3. Configure sync settings (direction, frequency, etc.)

### Destination Calendar

Choose a single calendar to use as your unified destination:

1. Select an existing calendar from any provider
2. Configure conflict resolution settings
3. Optionally set up categories/color coding for events from different sources

### Isolation Strategy

For calendars in isolated environments:

1. Run the remote agent in the isolated environment
2. Configure the agent to connect to the central service
3. Add the agent as a sync source in the central service

## Usage

### Basic Calendar Operations

```typescript
// Initialize the client
const calendarClient = new CalendarClient('http://localhost:8000');

// Authenticate with Google
const googleAuthUrl = await calendarClient.getAuthUrl(CalendarProvider.GOOGLE);
// Redirect user to googleAuthUrl

// Exchange auth code for tokens
const credentials = await calendarClient.exchangeAuthCode(
  CalendarProvider.GOOGLE, 
  authCode
);

// List available calendars
const calendars = await calendarClient.listCalendars();

// Set which calendars to use
calendarClient.setCalendarSelections({
  'google': ['primary', 'calendar2@group.calendar.google.com'],
  'microsoft': ['AAMkADJhODkxNTY5LTZhNDYtNDg5OS04YjMyLTRlYmFhZWQ5MmJlYgBGAAAAAABl...']
});

// Get events
const { events, syncTokens } = await calendarClient.getEvents(
  new Date('2023-01-01'), 
  new Date('2023-12-31')
);
```

### Synchronization Configuration

```typescript
// Configure destination calendar
await calendarClient.configureDestination({
  id: 'unified-destination',
  name: 'My Unified Calendar',
  providerType: 'google',
  connectionInfo: {},
  credentials: googleCredentials,
  calendarId: 'primary',
  conflictResolution: 'latest_wins',
  categories: {}
});

// Add a sync source
await calendarClient.addSyncSource({
  id: 'work-exchange',
  name: 'Work Exchange Calendar',
  providerType: 'microsoft',
  connectionInfo: {},
  credentials: microsoftCredentials,
  syncDirection: 'read_only',
  syncFrequency: 'hourly',
  syncMethod: 'api',
  calendars: ['AAMkADJhODkxNTY5LTZhNDYtNDg5OS04YjMyLTRlYmFhZWQ5MmJlYgBGAAAAAABl...'],
  syncTokens: {},
  enabled: true
});

// Run synchronization
const result = await calendarClient.runSync();
```

## Remote Agent Usage

Run the agent with these options:

```bash
python remote_agent.py --help
# Options:
#   --config CONFIG         Path to configuration file
#   --central-api URL       URL of central calendar service API
#   --once                  Run sync once and exit
#   --interval MINUTES      Sync interval in minutes
```

For regular syncing, you can set up the agent as a scheduled task/cron job in the isolated environment.

## Advanced Configuration

### Environment Variables

```
# API settings
DEBUG=false
CORS_ORIGINS=http://localhost:3000,https://yourapp.com

# Google Calendar
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback

# Microsoft Graph
MS_CLIENT_ID=your-client-id
MS_CLIENT_SECRET=your-client-secret 
MS_REDIRECT_URI=http://localhost:8000/api/auth/microsoft/callback
MS_TENANT_ID=your-tenant-id

# Redis for caching (optional)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Sync settings
SYNC_INTERVAL_MINUTES=60
```

### Custom Calendar Sources

For custom calendar sources, you can extend the remote agent:

1. Create a new method in `remote_agent.py` for your custom source
2. Implement the required logic to fetch and normalize events
3. Register the custom source type in the agent

## Security Considerations

- Remote agents use token-based authentication with the central service
- All API communications use HTTPS
- OAuth tokens are stored securely and never exposed in URLs
- Agents run with minimal required permissions in their environments
- Credential isolation ensures agents only access what they need

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT License](LICENSE)