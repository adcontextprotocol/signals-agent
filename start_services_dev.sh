#!/bin/bash
# Start both MCP and Search UI services

echo "Starting services..."

# Start MCP server on port 8000 in background
echo "Starting MCP server on port 8000..."
uv run fastmcp run main.py --transport http --port 8000 --host 0.0.0.0 &
MCP_PID=$!

# Wait for MCP to start
sleep 3

# Start Search UI server on port 8001 in background  
echo "Starting Search UI server on port 8001..."
PORT=8001 uv run python app_server.py &
UI_PID=$!

echo "✅ Services started:"
echo "   - MCP server: http://0.0.0.0:8000 (PID: $MCP_PID)"
echo "   - Search UI: http://0.0.0.0:8001 (PID: $UI_PID)"

# Function to handle shutdown
shutdown() {
    echo "Shutting down services..."
    kill $MCP_PID $UI_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap shutdown SIGINT SIGTERM

# Wait for both processes
wait $MCP_PID $UI_PID