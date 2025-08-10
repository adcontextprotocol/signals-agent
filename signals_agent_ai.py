#!/usr/bin/env python3
"""
Signals Agent using python-a2a with proper AI integration.
Based on the library's AI agent examples.
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import python-a2a components
from python_a2a import A2AServer, agent
from python_a2a.models import TaskStatus, TaskState

# For Gemini integration
import google.generativeai as genai

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
    AI-powered agent using Gemini for natural language processing.
    """
    
    def __init__(self):
        super().__init__()
        
        # Load configuration
        config_path = os.getenv("CONFIG_PATH", "config.json")
        self.config = {}
        if os.path.exists(config_path):
            with open(config_path) as f:
                self.config = json.load(f)
        
        # Initialize Gemini if API key available
        self.ai_model = None
        api_key = self.config.get('gemini_api_key') or os.getenv('GEMINI_API_KEY')
        if api_key and api_key != "your-gemini-api-key-here":
            genai.configure(api_key=api_key)
            self.ai_model = genai.GenerativeModel('gemini-2.0-flash-exp')
            print("✅ Gemini AI initialized")
        else:
            print("⚠️ No Gemini API key found - using basic responses")
    
    def get_agent_card(self) -> Dict[str, Any]:
        """
        Return properly formatted agent card with all required fields.
        """
        base_url = os.getenv("BASE_URL", "https://audience-agent.fly.dev")
        
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "url": f"{base_url}/a2a/jsonrpc",  # Required URL field
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": False,
                "google_a2a_compatible": True,
                "parts_array_format": True
            },
            "skills": [
                {
                    "id": "discover_audiences",
                    "name": "Discover Audiences",
                    "description": "Find audience segments using natural language",
                    "tags": ["discovery", "audiences", "search"]
                },
                {
                    "id": "search_signals",
                    "name": "Search Signals",
                    "description": "Search for specific signals in the database",
                    "tags": ["signals", "search"]
                },
                {
                    "id": "get_platforms",
                    "name": "List Platforms",
                    "description": "Get available advertising platforms",
                    "tags": ["platforms", "list"]
                }
            ],
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "protocolVersion": "a2a/v1"
        }
    
    async def handle_task(self, message) -> TaskStatus:
        """
        Handle incoming task requests with AI processing.
        """
        try:
            # Extract text from message - handle various formats
            query = ""
            if hasattr(message, 'parts'):
                for part in message.parts:
                    if hasattr(part, 'text'):
                        query = part.text
                        break
                    elif hasattr(part, 'content'):
                        query = str(part.content)
                        break
            elif hasattr(message, 'content'):
                query = str(message.content)
            elif hasattr(message, 'text'):
                query = message.text
            else:
                query = str(message)
            
            # Process with business logic
            result = business_logic.process_discovery_query(
                query=query,
                context_id=getattr(message, 'context_id', None)
            )
            
            # Build response data
            response_data = {
                "message": result.message,
                "signals": [],
                "context_id": result.context_id
            }
            
            # Add signals if we have them
            if result.signals:
                response_data["signals"] = [
                    {
                        "id": s.id,
                        "name": s.name,
                        "description": s.description,
                        "coverage": s.coverage,
                        "cpm": s.cpm,
                        "source": s.source
                    } for s in result.signals[:5]
                ]
                response_data["total_found"] = len(result.signals)
            
            return TaskStatus(
                state=TaskState.COMPLETED,
                message=result.message,
                data=response_data
            )
            
        except Exception as e:
            return TaskStatus(
                state=TaskState.FAILED,
                message=f"Error: {str(e)}"
            )
    
    async def handle_message(self, message: str, context: Optional[Dict] = None) -> str:
        """
        Handle message/send requests with AI enhancement.
        """
        try:
            # Extract context if provided
            context_id = None
            if context:
                context_id = context.get("contextId") or context.get("context_id")
            
            # If we have AI, enhance the response
            if self.ai_model and not os.getenv("TEST_MODE"):
                # Process with business logic first to get signals
                result = business_logic.process_discovery_query(
                    query=message,
                    context_id=context_id
                )
                
                # Enhance response with AI
                if result.signals:
                    prompt = f"""
                    The user asked: "{message}"
                    
                    I found these audience segments:
                    {json.dumps([{
                        'name': s.name,
                        'description': s.description,
                        'coverage': s.coverage,
                        'cpm': s.cpm
                    } for s in result.signals[:3]], indent=2)}
                    
                    Provide a helpful, concise response (2-3 sentences) that:
                    1. Confirms what was found
                    2. Highlights the best options
                    3. Mentions availability across platforms
                    
                    Be conversational and helpful.
                    """
                    
                    try:
                        response = self.ai_model.generate_content(prompt)
                        return response.text
                    except:
                        # Fallback to business logic response
                        return result.message
            
            # No AI available, use business logic
            result = business_logic.process_discovery_query(
                query=message,
                context_id=context_id
            )
            return result.message
            
        except Exception as e:
            return f"I encountered an error processing your request: {str(e)}"
    
    # Skills are defined as methods
    
    async def discover_audiences(
        self,
        query: str,
        limit: int = 10,
        principal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Skill: Discover audience segments.
        """
        result = business_logic.process_discovery_query(
            query=query,
            principal_id=principal_id,
            limit=limit
        )
        
        return {
            "success": True,
            "message": result.message,
            "signals": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "coverage": s.coverage,
                    "cpm": s.cpm
                } for s in result.signals[:limit]
            ],
            "context_id": result.context_id,
            "total_found": len(result.signals)
        }
    
    async def search_signals(
        self,
        search_term: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Skill: Search for specific signals.
        """
        from schemas import DeliverySpecification
        spec = DeliverySpecification(platforms="all", limit=limit)
        signals = core_logic.get_signals_core(
            signal_spec=search_term,
            deliver_to=spec
        )
        
        return {
            "success": True,
            "count": len(signals),
            "signals": signals
        }
    
    async def get_platforms(self) -> Dict[str, Any]:
        """
        Skill: List available platforms.
        """
        platforms = business_logic.get_available_platforms()
        
        return {
            "success": True,
            "platforms": platforms,
            "count": len(platforms)
        }


def main():
    """
    Start the AI-powered agent server.
    """
    # Create agent instance
    agent_instance = SignalsAgent()
    
    # Server configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    print(f"🚀 Starting AI-Powered Signals Agent")
    print(f"📍 Server: http://{host}:{port}")
    print(f"🤖 AI Model: {'Gemini 2.0' if agent_instance.ai_model else 'Disabled (no API key)'}")
    # Get signal count
    from schemas import DeliverySpecification
    dummy_spec = DeliverySpecification(platforms="all", limit=100)
    print(f"📊 Database: {len(core_logic.get_signals_core('', dummy_spec))} signals loaded")
    
    # Check if running on Fly.io
    if os.getenv("FLY_APP_NAME"):
        print("☁️ Running in production on Fly.io")
        
        # Use Flask app with proper configuration
        from python_a2a.server.http import create_flask_app
        from flask import jsonify
        
        app = create_flask_app(agent_instance)
        
        # Override the agent card endpoint to ensure proper format
        @app.route('/a2a/agent.json', methods=['GET'])
        @app.route('/agent-card', methods=['GET'])
        @app.route('/agent.json', methods=['GET'])
        @app.route('/.well-known/agent.json', methods=['GET'])
        @app.route('/.well-known/agent-card.json', methods=['GET'])
        def agent_card_json():
            """Return properly formatted agent card."""
            return jsonify(agent_instance.get_agent_card())
        
        # Run Flask app
        app.run(host=host, port=port, debug=False)
    else:
        # Local development
        from python_a2a import run_server
        run_server(
            agent_instance,
            host=host,
            port=port,
            debug=os.getenv("TEST_MODE", "false").lower() == "true"
        )


if __name__ == "__main__":
    main()