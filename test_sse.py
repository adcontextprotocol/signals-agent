#!/usr/bin/env python3
"""Test SSE streaming for message/send."""

import httpx
import json
import os
import sys

def test_sse_locally():
    """Test SSE streaming locally."""
    print("Testing SSE streaming locally...")
    
    # Test message/send with SSE
    request_data = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "parts": [
                    {"type": "text", "text": "luxury car buyers"}
                ]
            }
        },
        "id": "test-sse-1"
    }
    
    # Use TEST_MODE
    env = os.environ.copy()
    env['TEST_MODE'] = 'true'
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "http://localhost:8000/a2a/jsonrpc",
                json=request_data,
                headers={"Accept": "text/event-stream"}
            )
            
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print(f"Response:\n{response.text[:500]}")
            
            # Check if we got SSE response
            if 'text/event-stream' in response.headers.get('content-type', ''):
                print("✓ Got SSE response!")
                
                # Parse SSE data
                for line in response.text.split('\n'):
                    if line.startswith('data: '):
                        data = line[6:]
                        if data != '[DONE]':
                            result = json.loads(data)
                            print(f"✓ Parsed result: {json.dumps(result, indent=2)[:300]}...")
            else:
                print(f"✗ Expected SSE, got {response.headers.get('content-type')}")
                sys.exit(1)
                
    except httpx.ConnectError:
        print("✗ Could not connect to localhost:8000")
        print("Make sure the server is running with: TEST_MODE=true uv run python main.py")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n✅ SSE test successful!")

if __name__ == "__main__":
    test_sse_locally()