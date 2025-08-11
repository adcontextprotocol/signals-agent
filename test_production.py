#!/usr/bin/env python
"""Test production MCP endpoint."""

import asyncio
import httpx
import json

async def test_production_raw():
    """Test production endpoint with raw HTTP requests."""
    print("Testing production endpoint with raw HTTP...")
    
    url = "https://audience-agent.fly.dev/mcp/"
    
    async with httpx.AsyncClient() as client:
        # Send initialize request
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        # Test with a simple request
        request_data = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            },
            "id": 1
        }
        
        try:
            response = await client.post(url, json=request_data, headers=headers, timeout=10.0)
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            print(f"Response: {response.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

async def test_production_mcp():
    """Test production endpoint with MCP client."""
    from mcp import ClientSession
    from mcp.client.session import transport_from_json_rpc_url
    
    print("\nTesting production MCP endpoint...")
    
    # Use the transport helper to connect to HTTP endpoint
    transport = await transport_from_json_rpc_url("https://audience-agent.fly.dev/mcp/")
    
    async with ClientSession(*transport) as session:
        await session.initialize()
        
        # Test get_signals
        print("Testing get_signals...")
        result = await session.call_tool('get_signals', {
            'signal_spec': 'luxury car buyers',
            'deliver_to': {
                'platforms': 'all',
                'countries': ['US']
            }
        })
        
        if result.isError:
            print(f"Error: {result.content[0].text}")
        else:
            print(f"Success: Found signals")
            for content in result.content:
                print(content.text[:500] if hasattr(content, 'text') else str(content)[:500])

async def main():
    await test_production_raw()
    # Note: MCP client might not work directly with HTTP transport
    # await test_production_mcp()

if __name__ == "__main__":
    asyncio.run(main())