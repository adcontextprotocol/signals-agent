#!/usr/bin/env python3
"""Comprehensive test suite for the unified MCP/A2A server."""

import json
import time
import requests
import subprocess
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


class UnifiedServerTester:
    """Test harness for unified server."""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.server_process = None
        self.test_results = []
    
    def start_server(self):
        """Start the unified server in background."""
        console.print("[yellow]Starting unified server...[/yellow]")
        self.server_process = subprocess.Popen(
            [sys.executable, "unified_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(3)  # Wait for server to start
        
    def stop_server(self):
        """Stop the server."""
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait()
            console.print("[yellow]Server stopped[/yellow]")
    
    def test_health(self):
        """Test health endpoint."""
        try:
            resp = requests.get(f"{self.base_url}/health")
            resp.raise_for_status()
            data = resp.json()
            
            assert data["status"] == "healthy"
            assert "mcp" in data["protocols"]
            assert "a2a" in data["protocols"]
            
            self.test_results.append(("Health Check", "✅ PASS", "Both protocols available"))
            return True
        except Exception as e:
            self.test_results.append(("Health Check", "❌ FAIL", str(e)))
            return False
    
    def test_a2a_agent_card(self):
        """Test A2A agent card endpoint."""
        try:
            resp = requests.get(f"{self.base_url}/agent-card")
            resp.raise_for_status()
            data = resp.json()
            
            assert data["agentId"] == "signals-activation-agent"
            assert "discovery" in data["capabilities"]
            assert "activation" in data["capabilities"]
            
            self.test_results.append(("A2A Agent Card", "✅ PASS", f"Agent: {data['name']}"))
            return True
        except Exception as e:
            self.test_results.append(("A2A Agent Card", "❌ FAIL", str(e)))
            return False
    
    def test_a2a_discovery(self):
        """Test A2A discovery task."""
        try:
            task = {
                "taskId": "test_a2a_discovery",
                "type": "discovery",
                "parameters": {
                    "query": "luxury car buyers",
                    "max_results": 2
                }
            }
            
            resp = requests.post(f"{self.base_url}/a2a/task", json=task)
            resp.raise_for_status()
            data = resp.json()
            
            assert data["taskId"] == task["taskId"]
            assert data["status"] == "completed"
            assert "parts" in data
            
            # Extract content
            content = data["parts"][0]["content"]
            context_id = content.get("context_id", "N/A")
            signal_count = len(content.get("signals", []))
            
            self.test_results.append((
                "A2A Discovery", 
                "✅ PASS", 
                f"Found {signal_count} signals, Context: {context_id}"
            ))
            return context_id
            
        except Exception as e:
            self.test_results.append(("A2A Discovery", "❌ FAIL", str(e)))
            return None
    
    def test_mcp_tools_list(self):
        """Test MCP tools list."""
        try:
            req = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            }
            
            resp = requests.post(f"{self.base_url}/mcp", json=req)
            resp.raise_for_status()
            data = resp.json()
            
            assert data["jsonrpc"] == "2.0"
            assert "result" in data
            tools = data["result"]["tools"]
            tool_names = [t["name"] for t in tools]
            
            assert "get_signals" in tool_names
            assert "activate_signal" in tool_names
            
            self.test_results.append((
                "MCP Tools List", 
                "✅ PASS", 
                f"Found {len(tools)} tools: {', '.join(tool_names)}"
            ))
            return True
            
        except Exception as e:
            self.test_results.append(("MCP Tools List", "❌ FAIL", str(e)))
            return False
    
    def test_mcp_discovery(self):
        """Test MCP discovery."""
        try:
            req = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "get_signals",
                    "arguments": {
                        "signal_spec": "luxury car buyers",
                        "deliver_to": {"platforms": "all"},
                        "max_results": 2
                    }
                },
                "id": 2
            }
            
            resp = requests.post(f"{self.base_url}/mcp", json=req)
            resp.raise_for_status()
            data = resp.json()
            
            assert data["jsonrpc"] == "2.0"
            assert "result" in data
            
            result = data["result"]
            context_id = result.get("context_id", "N/A")
            signal_count = len(result.get("signals", []))
            
            self.test_results.append((
                "MCP Discovery",
                "✅ PASS",
                f"Found {signal_count} signals, Context: {context_id}"
            ))
            return context_id
            
        except Exception as e:
            self.test_results.append(("MCP Discovery", "❌ FAIL", str(e)))
            return None
    
    def test_jsonrpc_message_send(self):
        """Test JSON-RPC message/send format (A2A Inspector style)."""
        try:
            req = {
                "jsonrpc": "2.0",
                "method": "message/send", 
                "params": {
                    "message": {
                        "parts": [{
                            "kind": "text",
                            "text": "luxury car buyers"
                        }]
                    }
                },
                "id": "msg_test_123"
            }
            
            resp = requests.post(f"{self.base_url}/", json=req)
            resp.raise_for_status()
            data = resp.json()
            
            # Check JSON-RPC wrapper
            assert data["jsonrpc"] == "2.0"
            assert data["id"] == req["id"]
            assert "result" in data
            
            # Check Message format (not Task format)
            result = data["result"]
            assert result["kind"] == "message"
            assert "messageId" in result
            assert "parts" in result  
            assert "role" in result
            assert result["role"] == "assistant"
            
            # Verify content structure
            parts = result["parts"]
            assert len(parts) > 0
            content = parts[0].get("content", {})
            signal_count = len(content.get("signals", []))
            
            self.test_results.append((
                "JSON-RPC message/send",
                "✅ PASS", 
                f"Message format with {signal_count} signals"
            ))
            return True
            
        except Exception as e:
            self.test_results.append(("JSON-RPC message/send", "❌ FAIL", str(e)))
            return False

    def test_cross_protocol_activation(self, discovery_context_id):
        """Test activation with context from different protocol."""
        try:
            # Use A2A to activate with MCP's context
            task = {
                "taskId": "test_cross_activation",
                "type": "activation",
                "parameters": {
                    "signal_id": "sports_enthusiasts_public",
                    "platform": "the-trade-desk",
                    "context_id": discovery_context_id
                }
            }
            
            resp = requests.post(f"{self.base_url}/a2a/task", json=task)
            resp.raise_for_status()
            data = resp.json()
            
            assert data["status"] in ["completed", "in_progress"]
            
            # Check if context was linked
            content = data["parts"][0]["content"]
            linked_context = content.get("context_id", "N/A")
            
            self.test_results.append((
                "Cross-Protocol Activation",
                "✅ PASS",
                f"Activated with context from other protocol: {linked_context}"
            ))
            return True
            
        except Exception as e:
            self.test_results.append(("Cross-Protocol Activation", "❌ FAIL", str(e)))
            return False
    
    def display_results(self):
        """Display test results in a nice table."""
        console.print("\n")
        console.print(Panel("[bold]Unified Server Test Results[/bold]", style="cyan"))
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Test", style="cyan", width=25)
        table.add_column("Result", width=10)
        table.add_column("Details", style="dim")
        
        for test_name, result, details in self.test_results:
            table.add_row(test_name, result, details)
        
        console.print(table)
        
        # Summary
        passed = sum(1 for _, r, _ in self.test_results if "PASS" in r)
        total = len(self.test_results)
        
        if passed == total:
            console.print(f"\n[bold green]✅ All {total} tests passed![/bold green]")
        else:
            console.print(f"\n[bold yellow]⚠️  {passed}/{total} tests passed[/bold yellow]")
    
    def run_all_tests(self):
        """Run all tests in sequence."""
        console.print(Panel(
            "[bold cyan]🧪 Testing Unified MCP/A2A Server[/bold cyan]\n"
            "This will test both protocols on a single server instance",
            border_style="blue"
        ))
        
        try:
            # Start server
            self.start_server()
            
            # Run tests
            self.test_health()
            self.test_a2a_agent_card()
            
            # Discovery tests - save context IDs
            a2a_context = self.test_a2a_discovery()
            mcp_context = self.test_mcp_discovery()
            
            # JSON-RPC message/send test
            self.test_jsonrpc_message_send()
            
            # MCP tools
            self.test_mcp_tools_list()
            
            # Cross-protocol test
            if mcp_context:
                self.test_cross_protocol_activation(mcp_context)
            
            # Display results
            self.display_results()
            
        finally:
            self.stop_server()


def main():
    """Run the test suite."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Unified MCP/A2A Server")
    parser.add_argument("--url", default="http://localhost:8000", help="Server URL")
    parser.add_argument("--no-start", action="store_true", help="Don't start server (already running)")
    
    args = parser.parse_args()
    
    tester = UnifiedServerTester(args.url)
    
    if args.no_start:
        # Server already running
        tester.server_process = None
        console.print("[dim]Using existing server at {}[/dim]".format(args.url))
    
    tester.run_all_tests()


if __name__ == "__main__":
    main()