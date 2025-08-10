#!/usr/bin/env python3
"""Debug session handling in python-a2a."""

import json
import requests

# Test 1: Send a task and examine the response structure
print("Test 1: Initial task")
response1 = requests.post(
    "http://localhost:8000/tasks/send",
    json={"query": "sports fans"}
)

print(f"Status: {response1.status_code}")
result1 = response1.json()
print(f"Response keys: {result1.keys()}")
print(f"Session ID: {result1.get('sessionId')}")
print(f"Task ID: {result1.get('id')}")
print(f"Full response:\n{json.dumps(result1, indent=2)}\n")

# Test 2: Send follow-up with sessionId
session_id = result1.get('sessionId')
print(f"Test 2: Follow-up with sessionId={session_id}")
response2 = requests.post(
    "http://localhost:8000/tasks/send",
    json={
        "query": "tell me more about sports",
        "sessionId": session_id
    }
)

print(f"Status: {response2.status_code}")
result2 = response2.json()
print(f"Response keys: {result2.keys()}")
print(f"Session ID matches: {result2.get('sessionId') == session_id}")
print(f"Full response:\n{json.dumps(result2, indent=2)}\n")

# Test 3: Try with context parameter instead
print(f"Test 3: Follow-up with context parameter")
response3 = requests.post(
    "http://localhost:8000/tasks/send",
    json={
        "query": "what about the sports signals?",
        "context": {
            "sessionId": session_id,
            "context_id": session_id
        }
    }
)

print(f"Status: {response3.status_code}")
result3 = response3.json()
print(f"Full response:\n{json.dumps(result3, indent=2)}")