#!/usr/bin/env python3
"""Ultra-simple MCP server with FastMCP HTTP transport."""

from fastmcp import FastMCP
import main
from database import init_db
import os

# Initialize database
init_db()

# Create MCP server
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

if __name__ == "__main__":
    # Use FastMCP's built-in HTTP transport - it handles everything!
    port = int(os.environ.get("PORT", 8000))
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port
    )