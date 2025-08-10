#!/usr/bin/env python3
"""
Simplified Signals Agent using python-a2a library.
This version uses synchronous methods for better compatibility.
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import python-a2a components
from python_a2a import A2AServer, skill, agent, run_server
from python_a2a.models import Task, TaskStatus, TaskState, Message
from typing import Any

# Import our existing business logic
import business_logic
import core_logic
import database

# Initialize database
database.init_db()

@agent(
    name="Signals Activation Agent",
    description="AI-powered audience discovery and activation agent",
    version="2.0.0",
    url="https://audience-agent.fly.dev"  # Required field!
)
class SignalsAgent(A2AServer):
    """
    Simplified agent using synchronous methods.
    """
    
    def __init__(self):
        super().__init__()
        # Load configuration
        config_path = os.getenv("CONFIG_PATH", "config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
                # Set Gemini API key if available
                if 'gemini_api_key' in config:
                    os.environ['GEMINI_API_KEY'] = config['gemini_api_key']
    
    @skill(
        name="discover_audiences",
        description="Discover audience segments using natural language"
    )
    def discover_audiences(
        self, 
        query: str,
        context_id: str = None,
        principal_id: str = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Main skill for audience discovery.
        """
        try:
            # Use our existing business logic
            result = business_logic.process_discovery_query(
                query=query,
                context_id=context_id,
                principal_id=principal_id,
                limit=limit
            )
            
            # Format response
            signals_data = []
            for s in result.signals[:limit]:
                signals_data.append({
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "category": s.category,
                    "coverage": s.coverage,
                    "cpm": s.cpm,
                    "source": s.source,
                    "platforms": getattr(s, 'available_platforms', [])
                })
            
            return {
                "success": True,
                "message": result.message,
                "context_id": result.context_id,
                "signals": signals_data,
                "custom_proposals": result.custom_segment_proposals or [],
                "total_found": len(result.signals)
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "signals": [],
                "custom_proposals": []
            }
    
    @skill(
        name="search_signals",
        description="Search for specific signals"
    )
    def search_signals(
        self,
        query: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Simple signal search.
        """
        try:
            # Get signals from database
            signals = core_logic.get_signals_core(
                search_term=query,
                limit=limit
            )
            
            return {
                "success": True,
                "signals": signals,
                "count": len(signals)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "signals": []
            }
    
    def get_agent_card(self) -> Dict[str, Any]:
        """
        Get the agent card with all required fields matching A2A specification.
        """
        base_url = "https://audience-agent.fly.dev" if os.getenv("FLY_APP_NAME") else f"http://localhost:{os.getenv('PORT', 8000)}"
        
        return {
            "name": "Signals Activation Agent",
            "description": "AI-powered audience discovery and activation agent",
            "version": "2.0.0",
            "url": f"{base_url}/a2a/jsonrpc",
            # Capabilities as a dictionary (AgentCapabilities type)
            "capabilities": {
                "input": ["text"],
                "output": ["text", "json"],
                "tools": ["discover_audiences", "search_signals"],
                "streaming": False
            },
            # Required input/output modes
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text", "json"],
            # Skills with required id and tags fields
            "skills": [
                {
                    "id": "discover_audiences",
                    "name": "Discover Audiences",
                    "description": "Discover audience segments using natural language queries",
                    "tags": ["audience", "discovery", "ai", "search"],
                    "examples": [
                        "Find luxury car buyers",
                        "Show me sports enthusiasts",
                        "Discover high-income travelers"
                    ]
                },
                {
                    "id": "search_signals",
                    "name": "Search Signals",
                    "description": "Search for specific audience signals in the database",
                    "tags": ["search", "signals", "database"],
                    "examples": [
                        "Search for automotive signals",
                        "Find sports-related audiences",
                        "Look for travel segments"
                    ]
                }
            ],
            # Provider with required url field
            "provider": {
                "name": "Signals Agent",
                "organization": "Signals Inc.",
                "url": "https://audience-agent.fly.dev"
            },
            "streaming": False,
            "mcp_support": True,
            "a2a_support": True
        }
    
    def handle_conversation(self, messages: List[Dict[str, Any]], context: Dict = None) -> str:
        """
        Handle conversation with context support.
        """
        # Get the latest message
        if not messages:
            return "No message provided."
        
        latest = messages[-1]
        query = latest.get('content', '') or latest.get('text', '') or str(latest)
        
        # Extract context/session ID
        context_id = None
        if context:
            context_id = context.get('sessionId') or context.get('session_id') or context.get('contextId') or context.get('context_id')
        
        # Process with our business logic
        result = business_logic.process_discovery_query(
            query=query,
            context_id=context_id,
            limit=10
        )
        
        # Store the context for next time
        if context and result.context_id:
            context['context_id'] = result.context_id
        
        return result.message
    
    def handle_message(self, message, context: Dict = None) -> str:
        """
        Handle message/send requests.
        Returns a simple string response.
        """
        # Handle both string and Message object
        if hasattr(message, 'content'):
            query = str(message.content)
        elif hasattr(message, 'text'):
            query = str(message.text)
        else:
            query = str(message)
        
        # Extract context ID from various possible locations
        context_id = None
        if context:
            # Check for sessionId which python-a2a might pass
            context_id = context.get('sessionId') or context.get('session_id') or context.get('contextId') or context.get('context_id')
        
        # Process the query
        result = business_logic.process_discovery_query(
            query=query,
            context_id=context_id,
            limit=10
        )
        
        return result.message


def main():
    """
    Start the server.
    """
    agent_instance = SignalsAgent()
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    print(f"🎯 Starting Simplified Signals Agent on {host}:{port}")
    
    # For production, use a more robust server setup
    if os.getenv("FLY_APP_NAME"):  # Running on Fly.io
        print("Running in production mode on Fly.io")
        # Import Flask app creator
        from python_a2a.server.http import create_flask_app
        app = create_flask_app(agent_instance)
        
        # Add explicit routes to ensure URL field is included
        @app.route('/a2a/agent.json', methods=['GET'])
        @app.route('/.well-known/agent.json', methods=['GET'])
        @app.route('/.well-known/agent-card.json', methods=['GET'])
        def agent_card_json():
            """Return agent card with required URL field."""
            from flask import jsonify
            card = agent_instance.get_agent_card()
            # Ensure URL field is present
            if 'url' not in card or not card['url']:
                card['url'] = 'https://audience-agent.fly.dev/a2a/jsonrpc'
            return jsonify(card)
        
        # Run with production server (Flask will use Werkzeug in production)
        app.run(host=host, port=port, debug=False)
    else:
        # Local development
        run_server(
            agent_instance,
            host=host,
            port=port,
            debug=os.getenv("TEST_MODE", "false").lower() == "true"
        )


if __name__ == "__main__":
    main()