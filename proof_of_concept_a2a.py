#!/usr/bin/env python3
"""
Proof of concept: Using python-a2a to replace our entire server implementation.
This single file replaces:
- unified_server.py
- a2a_facade.py  
- mcp_facade.py
- Parts of main.py
"""

from python_a2a import A2AServer, skill, agent, run_server
from python_a2a.mcp import FastMCP, FastMCPAgent, text_response
import os
import json
from typing import Dict, Any, List, Optional

# Import our existing business logic (unchanged!)
import business_logic
import database

# Create a unified agent that supports both A2A and MCP protocols
@agent(
    name="Signals Activation Agent",
    description="AI-powered audience discovery and activation agent",
    version="2.0.0",
    # These capabilities are properly implemented by the library
    capabilities={
        "streaming": True,  # Real SSE support!
        "pushNotifications": False,
        "stateTransitionHistory": False
    }
)
class SignalsAgent(A2AServer, FastMCPAgent):
    """
    Single agent class that handles both A2A and MCP protocols.
    Inherits from both A2AServer and FastMCPAgent.
    """
    
    def __init__(self):
        # Initialize both parent classes
        A2AServer.__init__(self)
        
        # Initialize MCP with our tools
        mcp_config = {}  # Can add external MCP servers here
        FastMCPAgent.__init__(self, mcp_servers=mcp_config)
        
        # Initialize database
        database.init()
    
    # ==================== A2A Skills ====================
    
    @skill(
        name="discover_audiences",
        description="Discover audience segments using natural language",
        tags=["discovery", "audiences", "search"]
    )
    async def discover_audiences(
        self, 
        query: str,
        context_id: Optional[str] = None,
        principal_id: Optional[str] = None,
        platform_filter: Optional[List[str]] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        A2A skill for audience discovery.
        This replaces our /a2a/task endpoint.
        """
        # Use our existing business logic!
        result = business_logic.process_discovery_query(
            query=query,
            context_id=context_id,
            principal_id=principal_id,
            platform_filter=platform_filter,
            limit=limit
        )
        
        # Return structured response (library handles A2A formatting)
        return {
            "signals": result.signals,
            "custom_segment_proposals": result.custom_segment_proposals,
            "message": result.message,
            "context_id": result.context_id,
            "metadata": {
                "total_found": len(result.signals),
                "platforms_available": result.available_platforms
            }
        }
    
    @skill(
        name="get_signal_details", 
        description="Get detailed information about a specific signal",
        tags=["signals", "details"]
    )
    async def get_signal_details(self, signal_id: str) -> Dict[str, Any]:
        """Get details for a specific signal."""
        # Reuse existing business logic
        signal = business_logic.get_signal_by_id(signal_id)
        if not signal:
            return {"error": f"Signal {signal_id} not found"}
        
        return {
            "signal": signal,
            "platforms": business_logic.get_signal_platforms(signal_id)
        }
    
    # ==================== MCP Tools ====================
    # These are exposed via MCP protocol and can be called by other MCP clients
    
    async def setup_mcp_tools(self):
        """Define MCP tools that other agents can use."""
        
        @self.mcp_server.tool(
            name="search_audiences",
            description="Search for audience segments"
        )
        def search_audiences(query: str, limit: int = 10):
            """MCP tool for searching audiences."""
            result = business_logic.search_signals(query, limit=limit)
            return text_response(json.dumps(result, indent=2))
        
        @self.mcp_server.tool(
            name="get_platforms",
            description="Get list of available platforms"
        )
        def get_platforms():
            """MCP tool for getting platforms."""
            platforms = business_logic.get_available_platforms()
            return text_response(json.dumps(platforms, indent=2))
        
        @self.mcp_server.tool(
            name="activate_segment",
            description="Activate a segment on a platform"
        )
        def activate_segment(
            segment_id: str,
            platform: str,
            principal_id: Optional[str] = None
        ):
            """MCP tool for segment activation."""
            result = business_logic.activate_segment(
                segment_id, platform, principal_id
            )
            return text_response(f"Activation result: {result}")
    
    # ==================== Message Handling ====================
    
    async def handle_message(self, message: str, context: Optional[Dict] = None) -> str:
        """
        Handle direct messages (supports streaming!).
        This is called for message/send in A2A protocol.
        """
        # Extract context_id if provided
        context_id = context.get("context_id") if context else None
        
        # Process using our business logic
        result = business_logic.process_discovery_query(
            query=message,
            context_id=context_id
        )
        
        # Return the message (library handles streaming if client wants it)
        return result.message
    
    # ==================== Lifecycle Methods ====================
    
    async def on_startup(self):
        """Called when the server starts."""
        print("🚀 Signals Agent starting up...")
        await self.setup_mcp_tools()
        
        # Load any configuration
        config_path = os.getenv("CONFIG_PATH", "config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                self.config = json.load(f)
        
        print("✅ Signals Agent ready!")
    
    async def on_shutdown(self):
        """Called when the server shuts down."""
        print("👋 Signals Agent shutting down...")


# ==================== Main Entry Point ====================

def main():
    """
    Main entry point - starts the unified server.
    """
    # Create our agent instance
    agent = SignalsAgent()
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    # Run the server (handles both A2A and MCP!)
    # The library automatically:
    # - Sets up all the endpoints (/agent-card, /a2a/*, MCP routes)
    # - Handles SSE streaming properly
    # - Implements proper JSON-RPC
    # - Manages protocol compliance
    print(f"🎯 Starting unified A2A/MCP server on {host}:{port}")
    run_server(
        agent,
        host=host,
        port=port,
        # Enable all features
        enable_cors=True,
        enable_streaming=True,  # Proper SSE support!
        enable_mcp=True,
        enable_a2a=True,
        # Optional: Enable the visual UI
        enable_ui=os.getenv("ENABLE_UI", "false").lower() == "true"
    )


if __name__ == "__main__":
    main()