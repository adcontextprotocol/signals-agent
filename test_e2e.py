#!/usr/bin/env python3
"""End-to-end test suite for the Signals Agent.

This comprehensive test suite validates:
1. All endpoints are accessible
2. A2A protocol compliance
3. MCP protocol compliance
4. Context handling works correctly
5. Error handling is proper
"""

import requests
import json
import sys
import time
from typing import Dict, Any, List, Optional
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class TestResult:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []
        self.warnings = []
    
    def add_pass(self, test_name: str):
        self.passed += 1
        print(f"{Colors.OKGREEN}✓{Colors.ENDC} {test_name}")
    
    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"{Colors.FAIL}✗{Colors.ENDC} {test_name}: {error}")
    
    def add_warning(self, message: str):
        self.warnings.append(message)
        print(f"{Colors.WARNING}⚠{Colors.ENDC} {message}")
    
    def add_skip(self, test_name: str, reason: str):
        self.skipped += 1
        print(f"{Colors.WARNING}⊘{Colors.ENDC} {test_name}: {reason}")
    
    def summary(self) -> bool:
        """Print summary and return True if all tests passed."""
        print(f"\n{Colors.BOLD}Test Summary:{Colors.ENDC}")
        print(f"  {Colors.OKGREEN}Passed: {self.passed}{Colors.ENDC}")
        print(f"  {Colors.FAIL}Failed: {self.failed}{Colors.ENDC}")
        print(f"  {Colors.WARNING}Skipped: {self.skipped}{Colors.ENDC}")
        
        if self.errors:
            print(f"\n{Colors.FAIL}Errors:{Colors.ENDC}")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print(f"\n{Colors.WARNING}Warnings:{Colors.ENDC}")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        return self.failed == 0


