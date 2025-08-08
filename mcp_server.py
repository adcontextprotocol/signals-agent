#!/usr/bin/env python3
"""Simple MCP server using FastMCP that just works."""

from fastmcp import FastMCP
from fastmcp.server import Server
import logging
import main
from config_loader import load_config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP("Signals Agent")
server = Server(mcp)

@mcp.tool()
def discover_audiences(query: str, max_results: int = 10) -> dict:
    """
    Discover audience segments based on a natural language query.
    
    Args:
        query: Natural language description of the target audience
        max_results: Maximum number of results to return (default 10)
    
    Returns:
        Dictionary containing matched signals and custom proposals
    """
    logger.info(f"Discovering audiences for: {query}")
    
    try:
        # Use the main discovery function
        response = main.get_signals.fn(
            signal_spec=query,
            deliver_to={"platforms": "all", "countries": ["US"]},
            max_results=max_results
        )
        
        # Format response
        result = {
            "query": query,
            "signals": [
                {
                    "id": s.signal_id,
                    "name": s.name,
                    "description": s.description,
                    "coverage": s.coverage_percentage,
                    "cpm": s.pricing.cpm if s.pricing else None,
                    "provider": s.data_provider
                }
                for s in response.signals[:max_results]
            ],
            "custom_proposals": [
                {
                    "name": p.name,
                    "description": p.description,
                    "rationale": p.rationale
                }
                for p in (response.custom_segment_proposals or [])[:3]
            ],
            "total_found": len(response.signals)
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error discovering audiences: {e}")
        return {
            "error": str(e),
            "query": query
        }


@mcp.tool()
def get_signal_details(signal_id: str) -> dict:
    """
    Get detailed information about a specific signal.
    
    Args:
        signal_id: The ID of the signal to retrieve
    
    Returns:
        Detailed signal information
    """
    logger.info(f"Getting details for signal: {signal_id}")
    
    # This would query the database for specific signal details
    # For now, return a placeholder
    return {
        "signal_id": signal_id,
        "message": "Signal details would be retrieved from database"
    }


if __name__ == "__main__":
    # Run the server
    import uvicorn
    from fastmcp.server import create_app
    
    app = create_app(server)
    
    logger.info("Starting MCP server on http://localhost:8001/mcp")
    uvicorn.run(app, host="0.0.0.0", port=8001)