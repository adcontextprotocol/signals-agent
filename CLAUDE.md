# Audience Agent - Implementation Notes

This document provides implementation details and instructions for working with the Audience Activation Protocol agent.

## A2A Protocol Implementation

This agent implements both MCP and A2A protocols in a unified server (`unified_server.py`).

### Key Implementation Details

#### 1. Dual Protocol Support
- Single FastAPI server handles both MCP (`/mcp`) and A2A (`/a2a/task`, `/agent-card`) endpoints
- Shared business logic in `main.py` used by both protocols
- Protocol-specific request/response transformations in `unified_server.py`

#### 2. A2A Agent Card
- Available at both `/agent-card` and `/.well-known/agent.json` (A2A spec requirement)
- Dynamically detects HTTPS via `X-Forwarded-Proto` header for correct URLs
- Includes required fields: `name`, `description`, `version`, `capabilities`, `skills`, `provider`
- Skills array duplicates capabilities for A2A Inspector compatibility

#### 3. JSON-RPC Message Handling
- Root endpoint (`POST /`) detects JSON-RPC `message/send` requests
- Extracts query from `message.parts` array
- Returns `Message` object (not `Task`) for message/send requests
- Properly formats with `message_id` (underscore, not camelCase)

#### 4. Task Response Format
- All task responses return `Task` objects with nested `TaskStatus` and `Message`
- Status states: `completed`, `working`, `failed`
- Message includes both `TextPart` (human-readable) and `DataPart` (structured JSON)
- Error responses use numeric JSON-RPC codes (-32602, -32603)

#### 5. Contextual Query Handling
- Detects follow-up questions about signals or custom segments
- Keywords: "tell me about the signal", "custom segments", etc.
- Returns contextual explanations instead of new searches
- Maintains `contextId` through conversation flow

#### 6. Common Pitfalls Avoided
- **Database duplicates**: Check if data exists before inserting on initialization
- **Deployment counting**: Count unique platforms, not individual deployments
- **Message format**: Use "available on N platforms" not "N ready for activation"
- **Field naming**: Use `message_id` not `messageId`, `Role.agent` not `Role.assistant`
- **CORS headers**: Essential for web-based tools like A2A Inspector

## Overview

The Audience Agent implements the Audience Activation Protocol with support for:
- Natural language audience discovery using Gemini AI
- Multiple decisioning platform integrations (currently Index Exchange)
- Principal-based access control for multi-tenant support
- Transparent data availability indicators

## Running the Agent

### Prerequisites
```bash
# Install dependencies
uv pip install fastmcp rich google-generativeai requests
```

### Configuration
1. Copy the sample config:
```bash
cp config.json.sample config.json
```

2. Edit `config.json` to add:
   - Your Gemini API key
   - Platform credentials (e.g., Index Exchange username/password)
   - Principal-to-account mappings

### Starting the Server
```bash
uv run python main.py
```

### Using the Client

#### Interactive Mode
```bash
uv run python client.py
```

#### Quick Search Mode
```bash
# Basic search
uv run python client.py --prompt "luxury car buyers"

# With principal ID (for account-specific segments)
uv run python client.py --prompt "luxury" --principal acme_corp

# Limit results
uv run python client.py --prompt "automotive" --limit 10
```

## LiveRamp Integration

### Overview
The LiveRamp adapter provides access to the full LiveRamp Data Marketplace catalog with over 200,000 segments. It uses an offline sync approach for optimal performance.

### Key Features
- **Full Catalog Sync**: Downloads entire LiveRamp catalog to local SQLite database
- **Offline Search**: Uses SQLite FTS5 for fast, intelligent full-text search
- **Scheduled Updates**: Fly.io scheduled machines for daily catalog updates
- **Batch Processing**: Memory-efficient processing of large datasets
- **Secure Credentials**: Environment variable-based credential management

### Configuration
```json
"liveramp": {
    "enabled": true,
    "base_url": "https://api.liveramp.com",
    "client_id": "your-client-id",
    "account_id": "your-service-account",
    "secret_key": "your-secret-key",
    "token_uri": "your-token-uri",
    "owner_org": "your-owner-org"
}
```

