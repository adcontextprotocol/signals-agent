import requests
import json
import time

# Simulate exactly what the A2A client does based on your logs
print("Simulating A2A client behavior...")

# Step 1: Get agent card (this works according to your logs)
agent_card_url = "https://audience-agent.fly.dev/.well-known/agent-card.json"
print(f"\n1. GET {agent_card_url}")
response = requests.get(agent_card_url)
print(f"   Status: {response.status_code}")
card = response.json()
jsonrpc_url = card['url']
print(f"   Agent URL: {jsonrpc_url}")

# Step 2: Send a message (this fails with 404 according to your logs)
print(f"\n2. POST {jsonrpc_url}")

# Try exact request that might be sent
request_body = {
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
        "message": {
            "parts": [
                {"type": "text", "text": "test"}
            ]
        }
    },
    "id": "1"
}

headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "A2A-Client/1.0"
}

print(f"   Request: {json.dumps(request_body)}")
print(f"   Headers: {headers}")

try:
    # Try with very short timeout to simulate potential issue
    response = requests.post(jsonrpc_url, json=request_body, headers=headers, timeout=3)
    print(f"   Status: {response.status_code}")
    if response.status_code != 200:
        print(f"   Response: {response.text}")
    else:
        print(f"   Success!")
except requests.exceptions.Timeout:
    print(f"   TIMEOUT after 3 seconds")
except Exception as e:
    print(f"   Error: {e}")

# Also try without trailing slash if URL has one
if jsonrpc_url.endswith('/'):
    alt_url = jsonrpc_url[:-1]
    print(f"\n3. Trying without trailing slash: {alt_url}")
    try:
        response = requests.post(alt_url, json=request_body, headers=headers, timeout=3)
        print(f"   Status: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
