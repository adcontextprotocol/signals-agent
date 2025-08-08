#!/usr/bin/env python3
"""Dead simple MCP server using FastMCP's HTTP transport."""

from fastmcp import FastMCP
from fastmcp.server import Server
import uvicorn
import main
from database import init_db
import logging

logging.basicConfig(level=logging.INFO)

# Initialize database
init_db()

# Create MCP server
mcp = FastMCP("Signals Agent", version="1.0.0")

@mcp.tool()
async def discover(query: str, max_results: int = 10) -> dict:
    """
    Discover audience segments matching your query.
    
    Args:
        query: Natural language description of target audience
        max_results: Maximum results to return
    """
    response = main.get_signals.fn(
        signal_spec=query,
        deliver_to={"platforms": "all", "countries": ["US"]},
        max_results=max_results
    )
    
    return {
        "query": query,
        "signals": [
            {
                "id": s.signal_id,
                "name": s.name,
                "description": s.description,
                "coverage": f"{s.coverage_percentage}%",
                "cpm": f"${s.pricing.cpm}" if s.pricing and s.pricing.cpm else "Unknown",
                "provider": s.data_provider
            }
            for s in response.signals[:max_results]
        ],
        "proposals": [
            {
                "name": p.name,
                "rationale": p.rationale
            }
            for p in (response.custom_segment_proposals or [])[:3]
        ],
        "total": len(response.signals)
    }

if __name__ == "__main__":
    # FastMCP automatically handles HTTP/SSE transport
    server = Server(mcp)
    
    # Run with built-in HTTP support
    port = 8000
    logging.info(f"Starting MCP server on http://0.0.0.0:{port}/mcp")
    logging.info("FastMCP handles all transport complexity automatically")
    
    # This automatically supports both HTTP and SSE transports
    uvicorn.run(
        server.get_asgi_app(),
        host="0.0.0.0",
        port=port,
        log_level="info"
    )