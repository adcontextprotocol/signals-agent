# Signals Agent Reference Implementation

This project is a Python-based reference implementation of a Signals Activation Protocol agent. It demonstrates how to build a signals platform that integrates with AI assistants through the Model Context Protocol (MCP), supporting various signal types including:
- **Audience signals**: Demographic and behavioral targeting
- **Contextual signals**: Content classification and context
- **Geographical signals**: Location-based targeting
- **Temporal signals**: Time-based targeting
- **Environmental signals**: Weather, events, and external conditions
- **Bidding signals**: Custom bidding data and strategies

## 🚀 Try the Live Demo

**Quick Start**: Click the green **"Code"** button above → **"Codespaces"** → **"Create codespace on main"**

The demo will automatically set up with real data and AI-powered signal discovery. See [DEMO_GUIDE.md](DEMO_GUIDE.md) for complete instructions.

## Overview

The Signals Agent provides:

- **AI-Powered Discovery**: Uses Google Gemini to intelligently rank signals (audiences, bidding data, contextual signals) based on natural language queries
- **Smart Match Explanations**: Each result includes AI-generated explanations of why the segment matches your targeting goals
- **Custom Segment Proposals**: AI suggests new custom segments that could be created for better targeting
- **Multi-Platform Support**: Discover signals across multiple SSPs (Index Exchange, The Trade Desk, OpenX, etc.)
- **Live Platform Integration**: Real-time API integration with decisioning platforms (Index Exchange supported)
- **Intelligent Caching**: 60-second API response caching for optimal performance
- **Real-Time Activation**: On-demand signal deployment to decisioning platforms
- **Transparent Pricing**: CPM and revenue share models with realistic market pricing
- **Data Transparency**: Shows "Unknown" for coverage/pricing when data is not available (no guessing)

## Agent Types Supported

This reference implementation supports all three signal agent types:

### 1. Private Signal Agent
- Owned by the principal with exclusive access
- No signal costs (workflow orchestration only)
- Only visible to the owning principal

### 2. Marketplace Signal Agent - Public Catalog
- Available to any orchestrator without principal registration
- Standard marketplace pricing
- Platform-wide segments only

### 3. Marketplace Signal Agent - Personalized Catalog
- Requires principal account with the signal agent
- Account-specific segments plus platform-wide segments
- Mixed pricing: negotiated rates and standard rates

## Getting Started

### Option 1: GitHub Codespaces (Recommended)

The fastest way to try the demo:

1. Click **"Code"** → **"Codespaces"** → **"Create codespace on main"**
2. Wait for automatic setup (dependencies install automatically)
3. Get a free Gemini API key at [ai.google.dev](https://ai.google.dev)
4. Configure your API key:
   ```bash
   cp config.json.sample config.json
   # Edit config.json to add your API key
   ```
5. Initialize the database:
   ```bash
   uv run python database.py
   ```
6. Try the interactive demo:
   ```bash
   uv run python client.py
   ```

### Option 2: Local Installation

For local development:

```bash
# Install dependencies
pip install uv
uv sync

# Configure API key
cp config.json.sample config.json
# Edit config.json with your Gemini API key from ai.google.dev

# Initialize database
uv run python database.py

# Start MCP server
uv run python main.py
```

## Protocol Implementation

This agent implements the following tasks from the Signals Activation Protocol:

- `get_signals`: Discover signals based on marketing specifications
- `activate_signal`: Activate signals for specific platforms/accounts (includes status monitoring)

### Principal-Based Access Control

The implementation supports differentiated access levels and pricing based on principal identity:

**Access Levels:**
- **Public**: Standard catalog access with base pricing
- **Personalized**: Access to additional segments with account-specific pricing  
- **Private**: Full catalog access including exclusive segments

**Example principals configured:**
- `acme_corp` (personalized access) - Custom pricing for luxury segments
- `premium_partner` (personalized access) - Standard personalized pricing
- `enterprise_client` (private access) - Full catalog access

**Usage:**
```bash
# Public access (default)
uv run python client.py --prompt "luxury automotive"

# Principal with custom pricing
uv run python client.py --prompt "luxury automotive" --principal acme_corp
```

The same segment may show different pricing:
- Public: $2.50 CPM for luxury segments
- ACME Corp: $6.50 CPM (custom negotiated rate)

### Platform Adapter Integration

The system supports real-time integration with decisioning platform APIs:

**Supported Platforms:**
- **Index Exchange**: Live API integration with authentication and caching
- **The Trade Desk**: Adapter framework ready (implementation pending)

**Configuration:**
```json
{
  "platforms": {
    "index-exchange": {
      "enabled": true,
      "test_mode": false,
      "username": "your-ix-username", 
      "password": "your-ix-password",
      "principal_accounts": {
        "acme_corp": "1489997"
      }
    }
  }
}
```

Set `test_mode: true` to use simulated API responses for development/testing.

**Security:**
- Principal-to-account ID mapping prevents unauthorized access
- API credentials stored securely in config
- 60-second response caching reduces API load

**Data Transparency:**
- When platform APIs don't provide coverage data, shows "Unknown" instead of estimates
- When segments have no fees configured, shows "Unknown" for pricing
- Clear differentiation between known and unknown data points

## 🚀 Try the Live Demo

**Quick Start**: Click the green **"Code"** button above → **"Codespaces"** → **"Create codespace on main"**

Once in Codespaces (or locally), the demo uses the interactive MCP client:

```bash
# Interactive mode - full demo experience
uv run python client.py

# Quick search mode  
uv run python client.py --prompt "BMW luxury automotive targeting"

# Limit results (default is 5)
uv run python client.py --prompt "BMW luxury automotive targeting" --limit 10

# Test different principal access levels and pricing
uv run python client.py --prompt "luxury" --principal acme_corp
```

## Testing

Run the test suite:

```bash
uv run python -m unittest test_main.py
```

## Full Lifecycle Demo

The system now supports the complete signal lifecycle:

1. **Discovery**: Search for signals with natural language
2. **AI Proposals**: Get custom segment suggestions with unique IDs
3. **Activation**: Activate both existing and custom signals
4. **Status Tracking**: Check deployment progress

Try activating a custom segment:
```bash
uv run python client.py
# Use 'discover' to get custom segment IDs
# Use 'activate' with the custom segment ID (supports --principal)
# Use 'status' to check deployment progress (supports --principal)
```

The interactive mode now supports principal identity for all operations:
- **Discovery**: Different catalogs and pricing based on principal
- **Activation**: Principal-based access control prevents unauthorized activations
- **Status Checking**: Only shows status for segments the principal can access

## Architecture

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   AI Assistant      │    │   Signals Agent      │    │  Decisioning        │
│   (Orchestrator)    │───▶│   (This Project)     │───▶│  Platform (DSP)     │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
        │                            │                            │
        │                            │                            │
        └────────────── Direct Integration Model ──────────────────┘
```

The agent operates within the broader Ad Tech Ecosystem Architecture, enabling direct integration with decisioning platforms while eliminating intermediary reporting complexity.

## License

This project is licensed under the MIT License - see the LICENSE file for details.