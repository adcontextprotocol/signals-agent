#!/usr/bin/env python3
"""Test routing to ensure all endpoints are accessible."""

import requests
import json
import sys

def test_routing(base_url: str = "http://localhost:8000"):
    """Test all critical routing endpoints."""
    
    print(f"Testing routing at {base_url}")
    print("=" * 60)
    
    errors = []
    
    # Test endpoints with their expected methods
    endpoints = [
        ("GET", "/", "Root endpoint"),
        ("GET", "/health", "Health check"),
        ("GET", "/agent-card", "Agent card"),
        ("GET", "/.well-known/agent-card.json", "Well-known agent card"),
        ("POST", "/a2a/task", "A2A task endpoint"),
        ("POST", "/a2a/jsonrpc", "A2A JSON-RPC endpoint"),
        ("POST", "/", "Root JSON-RPC endpoint"),
        ("POST", "/mcp", "MCP endpoint"),
        ("OPTIONS", "/mcp", "MCP OPTIONS"),
    ]
    
    for method, path, description in endpoints:
        try:
            url = f"{base_url}{path}"
            print(f"\n{method} {path} - {description}")
            
            if method == "GET":
                response = requests.get(url, timeout=5)
            elif method == "POST":
                # Send minimal valid payload for each POST endpoint
                if "jsonrpc" in path or path == "/":
                    payload = {
                        "jsonrpc": "2.0",
                        "method": "message/send",
                        "params": {
                            "message": {
                                "content": {
                                    "parts": [
                                        {"kind": "text", "text": "test"}
                                    ]
                                }
                            }
                        },
                        "id": 1
                    }
                elif "task" in path:
                    payload = {"query": "test"}
                elif "mcp" in path:
                    payload = {
                        "jsonrpc": "2.0",
                        "method": "tools/list",
                        "id": 1
                    }
                else:
                    payload = {}
                
                response = requests.post(url, json=payload, timeout=5)
            elif method == "OPTIONS":
                response = requests.options(url, timeout=5)
            else:
                continue
            
            # Check status code
            if response.status_code == 404:
                print(f"  ❌ 404 Not Found")
                errors.append(f"{method} {path}: 404 Not Found")
            elif response.status_code >= 500:
                print(f"  ❌ {response.status_code} Server Error")
                errors.append(f"{method} {path}: {response.status_code} Server Error")
            elif response.status_code >= 400:
                # Some 4xx errors are expected for invalid payloads
                print(f"  ⚠️  {response.status_code} - May be expected for test payload")
            else:
                print(f"  ✅ {response.status_code} OK")
                
                # For successful responses, verify content type
                content_type = response.headers.get('content-type', '')
                if 'json' in content_type and response.text:
                    try:
                        data = response.json()
                        print(f"     Response type: {type(data).__name__}")
                        if isinstance(data, dict):
                            keys = list(data.keys())[:3]
                            print(f"     Keys: {', '.join(keys)}...")
                    except:
                        pass
                        
        except requests.RequestException as e:
            print(f"  ❌ Request failed: {e}")
            errors.append(f"{method} {path}: Request failed - {str(e)}")
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            errors.append(f"{method} {path}: {str(e)}")
    
    # Summary
    print("\n" + "=" * 60)
    if errors:
        print(f"❌ {len(errors)} routing errors found:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("✅ All routes accessible")
        return True

def test_json_rpc_routing(base_url: str = "http://localhost:8000"):
    """Specifically test JSON-RPC routing issues."""
    
    print(f"\n\nTesting JSON-RPC routing at {base_url}")
    print("=" * 60)
    
    # First get the agent card to find the advertised JSON-RPC URL
    try:
        response = requests.get(f"{base_url}/agent-card")
        agent_card = response.json()
        advertised_url = agent_card.get('url')
        print(f"Agent card advertises JSON-RPC at: {advertised_url}")
    except Exception as e:
        print(f"❌ Failed to get agent card: {e}")
        advertised_url = None
    
    # Test JSON-RPC at various endpoints
    json_rpc_endpoints = [
        "/",
        "/a2a/jsonrpc",
    ]
    
    if advertised_url:
        # Extract path from advertised URL
        from urllib.parse import urlparse
        parsed = urlparse(advertised_url)
        if parsed.path and parsed.path not in json_rpc_endpoints:
            json_rpc_endpoints.append(parsed.path)
    
    valid_request = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "content": {
                    "parts": [
                        {"kind": "text", "text": "test message"}
                    ]
                }
            }
        },
        "id": 1
    }
    
    working_endpoints = []
    
    for endpoint in json_rpc_endpoints:
        print(f"\nTesting JSON-RPC at {endpoint}")
        try:
            response = requests.post(
                f"{base_url}{endpoint}",
                json=valid_request,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    print(f"  ✅ Works - got valid JSON-RPC response")
                    working_endpoints.append(endpoint)
                elif "error" in data:
                    print(f"  ⚠️  JSON-RPC error: {data['error'].get('message')}")
                else:
                    print(f"  ❌ Invalid JSON-RPC response structure")
            else:
                print(f"  ❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Failed: {e}")
    
    # Verify advertised URL works
    if advertised_url:
        print(f"\n{'='*60}")
        if advertised_url.endswith('/a2a/jsonrpc') and '/a2a/jsonrpc' in working_endpoints:
            print(f"✅ Agent card URL endpoint is working correctly")
        elif advertised_url and any(advertised_url.endswith(ep) for ep in working_endpoints):
            print(f"✅ Agent card URL endpoint is accessible")
        else:
            print(f"❌ Agent card advertises {advertised_url} but it's not working!")
            return False
    
    return len(working_endpoints) > 0

if __name__ == "__main__":
    import sys
    
    # Accept base URL as argument
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    # Run both test suites
    routing_ok = test_routing(base_url)
    json_rpc_ok = test_json_rpc_routing(base_url)
    
    if routing_ok and json_rpc_ok:
        print("\n✅ All routing tests passed")
        sys.exit(0)
    else:
        print("\n❌ Some routing tests failed")
        sys.exit(1)