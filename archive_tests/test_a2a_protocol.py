#!/usr/bin/env python3
"""
Comprehensive A2A Protocol Test Suite
Tests the Audience Agent's compliance with the A2A (Agent-to-Agent) protocol.
"""

import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import sys

console = Console()

class A2AProtocolTester:
    """Test suite for A2A protocol compliance."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        
    def run_all_tests(self):
        """Run all A2A protocol tests."""
        console.print(Panel.fit(
            "[bold blue]A2A Protocol Compliance Test Suite[/bold blue]\n"
            f"Testing: {self.base_url}",
            title="A2A Protocol Tests"
        ))
        
        # Test suite
        self.test_agent_card()
        self.test_wellknown_agent_card()
        self.test_json_rpc_message()
        self.test_task_discovery()
        self.test_task_activation()
        self.test_contextual_queries()
        self.test_cors_headers()
        self.test_error_handling()
        
        # Display results
        self.display_results()
        
        # Return success/failure
        return all(r["passed"] for r in self.results)
    
    def test_agent_card(self):
        """Test agent card endpoint."""
        try:
            response = requests.get(f"{self.base_url}/agent-card")
            card = response.json()
            
            # Validate required fields
            required_fields = ["name", "description", "version", "capabilities", "skills", "provider"]
            missing = [f for f in required_fields if f not in card]
            
            if response.status_code == 200 and not missing:
                self.results.append({"test": "Agent Card (/agent-card)", "passed": True, "note": f"v{card.get('version')}"})
            else:
                self.results.append({"test": "Agent Card (/agent-card)", "passed": False, "note": f"Missing: {missing}"})
        except Exception as e:
            self.results.append({"test": "Agent Card (/agent-card)", "passed": False, "note": str(e)})
    
    def test_wellknown_agent_card(self):
        """Test .well-known/agent.json endpoint."""
        try:
            response = requests.get(f"{self.base_url}/.well-known/agent.json")
            if response.status_code == 200:
                card = response.json()
                self.results.append({"test": "Well-Known Agent Card", "passed": True, "note": "/.well-known/agent.json"})
            else:
                self.results.append({"test": "Well-Known Agent Card", "passed": False, "note": f"Status: {response.status_code}"})
        except Exception as e:
            self.results.append({"test": "Well-Known Agent Card", "passed": False, "note": str(e)})
    
    def test_json_rpc_message(self):
        """Test JSON-RPC message/send format."""
        try:
            request = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "message": {
                        "kind": "message",
                        "message_id": f"msg_{datetime.now().timestamp()}",
                        "parts": [{
                            "kind": "text",
                            "text": "luxury travel"
                        }],
                        "role": "user"
                    }
                },
                "id": "test-jsonrpc"
            }
            
            response = requests.post(self.base_url, json=request)
            result = response.json()
            
            if "result" in result and "message_id" in result.get("result", {}):
                self.results.append({"test": "JSON-RPC message/send", "passed": True, "note": "Protocol 2.0"})
            else:
                self.results.append({"test": "JSON-RPC message/send", "passed": False, "note": "Invalid response format"})
        except Exception as e:
            self.results.append({"test": "JSON-RPC message/send", "passed": False, "note": str(e)})
    
    def test_task_discovery(self):
        """Test A2A task discovery endpoint."""
        try:
            request = {
                "type": "discovery",
                "taskId": f"task_{datetime.now().timestamp()}",
                "parameters": {
                    "query": "sports audiences",
                    "max_results": 5
                }
            }
            
            response = requests.post(f"{self.base_url}/a2a/task", json=request)
            result = response.json()
            
            if "status" in result and "message" in result.get("status", {}):
                self.results.append({"test": "Task Discovery", "passed": True, "note": "/a2a/task"})
            else:
                self.results.append({"test": "Task Discovery", "passed": False, "note": "Invalid task response"})
        except Exception as e:
            self.results.append({"test": "Task Discovery", "passed": False, "note": str(e)})
    
    def test_task_activation(self):
        """Test A2A task activation endpoint."""
        try:
            request = {
                "type": "activation",
                "taskId": f"task_{datetime.now().timestamp()}",
                "parameters": {
                    "signal_id": "test_signal",
                    "platform": "test-platform"
                }
            }
            
            response = requests.post(f"{self.base_url}/a2a/task", json=request)
            result = response.json()
            
            # Should return a task response (even if it fails due to invalid signal)
            if "status" in result:
                self.results.append({"test": "Task Activation", "passed": True, "note": "/a2a/task"})
            else:
                self.results.append({"test": "Task Activation", "passed": False, "note": "Invalid response"})
        except Exception as e:
            self.results.append({"test": "Task Activation", "passed": False, "note": str(e)})
    
    def test_contextual_queries(self):
        """Test contextual query handling."""
        try:
            # First query
            response1 = requests.post(f"{self.base_url}/a2a/task", json={
                "type": "discovery",
                "parameters": {"query": "sports audiences"}
            })
            result1 = response1.json()
            context_id = result1.get("contextId")
            
            # Contextual follow-up
            response2 = requests.post(f"{self.base_url}/a2a/task", json={
                "type": "discovery",
                "contextId": context_id or "test_context",
                "parameters": {"query": "tell me about the signal for sports"}
            })
            result2 = response2.json()
            
            # Check if it's a contextual response
            metadata = result2.get("metadata", {})
            if metadata.get("response_type") in ["signal_details", "contextual_explanation"]:
                self.results.append({"test": "Contextual Queries", "passed": True, "note": "Context preserved"})
            else:
                self.results.append({"test": "Contextual Queries", "passed": False, "note": "Context not handled"})
        except Exception as e:
            self.results.append({"test": "Contextual Queries", "passed": False, "note": str(e)})
    
    def test_cors_headers(self):
        """Test CORS headers for web compatibility."""
        try:
            # Test with a GET request as some servers don't handle OPTIONS
            response = requests.get(f"{self.base_url}/agent-card")
            headers = response.headers
            
            # Check for CORS headers
            has_cors = "Access-Control-Allow-Origin" in headers
            
            if has_cors:
                self.results.append({"test": "CORS Headers", "passed": True, "note": "Web compatible"})
            else:
                self.results.append({"test": "CORS Headers", "passed": False, "note": "No CORS headers"})
        except Exception as e:
            self.results.append({"test": "CORS Headers", "passed": False, "note": str(e)})
    
    def test_error_handling(self):
        """Test error handling with invalid requests."""
        try:
            request = {
                "type": "unknown_task_type",
                "parameters": {}
            }
            
            response = requests.post(f"{self.base_url}/a2a/task", json=request)
            result = response.json()
            
            # Should return proper error structure
            if "status" in result and result.get("status", {}).get("state") == "failed":
                self.results.append({"test": "Error Handling", "passed": True, "note": "Graceful failures"})
            else:
                self.results.append({"test": "Error Handling", "passed": False, "note": "No error structure"})
        except Exception as e:
            self.results.append({"test": "Error Handling", "passed": False, "note": str(e)})
    
    def display_results(self):
        """Display test results in a table."""
        table = Table(title="Test Results")
        table.add_column("Test", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Notes", style="dim")
        
        for result in self.results:
            status = "[green]✓ PASS[/green]" if result["passed"] else "[red]✗ FAIL[/red]"
            table.add_row(result["test"], status, result["note"])
        
        console.print("\n")
        console.print(table)
        
        # Summary
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        
        if passed == total:
            console.print(f"\n[bold green]✅ All {total} tests passed![/bold green]")
        else:
            console.print(f"\n[bold yellow]⚠️  {passed}/{total} tests passed[/bold yellow]")


def main():
    """Run the test suite."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test A2A Protocol compliance")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL to test")
    parser.add_argument("--deployed", action="store_true", help="Test deployed version on Fly.io")
    args = parser.parse_args()
    
    if args.deployed:
        url = "https://audience-agent.fly.dev"
        console.print(f"[yellow]Testing deployed version at {url}[/yellow]")
    else:
        url = args.url
    
    tester = A2AProtocolTester(url)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()