#!/usr/bin/env python3
"""Test with python-a2a client."""

import asyncio
from python_a2a import A2AClient

async def test():
    """Test the agent with python-a2a client."""
    
    # First try the working endpoint
    print("Testing with /a2a/agent.json endpoint...")
    client = A2AClient("https://audience-agent.fly.dev/a2a/agent.json")
    
    # Get agent card (not async)
    card = client.get_agent_card()
    print(f"Agent: {card.name}")
    print(f"Version: {card.version}")
    
    # Send a task
    print("\nSending task: 'sports audiences'")
    result = await client.send_task("sports audiences")
    print(f"Result: {result}")
    
    # Also test the .well-known endpoint that's failing
    print("\n\nTrying .well-known endpoint (expected to fail)...")
    try:
        client2 = A2AClient("https://audience-agent.fly.dev")
        card2 = client2.get_agent_card()
        print(f"Success: {card2}")
    except Exception as e:
        print(f"Error as expected: {e}")

if __name__ == "__main__":
    asyncio.run(test())