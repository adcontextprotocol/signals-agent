#!/usr/bin/env python3
"""Test A2A context handling with python-a2a endpoints."""

import json
import requests
import time

def test_context_with_tasks_send():
    """Test context handling via tasks/send endpoint."""
    print("Testing context with /tasks/send endpoint...")
    
    # First query
    print("\n1. Initial query: 'sports enthusiasts'")
    response1 = requests.post(
        "http://localhost:8000/tasks/send",
        json={"query": "sports enthusiasts"}
    )
    
    if response1.status_code == 200:
        result1 = response1.json()
        session_id = result1.get('sessionId')
        task_id = result1.get('id')
        
        print(f"   ✓ Got response")
        print(f"   Session ID: {session_id}")
        print(f"   Task ID: {task_id}")
        
        # Extract the message
        if 'artifacts' in result1:
            for artifact in result1['artifacts']:
                for part in artifact.get('parts', []):
                    if part.get('type') == 'text':
                        print(f"   Message: {part['text'][:100]}...")
                        break
        
        # Follow-up query with session ID
        print("\n2. Follow-up query: 'tell me more about the sports audience'")
        response2 = requests.post(
            "http://localhost:8000/tasks/send",
            json={
                "query": "tell me more about the sports audience",
                "sessionId": session_id  # Pass session ID for context
            }
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            print(f"   ✓ Got follow-up response")
            
            # Check if response references previous context
            if 'artifacts' in result2:
                for artifact in result2['artifacts']:
                    for part in artifact.get('parts', []):
                        if part.get('type') == 'text':
                            message = part['text']
                            print(f"   Message: {message[:150]}...")
                            
                            # Check for contextual keywords
                            context_words = ['previous', 'sports', 'those', 'these', 'mentioned']
                            if any(word in message.lower() for word in context_words):
                                print(f"   ✓ Response appears contextual")
                            else:
                                print(f"   ✗ Response may not be using context")
                            break
        else:
            print(f"   ✗ Follow-up failed: Status {response2.status_code}")
    else:
        print(f"   ✗ Initial query failed: Status {response1.status_code}")

def test_mcp_endpoint():
    """Test MCP endpoint for context handling."""
    print("\n\nTesting MCP endpoint...")
    
    # Test MCP discover with initial query
    mcp_request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "discover_audiences",
            "arguments": {
                "query": "automotive enthusiasts",
                "limit": 5
            }
        },
        "id": "test-1"
    }
    
    print("\n1. MCP query: 'automotive enthusiasts'")
    response = requests.post(
        "http://localhost:8000/mcp",
        json=mcp_request
    )
    
    if response.status_code == 200:
        result = response.json()
        if 'result' in result:
            context_id = result['result'].get('context_id')
            signals_count = len(result['result'].get('signals', []))
            print(f"   ✓ Found {signals_count} signals")
            print(f"   Context ID: {context_id}")
            
            # Follow-up with context
            mcp_followup = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "discover_audiences",
                    "arguments": {
                        "query": "tell me more about these automotive signals",
                        "context_id": context_id
                    }
                },
                "id": "test-2"
            }
            
            print("\n2. MCP follow-up: 'tell me more about these automotive signals'")
            response2 = requests.post(
                "http://localhost:8000/mcp",
                json=mcp_followup
            )
            
            if response2.status_code == 200:
                result2 = response2.json()
                if 'result' in result2:
                    signals_count2 = len(result2['result'].get('signals', []))
                    message = result2['result'].get('message', '')
                    
                    if signals_count2 == signals_count:
                        print(f"   ✓ Context preserved: Same {signals_count2} signals")
                    else:
                        print(f"   ? Different signal count: {signals_count2} vs {signals_count}")
                    
                    print(f"   Message: {message[:100]}...")
            else:
                print(f"   ✗ Follow-up failed: Status {response2.status_code}")
        else:
            print(f"   ✗ No result in response")
    else:
        print(f"   ✗ Initial query failed: Status {response.status_code}")

if __name__ == "__main__":
    print("=== Testing A2A Context Handling ===\n")
    
    # Check server
    try:
        response = requests.get("http://localhost:8000/")
        print("✓ Server is running")
    except:
        print("✗ Server is not running")
        exit(1)
    
    test_context_with_tasks_send()
    test_mcp_endpoint()
    
    print("\n=== Tests Complete ===")