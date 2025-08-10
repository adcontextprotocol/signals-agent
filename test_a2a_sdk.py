#!/usr/bin/env python3
"""Test with official A2A SDK."""

import asyncio
from a2a.client import A2AClient
import httpx
import sys

async def test_a2a_sdk():
    """Test the production endpoint with official A2A SDK."""
    
    # Initialize client
    print("Initializing A2A SDK client...")
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        client = A2AClient(http_client)
        
        try:
            # Discover the agent
            print("\n1. Discovering agent at https://audience-agent.fly.dev")
            agent = await client.discover("https://audience-agent.fly.dev")
            print(f"   ✓ Agent discovered: {agent}")
            
            # Get agent card
            print("\n2. Getting agent card...")
            card = await client.get_agent_card("https://audience-agent.fly.dev")
            print(f"   ✓ Agent: {card.get('name')}")
            print(f"   ✓ Version: {card.get('version')}")
            print(f"   ✓ URL: {card.get('url')}")
            
            print("\n✅ A2A SDK test successful!")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_a2a_sdk())