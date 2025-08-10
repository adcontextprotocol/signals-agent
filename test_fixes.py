#!/usr/bin/env python3
"""Test script to verify agent card and context handling fixes."""

import json
import requests

def test_agent_card():
    """Test that agent card includes required URL field."""
    print("Testing agent card...")
    
    # Test different endpoints
    endpoints = [
        "http://localhost:8000/.well-known/agent.json",
        "http://localhost:8000/.well-known/agent-card.json",
        "http://localhost:8000/a2a/agent.json"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint)
            if response.status_code == 200:
                card = response.json()
                print(f"✓ {endpoint}: Found agent card")
                
                # Check for required URL field
                if 'url' in card:
                    print(f"  ✓ URL field present: {card['url']}")
                else:
                    print(f"  ✗ URL field missing!")
                    
                # Check other fields
                if 'name' in card:
                    print(f"  ✓ Name: {card['name']}")
                if 'version' in card:
                    print(f"  ✓ Version: {card['version']}")
                    
            else:
                print(f"✗ {endpoint}: Status {response.status_code}")
        except Exception as e:
            print(f"✗ {endpoint}: {e}")
    
    print()

def test_context_handling():
    """Test that context is properly handled in follow-up queries."""
    print("Testing context handling...")
    
    # First query - establish context
    first_query = {
        "query": "luxury car buyers",
        "limit": 5
    }
    
    print("1. Initial query: 'luxury car buyers'")
    response = requests.post(
        "http://localhost:8000/discover",
        json=first_query
    )
    
    if response.status_code == 200:
        result = response.json()
        context_id = result.get('context_id')
        signals_count = len(result.get('signals', []))
        print(f"   ✓ Found {signals_count} signals")
        print(f"   ✓ Context ID: {context_id}")
        
        if signals_count > 0:
            print(f"   ✓ First signal: {result['signals'][0]['name']}")
        
        # Follow-up query using context
        print("\n2. Follow-up query: 'tell me more about these signals'")
        follow_up = {
            "query": "tell me more about these signals",
            "context_id": context_id
        }
        
        response2 = requests.post(
            "http://localhost:8000/discover",
            json=follow_up
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            signals_count2 = len(result2.get('signals', []))
            
            # Check if same signals are returned (context preserved)
            if signals_count2 == signals_count:
                print(f"   ✓ Context preserved: Same {signals_count2} signals returned")
            else:
                print(f"   ✗ Context not preserved: Got {signals_count2} signals instead of {signals_count}")
                
            # Check if message indicates contextual response
            message = result2.get('message', '')
            if 'previous' in message.lower() or 'more details' in message.lower():
                print(f"   ✓ Contextual message: {message[:100]}...")
            else:
                print(f"   ? Message: {message[:100]}...")
                
        else:
            print(f"   ✗ Follow-up failed: Status {response2.status_code}")
            
    else:
        print(f"   ✗ Initial query failed: Status {response.status_code}")
    
    print()

def test_a2a_protocol():
    """Test A2A protocol with context."""
    print("Testing A2A protocol with context...")
    
    # Test message/send with initial query
    message1 = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "parts": [
                    {
                        "type": "text",
                        "content": "sports enthusiasts"
                    }
                ]
            }
        },
        "id": "test-1"
    }
    
    print("1. A2A initial message: 'sports enthusiasts'")
    response = requests.post(
        "http://localhost:8000/",
        json=message1
    )
    
    if response.status_code == 200:
        result = response.json()
        if 'result' in result:
            context_id = result['result'].get('context_id')
            print(f"   ✓ Got response with context: {context_id}")
            
            # Follow-up with context
            message2 = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "message": {
                        "parts": [
                            {
                                "type": "text",
                                "content": "tell me more about the sports audience"
                            }
                        ]
                    },
                    "context": {
                        "context_id": context_id
                    }
                },
                "id": "test-2"
            }
            
            print("\n2. A2A follow-up: 'tell me more about the sports audience'")
            response2 = requests.post(
                "http://localhost:8000/",
                json=message2
            )
            
            if response2.status_code == 200:
                result2 = response2.json()
                if 'result' in result2:
                    message = result2['result'].get('message', '')
                    if 'sports' in message.lower():
                        print(f"   ✓ Context preserved in response")
                        print(f"   Message: {message[:100]}...")
                    else:
                        print(f"   ✗ Context may not be preserved")
                        print(f"   Message: {message[:100]}...")
            else:
                print(f"   ✗ Follow-up failed: Status {response2.status_code}")
        else:
            print(f"   ✗ No result in response")
    else:
        print(f"   ✗ Initial message failed: Status {response.status_code}")

if __name__ == "__main__":
    print("=== Testing Agent Fixes ===\n")
    
    # Make sure server is running
    try:
        response = requests.get("http://localhost:8000/")
        print("✓ Server is running\n")
    except:
        print("✗ Server is not running. Please start it first with:\n")
        print("  python signals_agent_simple.py\n")
        exit(1)
    
    test_agent_card()
    test_context_handling()
    test_a2a_protocol()
    
    print("=== Tests Complete ===")