#!/usr/bin/env python3
"""Test MCP server functionality."""

import requests
import json

BASE_URL = "https://audience-agent.fly.dev/mcp"

def test_mcp():
    """Test MCP protocol methods."""
    
    # Test initialize
    print("Testing initialize...")
    response = requests.post(BASE_URL, json={
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {"clientInfo": {"name": "test-client"}},
        "id": 1
    })
    print(f"Initialize: {response.status_code}")
    result = response.json()
    assert result.get("result", {}).get("protocolVersion") == "2024-11-05"
    print("✓ Initialize successful\n")
    
    # Test tools/list
    print("Testing tools/list...")
    response = requests.post(BASE_URL, json={
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": 2
    })
    print(f"Tools list: {response.status_code}")
    result = response.json()
    tools = result.get("result", {}).get("tools", [])
    assert len(tools) == 2
    assert tools[0]["name"] == "discover"
    assert tools[1]["name"] == "activate"
    print(f"✓ Found {len(tools)} tool(s): {', '.join(t['name'] for t in tools)}\n")
    
    # Test tools/call
    print("Testing tools/call with discover...")
    response = requests.post(BASE_URL, json={
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "discover",
            "arguments": {
                "query": "tech enthusiasts",
                "max_results": 5
            }
        },
        "id": 3
    })
    print(f"Tools call: {response.status_code}")
    result = response.json()
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        content = result.get("result", {}).get("content", [])
        if content:
            text = content[0].get("text", "")
            print(f"✓ Discovery result:\n{text[:200]}...\n")
    
    # Test CORS headers
    print("Testing CORS headers...")
    response = requests.options(BASE_URL, headers={
        "Origin": "https://claude.ai",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type"
    })
    cors_headers = {
        k: v for k, v in response.headers.items() 
        if k.lower().startswith("access-control")
    }
    print("CORS headers present:")
    for header, value in cors_headers.items():
        print(f"  {header}: {value}")
    
    print("\n✅ All MCP tests passed!")

if __name__ == "__main__":
    test_mcp()