#!/usr/bin/env python3
"""Test streaming functionality."""

import requests
import json
import sys

def test_streaming():
    """Test the streaming endpoint."""
    url = "http://localhost:8000/a2a/task/stream"
    
    # Test query
    payload = {
        "query": "luxury car enthusiasts",
        "instruction": "Find luxury car audiences with streaming"
    }
    
    print("Testing streaming endpoint...")
    print(f"Request: {json.dumps(payload, indent=2)}")
    print("\nStreaming response:")
    print("-" * 50)
    
    try:
        # Make streaming request
        response = requests.post(url, json=payload, stream=True)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            return False
        
        # Process stream
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:]  # Remove "data: " prefix
                    try:
                        data = json.loads(data_str)
                        
                        # Format output based on type
                        if data['type'] == 'status':
                            print(f"📊 Status: {data['state']} - {data.get('message', '')}")
                        elif data['type'] == 'intent':
                            print(f"🎯 Intent: {data['data']['intent']}")
                        elif data['type'] == 'signal':
                            signal = data['signal']
                            print(f"📡 Signal {data['index']}/{data['total']}: {signal['name']} (Coverage: {signal['coverage']}%)")
                        elif data['type'] == 'custom_proposal':
                            proposal = data['proposal']
                            print(f"💡 Custom Proposal {data['index']}: {proposal['name']}")
                        elif data['type'] == 'message':
                            print(f"💬 Response: {data['text']}")
                        elif data['type'] == 'complete':
                            print(f"✅ Stream completed!")
                        else:
                            print(f"📦 {data['type']}: {data}")
                            
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse: {data_str}")
        
        print("-" * 50)
        print("Streaming test completed successfully!")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        print("Make sure the server is running with: TEST_MODE=true uv run python unified_server_v2.py")
        return False

def test_agent_card():
    """Test that agent card shows streaming capability."""
    url = "http://localhost:8000/agent-card"
    
    print("\nTesting agent card...")
    response = requests.get(url)
    
    if response.status_code == 200:
        card = response.json()
        streaming = card.get('capabilities', {}).get('streaming', False)
        
        if streaming:
            print(f"✅ Agent card shows streaming: {streaming}")
            endpoint = card.get('capabilities', {}).get('extensions', {}).get('streaming_endpoint')
            if endpoint:
                print(f"   Streaming endpoint: {endpoint}")
        else:
            print(f"❌ Agent card shows streaming: {streaming}")
            
        return streaming
    else:
        print(f"Failed to get agent card: {response.status_code}")
        return False

if __name__ == "__main__":
    # Test agent card first
    card_ok = test_agent_card()
    
    # Test streaming
    stream_ok = test_streaming()
    
    # Exit with appropriate code
    sys.exit(0 if (card_ok and stream_ok) else 1)