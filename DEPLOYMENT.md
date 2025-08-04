# Deployment Guide

This guide explains how to deploy the Audience Agent reference implementation for live demonstrations.

## Option 1: GitHub Codespaces (Recommended for Quick Demo)

The easiest way to provide a live demo is through GitHub Codespaces:

1. **Setup**: The repository includes a `.devcontainer` configuration
2. **Access**: Users can click "Code" → "Codespaces" → "Create codespace"
3. **Demo**: The codespace will automatically:
   - Install dependencies with `uv`
   - Initialize the database with sample data
   - Forward port 8000 for the web demo

### Usage in Codespaces:
```bash
# Set your Gemini API key
cp config.json.sample config.json
# Edit config.json to add your API key

# Start the web demo
uv run python demo_web.py

# Or use the MCP client
uv run python client.py --prompt "luxury automotive targeting"
```

## Option 2: Docker Deployment

For more permanent hosting, use Docker:

### Build and run locally:
```bash
docker build -t audience-agent .
docker run -p 8000:8000 \
  -e GEMINI_API_KEY=your-key-here \
  audience-agent uv run python demo_web.py
```

### Deploy to cloud platforms:

#### Railway.app
1. Connect your GitHub repository
2. Set environment variable: `GEMINI_API_KEY`
3. Railway will automatically deploy using the Dockerfile

#### Render.com
1. Connect repository
2. Choose "Web Service"
3. Set build command: `pip install uv && uv sync`
4. Set start command: `uv run python demo_web.py`
5. Add environment variable: `GEMINI_API_KEY`

#### Fly.io
```bash
flyctl launch
flyctl secrets set GEMINI_API_KEY=your-key-here
flyctl deploy
```

## Option 3: Local Development

For development and testing:

```bash
# Install dependencies
pip install uv
uv sync

# Configure API key
cp config.json.sample config.json
# Edit config.json with your Gemini API key

# Initialize database
uv run python database.py

# Start web demo
uv run python demo_web.py

# Or start MCP server
uv run python main.py

# Or use interactive client
uv run python client.py
```

## Demo Features

The live demo provides:

1. **Web Interface** (`demo_web.py`):
   - HTML form for audience queries
   - Real-time AI-powered search results
   - Custom segment proposals
   - One-click activation simulation

2. **MCP Client** (`client.py`):
   - Command-line interface
   - Interactive mode for testing all protocol tasks
   - Batch query mode with `--prompt`

3. **Protocol Server** (`main.py`):
   - Full MCP server implementation
   - Two protocol tasks: `get_signals`, `activate_signal` (includes status monitoring)
   - AI-powered ranking and custom segment generation

## Data

The demo includes:
- 56 real Peer39 audience segments from Index Exchange
- 6 major SSP platform deployments (Index Exchange, The Trade Desk, OpenX, etc.)
- Realistic CPM pricing based on segment specificity
- AI-generated match explanations and custom segment proposals

## Requirements

- Python 3.10+
- Google Gemini API key (free at [ai.google.dev](https://ai.google.dev))
- SQLite database (auto-created)
- Internet connection for AI features

## Security Notes

- The `config.json` file is gitignored to protect API keys
- Use environment variables in production deployments
- The demo database contains no real user data
- All activations are simulated - no real ad serving occurs