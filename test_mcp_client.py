#!/usr/bin/env python
"""Test MCP client for the Signals Agent."""

import asyncio
import sys
from typing import Optional
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def test_local():
    """Test against local MCP server."""
    print("Testing local MCP server...")
    
    server_params = StdioServerParameters(
        command='uv',
        args=['run', 'fastmcp', 'run', 'main.py'],
        env={}
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Test get_signals with proper parameters
            print("\nTesting get_signals...")
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

async def test_production():
    """Test against production endpoint."""
    print("\nTesting production endpoint at https://audience-agent.fly.dev/mcp/...")
    
    # Import httpx for production testing
    import httpx
    from mcp.client.sse import sse_client, SSEServerParameters
    
    server_params = SSEServerParameters(
        url='https://audience-agent.fly.dev/sse/'
    )
    
    try:
        async with sse_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Test get_signals with proper parameters
                print("\nTesting get_signals on production...")
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
    except Exception as e:
        print(f"Failed to connect to production: {e}")
        print("Note: The production server may be using HTTP transport, not SSE")

async def main():
    """Run tests."""
    if len(sys.argv) > 1 and sys.argv[1] == '--production':
        await test_production()
    else:
        await test_local()

if __name__ == "__main__":
    asyncio.run(main())