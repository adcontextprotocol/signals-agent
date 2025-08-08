#!/usr/bin/env python3
"""FastMCP server with CORS support via FastAPI wrapper."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from fastmcp.server.asgi import MCPAsgiAdapter
import uvicorn
import main
from database import init_db
import os

# Initialize database
init_db()

# Create FastMCP server
mcp = FastMCP("Signals Agent")

@mcp.tool()
def discover(query: str, max_results: int = 10) -> dict:
    """Discover audience segments matching your query."""
    response = main.get_signals.fn(
        signal_spec=query,
        deliver_to={"platforms": "all", "countries": ["US"]},
        max_results=max_results
    )
    
    return {
        "query": query,
        "signals": [
            {
                "name": s.name,
                "coverage": f"{s.coverage_percentage}%",
                "cpm": f"${s.pricing.cpm}" if s.pricing and s.pricing.cpm else "N/A"
            }
            for s in response.signals[:5]
        ],
        "found": len(response.signals)
    }

# Create FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Mount MCP at /mcp
mcp_adapter = MCPAsgiAdapter(mcp)
app.mount("/mcp", mcp_adapter)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)