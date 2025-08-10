#!/usr/bin/env python3
"""Simple test for context handling."""

import json
import requests
import time

print("Test: Context handling via /tasks/send\n")

# Query 1: Sports
print("1. Query: 'sports enthusiasts'")
r1 = requests.post("http://localhost:8000/tasks/send", json={"query": "sports enthusiasts"})
if r1.status_code == 200:
    data1 = r1.json()
    session_id = data1.get('sessionId', '')
    text1 = ""
    if 'artifacts' in data1:
        for a in data1['artifacts']:
            for p in a.get('parts', []):
                if p.get('type') == 'text':
                    text1 = p.get('text', '')[:150]
                    break
    print(f"   Session: {session_id}")
    print(f"   Response: {text1}...")
    
    # Query 2: Follow-up with sessionId
    time.sleep(0.5)
    print(f"\n2. Follow-up: 'tell me more about the sports audience' (session={session_id[:8]}...)")
    r2 = requests.post("http://localhost:8000/tasks/send", json={
        "query": "tell me more about the sports audience",
        "sessionId": session_id
    })
    
    if r2.status_code == 200:
        data2 = r2.json()
        text2 = ""
        if 'artifacts' in data2:
            for a in data2['artifacts']:
                for p in a.get('parts', []):
                    if p.get('type') == 'text':
                        text2 = p.get('text', '')[:150]
                        break
        print(f"   Response: {text2}...")
        
        # Check if it's contextual
        if 'sports' in text2.lower() or 'previous' in text2.lower():
            print("   ✓ Context appears to be preserved!")
        else:
            print("   ✗ Context NOT preserved (got unrelated response)")
    else:
        print(f"   Error: {r2.status_code}")
else:
    print(f"   Error: {r1.status_code}")
    if r1.text:
        print(f"   Details: {r1.text[:200]}")