class E2ETestSuite:
    """End-to-end test suite."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.results = TestResult()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'E2E-Test-Suite/1.0'
        })
    
    def run_all_tests(self):
        """Run all test suites."""
        print(f"{Colors.HEADER}{Colors.BOLD}Running E2E Tests for {self.base_url}{Colors.ENDC}")
        print("=" * 70)
        
        # 1. Basic connectivity
        self.test_basic_connectivity()
        
        # 2. Endpoint accessibility
        self.test_all_endpoints()
        
        # 3. A2A Protocol tests
        self.test_a2a_protocol()
        
        # 4. MCP Protocol tests
        self.test_mcp_protocol()
        
        # 5. Context handling
        self.test_context_handling()
        
        # 6. Error handling
        self.test_error_handling()
        
        # 7. Performance tests
        self.test_performance()
        
        # Summary
        print("\n" + "=" * 70)
        return self.results.summary()
    
    def test_basic_connectivity(self):
        """Test basic server connectivity."""
        print(f"\n{Colors.BOLD}1. Basic Connectivity{Colors.ENDC}")
        
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=35)
            if response.status_code == 200:
                self.results.add_pass("Server is reachable")
            else:
                self.results.add_fail("Server health check", f"Status {response.status_code}")
        except Exception as e:
            self.results.add_fail("Server connectivity", str(e))
            print(f"{Colors.FAIL}Cannot connect to server. Aborting tests.{Colors.ENDC}")
            sys.exit(1)
    
    def test_all_endpoints(self):
        """Test all endpoints are accessible."""
        print(f"\n{Colors.BOLD}2. Endpoint Accessibility{Colors.ENDC}")
        
        endpoints = [
            ("GET", "/", "Root endpoint"),
            ("GET", "/health", "Health check"),
            ("GET", "/agent-card", "Agent card"),
            ("GET", "/.well-known/agent-card.json", "Well-known agent card"),
            ("POST", "/a2a/task", "A2A task endpoint"),
            ("POST", "/a2a/jsonrpc", "A2A JSON-RPC endpoint"),
            ("POST", "/mcp", "MCP endpoint"),
        ]
        
        for method, path, description in endpoints:
            try:
                if method == "GET":
                    response = self.session.get(f"{self.base_url}{path}", timeout=35)
                else:
                    # Send minimal valid payload
                    if "jsonrpc" in path or path == "/":
                        payload = {
                            "jsonrpc": "2.0",
                            "method": "message/send",
                            "params": {"message": {"content": {"parts": [{"kind": "text", "text": "test"}]}}},
                            "id": 1
                        }
                    elif "task" in path:
                        payload = {"query": "test"}
                    elif "mcp" in path:
                        payload = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
                    else:
                        payload = {}
                    
                    response = self.session.post(f"{self.base_url}{path}", json=payload, timeout=35)
                
                if response.status_code == 404:
                    self.results.add_fail(f"{method} {path}", "404 Not Found")
                elif response.status_code >= 500:
                    self.results.add_fail(f"{method} {path}", f"{response.status_code} Server Error")
                else:
                    self.results.add_pass(f"{method} {path}")
                    
            except Exception as e:
                self.results.add_fail(f"{method} {path}", str(e))
    
    def test_a2a_protocol(self):
        """Test A2A protocol compliance."""
        print(f"\n{Colors.BOLD}3. A2A Protocol Compliance{Colors.ENDC}")
        
        # Get agent card
        try:
            response = self.session.get(f"{self.base_url}/agent-card")
            if response.status_code == 200:
                card = response.json()
                
                # Validate required fields
                required = ["name", "description", "version", "url", "protocolVersion", 
                           "capabilities", "skills", "provider"]
                missing = [f for f in required if f not in card]
                
                if missing:
                    self.results.add_fail("Agent card structure", f"Missing fields: {missing}")
                else:
                    self.results.add_pass("Agent card has all required fields")
                    
                    # Test the advertised URL
                    if 'url' in card:
                        json_rpc_url = card['url']
                        try:
                            test_payload = {
                                "jsonrpc": "2.0",
                                "method": "message/send",
                                "params": {"message": {"content": {"parts": [{"kind": "text", "text": "test"}]}}},
                                "id": 1
                            }
                            response = self.session.post(json_rpc_url, json=test_payload, timeout=35)
                            if response.status_code == 200:
                                self.results.add_pass(f"Agent card URL ({json_rpc_url}) is accessible")
                            else:
                                self.results.add_fail(f"Agent card URL", f"Status {response.status_code}")
                        except Exception as e:
                            self.results.add_fail(f"Agent card URL", str(e))
            else:
                self.results.add_fail("Agent card retrieval", f"Status {response.status_code}")
                
        except Exception as e:
            self.results.add_fail("A2A agent card test", str(e))
        
        # Test task execution
        try:
            response = self.session.post(
                f"{self.base_url}/a2a/task",
                json={"query": "test query"},
                timeout=35
            )
            if response.status_code == 200:
                task = response.json()
                if task.get("kind") == "task" and "status" in task:
                    self.results.add_pass("A2A task execution")
                else:
                    self.results.add_fail("A2A task response", "Invalid structure")
            else:
                self.results.add_fail("A2A task execution", f"Status {response.status_code}")
        except Exception as e:
            self.results.add_fail("A2A task test", str(e))
    
    def test_mcp_protocol(self):
        """Test MCP protocol compliance."""
        print(f"\n{Colors.BOLD}4. MCP Protocol Compliance{Colors.ENDC}")
        
        # List tools
        try:
            response = self.session.post(
                f"{self.base_url}/mcp",
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                timeout=35
            )
            if response.status_code == 200:
                result = response.json()
                if "result" in result and "tools" in result["result"]:
                    tools = result["result"]["tools"]
                    self.results.add_pass(f"MCP tools/list ({len(tools)} tools)")
                    
                    # Check for expected tools
                    tool_names = [t["name"] for t in tools]
                    if "discover" in tool_names and "activate" in tool_names:
                        self.results.add_pass("MCP has discover and activate tools")
                    else:
                        self.results.add_warning("MCP missing expected tools")
                else:
                    self.results.add_fail("MCP tools/list", "Invalid response structure")
            else:
                self.results.add_fail("MCP tools/list", f"Status {response.status_code}")
        except Exception as e:
            self.results.add_fail("MCP protocol test", str(e))
    
    def test_context_handling(self):
        """Test context handling for follow-up queries."""
        print(f"\n{Colors.BOLD}5. Context Handling{Colors.ENDC}")
        
        try:
            # First query
            response1 = self.session.post(
                f"{self.base_url}/a2a/jsonrpc",
                json={
                    "jsonrpc": "2.0",
                    "method": "message/send",
                    "params": {"message": {"content": {"parts": [{"kind": "text", "text": "sport"}]}}},
                    "id": 1
                },
                timeout=35
            )
            
            if response1.status_code == 200:
                result1 = response1.json()
                if "result" in result1 and "contextId" in result1["result"]:
                    context_id = result1["result"]["contextId"]
                    self.results.add_pass("First query returns context ID")
                    
                    # Follow-up query
                    response2 = self.session.post(
                        f"{self.base_url}/a2a/jsonrpc",
                        json={
                            "jsonrpc": "2.0",
                            "method": "message/send",
                            "params": {
                                "message": {"content": {"parts": [{"kind": "text", "text": "tell me more"}]}},
                                "contextId": context_id
                            },
                            "id": 2
                        },
                        timeout=35
                    )
                    
                    if response2.status_code == 200:
                        result2 = response2.json()
                        if "result" in result2:
                            msg1 = result1["result"]["parts"][0]["text"]
                            msg2 = result2["result"]["parts"][0]["text"]
                            
                            # Check if second message is contextual (different from first)
                            if msg1 != msg2 and "more" in msg2.lower():
                                self.results.add_pass("Context handling works")
                            else:
                                self.results.add_warning("Context may not be working properly")
                    else:
                        self.results.add_fail("Follow-up query", f"Status {response2.status_code}")
                else:
                    self.results.add_fail("Context ID", "Not returned in response")
            else:
                self.results.add_fail("Initial context query", f"Status {response1.status_code}")
                
        except Exception as e:
            self.results.add_fail("Context handling test", str(e))
    
    def test_error_handling(self):
        """Test error handling."""
        print(f"\n{Colors.BOLD}6. Error Handling{Colors.ENDC}")
        
        # Invalid JSON-RPC
        try:
            response = self.session.post(
                f"{self.base_url}/a2a/jsonrpc",
                json={"invalid": "request"},
                timeout=35
            )
            if response.status_code in [400, 422]:
                self.results.add_pass("Invalid JSON-RPC rejected properly")
            else:
                self.results.add_warning(f"Invalid JSON-RPC returned {response.status_code}")
        except Exception as e:
            self.results.add_fail("Error handling test", str(e))
        
        # Method not found
        try:
            response = self.session.post(
                f"{self.base_url}/a2a/jsonrpc",
                json={"jsonrpc": "2.0", "method": "invalid/method", "id": 1},
                timeout=35
            )
            if response.status_code == 404 or (response.status_code == 200 and "error" in response.json()):
                self.results.add_pass("Unknown method handled properly")
            else:
                self.results.add_warning(f"Unknown method returned {response.status_code}")
        except Exception as e:
            self.results.add_fail("Method not found test", str(e))
    
    def test_performance(self):
        """Test performance and response times."""
        print(f"\n{Colors.BOLD}7. Performance{Colors.ENDC}")
        
        # Test response time
        try:
            start = time.time()
            response = self.session.get(f"{self.base_url}/health", timeout=35)
            elapsed = time.time() - start
            
            if elapsed < 1.0:
                self.results.add_pass(f"Health check response time ({elapsed:.2f}s)")
            else:
                self.results.add_warning(f"Health check slow ({elapsed:.2f}s)")
                
        except Exception as e:
            self.results.add_fail("Performance test", str(e))
        
        # Test multiple concurrent requests
        try:
            import concurrent.futures
            
            def make_request():
                return self.session.post(
                    f"{self.base_url}/a2a/jsonrpc",
                    json={
                        "jsonrpc": "2.0",
                        "method": "message/send",
                        "params": {"message": {"content": {"parts": [{"kind": "text", "text": "test"}]}}},
                        "id": 1
                    },
                    timeout=35
                )
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(make_request) for _ in range(3)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
                
                success_count = sum(1 for r in results if r.status_code == 200)
                if success_count == 3:
                    self.results.add_pass("Handles concurrent requests")
                else:
                    self.results.add_warning(f"Only {success_count}/3 concurrent requests succeeded")
                    
        except Exception as e:
            self.results.add_skip("Concurrent requests", str(e))


def main():
    """Main test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="End-to-end test suite for Signals Agent")
    parser.add_argument("url", nargs="?", default="http://localhost:8000",
                       help="Base URL to test (default: http://localhost:8000)")
    parser.add_argument("--production", action="store_true",
                       help="Test production deployment")
    
    args = parser.parse_args()
    
    if args.production:
        url = "https://audience-agent.fly.dev"
    else:
        url = args.url
    
    print(f"{Colors.BOLD}Signals Agent E2E Test Suite{Colors.ENDC}")
    print(f"Testing: {url}")
    print(f"Time: {datetime.now().isoformat()}")
    print()
    
    suite = E2ETestSuite(url)
    success = suite.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()