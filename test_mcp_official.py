#!/usr/bin/env python3
"""Test MCP server with official-style client."""

import json
import requests
from typing import Dict, Any

class MCPClient:
    """Simple MCP client for testing."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.request_id = 0
    
    def call(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an MCP JSON-RPC call."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self.request_id
        }
        
        response = self.session.post(
            self.base_url,
            json=request,
            headers={"Content-Type": "application/json"}
        )
        
        result = response.json()
        if "error" in result:
            raise Exception(f"MCP Error: {result['error']}")
        
        return result.get("result", {})

def test_mcp_server():
    """Test the MCP server with official protocol."""
    
    # Use the deployed server
    client = MCPClient("https://audience-agent.fly.dev/mcp")
    
    print("Testing MCP Server at https://audience-agent.fly.dev/mcp")
    print("=" * 60)
    
    # 1. Initialize
    print("\n1. Testing initialize...")
    try:
        result = client.call("initialize", {
            "protocolVersion": "2024-11-05",
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        })
        print(f"✓ Server info: {result.get('serverInfo', {}).get('name')} v{result.get('serverInfo', {}).get('version')}")
        print(f"✓ Protocol version: {result.get('protocolVersion')}")
        print(f"✓ Capabilities: {json.dumps(result.get('capabilities', {}), indent=2)}")
    except Exception as e:
        print(f"✗ Failed: {e}")
        return
    
    # 2. List tools
    print("\n2. Testing tools/list...")
    try:
        result = client.call("tools/list")
        tools = result.get("tools", [])
        print(f"✓ Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
            required = tool.get('inputSchema', {}).get('required', [])
            if required:
                print(f"    Required params: {', '.join(required)}")
    except Exception as e:
        print(f"✗ Failed: {e}")
        return
    
    # 3. Call discover tool
    print("\n3. Testing tools/call with 'discover'...")
    try:
        result = client.call("tools/call", {
            "name": "discover",
            "arguments": {
                "signal_spec": "luxury automotive enthusiasts",
                "deliver_to": {
                    "platforms": "all",
                    "countries": ["US"]
                },
                "max_results": 3
            }
        })
        
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            text = content[0].get("text", "")
            print(f"✓ Discovery result:")
            # Print first 3 lines
            for line in text.split('\n')[:5]:
                if line.strip():
                    print(f"  {line}")
        else:
            print(f"✓ Result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    # 4. Call activate tool (will fail without valid segment ID)
    print("\n4. Testing tools/call with 'activate'...")
    try:
        result = client.call("tools/call", {
            "name": "activate",
            "arguments": {
                "signals_agent_segment_id": "test_segment_123",
                "platform": "index-exchange"
            }
        })
        
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            print(f"✓ Activation result: {content[0].get('text', '')[:100]}...")
        else:
            print(f"✓ Result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"⚠ Expected failure (no valid segment): {str(e)[:100]}")
    
    print("\n" + "=" * 60)
    print("✅ MCP Protocol Test Complete")

if __name__ == "__main__":
    test_mcp_server()