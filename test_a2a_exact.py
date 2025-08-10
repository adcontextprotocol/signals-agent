#!/usr/bin/env python3
"""Test with A2A SDK to reproduce exact client behavior."""

import asyncio
from a2a.client import A2AClient
from a2a.types import SendMessageRequest, MessageSendParams, Message, TextPart
import httpx
import sys
import uuid

async def test_a2a_client():
    """Test with actual A2A SDK client."""
    
    url = "http://localhost:8000"
    
    print(f"Testing A2A client with {url}")
    
    try:
        # Create HTTP client with timeout
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # Initialize A2A client with httpx_client first, then url
            client = A2AClient(http_client, url=url)
            
            print("Sending message: 'sports audiences'")
            
            # Create proper message request
            message = Message(
                messageId=str(uuid.uuid4()),
                role="user",
                parts=[TextPart(type="text", text="sports audiences")]
            )
            
            params = MessageSendParams(message=message)
            
            request = SendMessageRequest(
                id=str(uuid.uuid4()),
                params=params
            )
            
            # Send message
            response = await client.send_message(request)
            
            print(f"Response: {response}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_a2a_client())