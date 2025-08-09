#!/usr/bin/env python3
"""Test A2A protocol with official-style client."""

import json
import requests
from typing import Dict, Any, Optional

class A2AClient:
    """Simple A2A client for testing."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.context_id = None
    
    def get_agent_card(self) -> Dict[str, Any]:
        """Fetch the agent card."""
        response = self.session.get(f"{self.base_url}/agent-card")
        response.raise_for_status()
        return response.json()
    
    def execute_task(self, query: str, context_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute an A2A task."""
        request = {
            "query": query
        }
        if context_id:
            request["contextId"] = context_id
        
        response = self.session.post(
            f"{self.base_url}/a2a/task",
            json=request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()
    
    def send_message(self, message: str, context_id: Optional[str] = None, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """Send a JSON-RPC message."""
        request = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [
                        {"kind": "text", "text": message}
                    ]
                }
            },
            "id": 1
        }
        if context_id:
            request["params"]["contextId"] = context_id
        
        # Use provided endpoint or default to base URL
        url = endpoint if endpoint else self.base_url
        
        response = self.session.post(
            url,
            json=request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()

def validate_agent_card(card: Dict[str, Any]) -> bool:
    """Validate agent card structure."""
    required_fields = [
        "name", "description", "version", "url", "protocolVersion",
        "capabilities", "skills", "provider"
    ]
    
    missing = [f for f in required_fields if f not in card]
    if missing:
        print(f"✗ Missing required fields: {', '.join(missing)}")
        return False
    
    # Check provider structure
    provider = card.get("provider", {})
    if not all(k in provider for k in ["name", "organization", "url"]):
        print("✗ Provider missing required fields")
        return False
    
    # Check skills structure
    skills = card.get("skills", [])
    if not skills:
        print("✗ No skills defined")
        return False
    
    for skill in skills:
        if not all(k in skill for k in ["id", "name", "description"]):
            print("✗ Skill missing required fields")
            return False
    
    return True

def test_a2a_server():
    """Test the A2A server with official protocol."""
    
    client = A2AClient("https://audience-agent.fly.dev")
    
    print("Testing A2A Server at https://audience-agent.fly.dev")
    print("=" * 60)
    
    # 1. Test agent card
    print("\n1. Testing Agent Card...")
    try:
        card = client.get_agent_card()
        if validate_agent_card(card):
            print(f"✓ Agent: {card['name']} v{card['version']}")
            print(f"✓ Protocol: {card['protocolVersion']}")
            print(f"✓ URL: {card['url']}")
            print(f"✓ Provider: {card['provider']['organization']}")
            print(f"✓ Skills: {', '.join(s['name'] for s in card['skills'])}")
            print(f"✓ Streaming: {card['capabilities'].get('streaming', False)}")
            
            # Store the JSON-RPC endpoint URL from agent card
            client.jsonrpc_url = card.get('url')
    except Exception as e:
        print(f"✗ Failed: {e}")
        return
    
    # 2. Test .well-known endpoint
    print("\n2. Testing .well-known/agent-card.json...")
    try:
        response = requests.get("https://audience-agent.fly.dev/.well-known/agent-card.json")
        response.raise_for_status()
        wellknown_card = response.json()
        if wellknown_card.get("name") == card.get("name"):
            print("✓ .well-known endpoint working")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    # 3. Test task execution
    print("\n3. Testing Task Execution...")
    try:
        result = client.execute_task("automotive enthusiasts")
        
        # Validate task response structure
        if result.get("kind") != "task":
            print(f"✗ Invalid kind: {result.get('kind')}")
        elif "status" not in result:
            print("✗ Missing status field")
        else:
            status = result["status"]
            print(f"✓ Task ID: {result.get('id')}")
            print(f"✓ Status: {status.get('state')}")
            print(f"✓ Context ID: {result.get('contextId')}")
            
            # Store context for next test
            client.context_id = result.get('contextId')
            
            # Check message
            if status.get("state") == "completed" and "message" in status:
                msg = status["message"]
                if msg.get("kind") == "message" and "parts" in msg:
                    text_parts = [p for p in msg["parts"] if p.get("kind") == "text"]
                    if text_parts:
                        text = text_parts[0].get("text", "")[:150]
                        print(f"✓ Response: {text}...")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    # 4. Test contextual query
    print("\n4. Testing Contextual Query...")
    if client.context_id:
        try:
            result = client.execute_task("tell me more about these", client.context_id)
            
            status = result.get("status", {})
            if status.get("state") == "completed":
                # Check if context was maintained
                if result.get("contextId") == client.context_id:
                    print(f"✓ Context maintained: {client.context_id}")
                
                msg = status.get("message", {})
                text_parts = [p for p in msg.get("parts", []) if p.get("kind") == "text"]
                if text_parts:
                    text = text_parts[0].get("text", "")[:150]
                    print(f"✓ Contextual response: {text}...")
        except Exception as e:
            print(f"✗ Failed: {e}")
    
    # 5. Test JSON-RPC message at root endpoint
    print("\n5. Testing JSON-RPC message/send at root...")
    try:
        result = client.send_message("sports audiences")
        
        if "result" in result:
            msg = result["result"]
            if msg.get("kind") == "message" and msg.get("role") == "agent":
                parts = msg.get("parts", [])
                text_parts = [p for p in parts if p.get("kind") == "text"]
                if text_parts:
                    text = text_parts[0].get("text", "")[:150]
                    print(f"✓ Message response: {text}...")
        elif "error" in result:
            print(f"✗ Error: {result['error']}")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    # 6. Test JSON-RPC at URL from agent card
    print("\n6. Testing JSON-RPC at agent card URL...")
    if hasattr(client, 'jsonrpc_url') and client.jsonrpc_url:
        try:
            result = client.send_message("entertainment audiences", endpoint=client.jsonrpc_url)
            
            if "result" in result:
                msg = result["result"]
                if msg.get("kind") == "message" and msg.get("role") == "agent":
                    parts = msg.get("parts", [])
                    text_parts = [p for p in parts if p.get("kind") == "text"]
                    if text_parts:
                        text = text_parts[0].get("text", "")[:150]
                        print(f"✓ Agent card URL works: {client.jsonrpc_url}")
                        print(f"✓ Message response: {text}...")
            elif "error" in result:
                print(f"✗ Error: {result['error']}")
        except Exception as e:
            print(f"✗ Failed at {client.jsonrpc_url}: {e}")
    
    print("\n" + "=" * 60)
    print("✅ A2A Protocol Test Complete")

if __name__ == "__main__":
    test_a2a_server()