### Sync Process
1. Run manual sync: `uv run python sync_liveramp_catalog.py --full`
2. Scheduled sync: Configured in Fly.io to run daily
3. Database location: `/data/signals_agent.db` (Fly.io) or `signals_agent.db` (local)

### Important Notes
- The adapter ALWAYS uses the local cache - no automatic API calls
- Sync is handled separately by the scheduled job
- Full catalog is available without pagination limits
- FTS5 queries are sanitized to prevent injection

## Platform Adapter Architecture

### Overview
Platform adapters wrap decisioning platform APIs to provide unified access to audience segments.

### Key Components

1. **Base Adapter** (`adapters/base.py`)
   - Abstract base class defining the adapter interface
   - Built-in caching with configurable TTL (default 60 seconds)
   - Principal validation for security

2. **Index Exchange Adapter** (`adapters/index_exchange.py`)
   - Full authentication with token refresh
   - Segment normalization to internal format
   - Transparent data availability:
     - Returns `None` for coverage when not available
     - Returns `None` for CPM when no fees configured
     - Sets `has_coverage_data` and `has_pricing_data` flags

3. **Adapter Manager** (`adapters/manager.py`)
   - Manages multiple platform adapters
   - Automatically determines adapter class from platform name
   - Maps principals to platform accounts

### Data Transparency

The system explicitly indicates when data is not available:
- Coverage displays as "Unknown" when no data exists
- CPM displays as "Unknown" when no pricing data exists
- No smart estimation or guessing of values

### Adding New Platform Adapters

1. Create a new adapter class inheriting from `PlatformAdapter`
2. Implement required methods:
   - `authenticate()` - Handle platform authentication
   - `get_segments()` - Fetch and normalize segments
   - `activate_segment()` - Activate a segment on the platform
   - `check_segment_status()` - Check activation status

3. Update the adapter manager to recognize the new platform:
```python
def _get_adapter_info(self, platform_name: str, platform_config: Dict[str, Any]) -> tuple[str, str]:
    if platform_name == 'your-platform':
        return 'YourPlatformAdapter', 'adapters.your_platform'
```

## Configuration Details

### Platform Configuration
```json
"platforms": {
    "index-exchange": {
        "enabled": true,
        "test_mode": false,
        "base_url": "https://app.indexexchange.com/api",
        "username": "your-username",
        "password": "your-password",
        "cache_duration_seconds": 60,
        "principal_accounts": {
            "principal_id": "account_id"
        }
    }
}
```

### Principal Mapping
- Maps principal IDs to platform account IDs
- Enables multi-tenant access control
- Principals only see segments from their mapped accounts

## Testing

### Test with Live Index Exchange Data
1. Configure real IX credentials in `config.json`
2. Map principals to account IDs
3. Run searches with principal ID to see account-specific segments

### Example Test Commands
```bash
# Search public segments
uv run python client.py --prompt "automotive enthusiasts"

# Search with principal (includes platform segments)
uv run python client.py --prompt "luxury" --principal acme_corp

# Interactive discovery
uv run python client.py
> discover
> luxury travel
> 1  # Choose specific platforms
> index-exchange
```

## Common Issues

### "Unknown" Values
- This is by design - the system shows "Unknown" when data is not available
- Index Exchange segments without fees show "Unknown" CPM
- Segments without coverage data show "Unknown" coverage

### Authentication Errors
- Check platform credentials in config.json
- Ensure the account has API access enabled
- Verify principal-to-account mappings

### No Platform Segments Found
- Check if platform is enabled in config
- Verify principal has mapped account
- Check platform API is accessible

## Development Notes

### Key Design Decisions
1. **Transparent Data**: Never estimate or guess values - show "Unknown"
2. **Caching**: 60-second cache to reduce API load
3. **Security**: Principal-based access control for multi-tenancy
4. **Extensibility**: Easy to add new platform adapters

### Future Enhancements
- Add more platform adapters (Trade Desk, DV360, etc.)
- Implement segment activation and status checking
- Add webhook support for activation notifications
- Support for custom segment creation on platforms