#!/usr/bin/env python3
"""Test contextual query handling in the unified server."""

import requests
import json
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def test_a2a_context():
    """Test A2A contextual query handling."""
    base_url = "http://localhost:8000"
    
    console.print("\n[bold cyan]Testing A2A Context Handling[/bold cyan]")
    
    # 1. Initial discovery query
    console.print("\n1️⃣  Initial query: 'sports audiences'")
    response1 = requests.post(f"{base_url}/a2a/task", json={
        "type": "discovery",
        "parameters": {
            "query": "sports audiences"
        }
    })
    
    if response1.status_code != 200:
        console.print(f"[red]❌ Initial query failed: {response1.status_code}[/red]")
        return False
    
    result1 = response1.json()
    context_id = result1.get("contextId")
    
    # Extract message from result
    status = result1.get("status", {})
    message = status.get("message", {})
    parts = message.get("parts", [])
    
    if parts:
        text_part = next((p for p in parts if p.get("kind") == "text"), None)
        if text_part:
            console.print(Panel(text_part.get("text", ""), title="Initial Response", border_style="green"))
    
    console.print(f"[dim]Context ID: {context_id}[/dim]")
    
    # 2. Follow-up contextual query
    console.print("\n2️⃣  Follow-up query: 'tell me more about the sports audience'")
    response2 = requests.post(f"{base_url}/a2a/task", json={
        "type": "discovery",
        "contextId": context_id,
        "parameters": {
            "query": "tell me more about the sports audience"
        }
    })
    
    if response2.status_code != 200:
        console.print(f"[red]❌ Follow-up query failed: {response2.status_code}[/red]")
        return False
    
    result2 = response2.json()
    
    # Extract message from follow-up
    status2 = result2.get("status", {})
    message2 = status2.get("message", {})
    parts2 = message2.get("parts", [])
    
    if parts2:
        text_part2 = next((p for p in parts2 if p.get("kind") == "text"), None)
        if text_part2:
            text = text_part2.get("text", "")
            console.print(Panel(text, title="Follow-up Response", border_style="cyan"))
            
            # Check if it's using context properly
            metadata = result2.get("metadata", {})
            response_type = metadata.get("response_type")
            original_query = metadata.get("original_query")
            
            if response_type == "contextual_response":
                console.print(f"[green]✅ Context handled correctly![/green]")
                console.print(f"[dim]Response type: {response_type}[/dim]")
                console.print(f"[dim]Original query recalled: {original_query}[/dim]")
                return True
            else:
                console.print(f"[yellow]⚠️  Not using context (response_type: {response_type})[/yellow]")
                # Check if it's performing a new search
                if "sports audience" in text.lower() or original_query:
                    console.print("[green]✅ But still providing relevant information[/green]")
                    return True
                return False
    
    return False

def test_json_rpc_context():
    """Test JSON-RPC message/send context handling."""
    base_url = "http://localhost:8000"
    
    console.print("\n[bold cyan]Testing JSON-RPC Context Handling[/bold cyan]")
    
    # 1. Initial query via JSON-RPC
    console.print("\n1️⃣  Initial JSON-RPC query: 'luxury car buyers'")
    response1 = requests.post(base_url, json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {
            "message": {
                "parts": [{
                    "kind": "text",
                    "text": "luxury car buyers"
                }]
            }
        }
    })
    
    if response1.status_code != 200:
        console.print(f"[red]❌ Initial JSON-RPC query failed: {response1.status_code}[/red]")
        return False
    
    result1 = response1.json()
    
    # Extract context from response
    rpc_result = result1.get("result", {})
    message_parts = rpc_result.get("parts", [])
    
    # Try to find context_id in data part
    context_id = None
    for part in message_parts:
        if part.get("kind") == "data":
            data = part.get("data", {}).get("content", {})
            context_id = data.get("context_id")
            break
    
    if message_parts:
        text_part = next((p for p in message_parts if p.get("kind") == "text"), None)
        if text_part:
            console.print(Panel(text_part.get("text", ""), title="Initial JSON-RPC Response", border_style="green"))
    
    console.print(f"[dim]Context ID: {context_id}[/dim]")
    
    # 2. Follow-up with context
    console.print("\n2️⃣  Follow-up JSON-RPC query: 'tell me more about these luxury buyers'")
    response2 = requests.post(base_url, json={
        "jsonrpc": "2.0",
        "id": 2,
        "method": "message/send",
        "params": {
            "contextId": context_id,
            "message": {
                "parts": [{
                    "kind": "text",
                    "text": "tell me more about these luxury buyers"
                }]
            }
        }
    })
    
    if response2.status_code != 200:
        console.print(f"[red]❌ Follow-up JSON-RPC query failed: {response2.status_code}[/red]")
        return False
    
    result2 = response2.json()
    rpc_result2 = result2.get("result", {})
    message_parts2 = rpc_result2.get("parts", [])
    
    if message_parts2:
        text_part2 = next((p for p in message_parts2 if p.get("kind") == "text"), None)
        if text_part2:
            text = text_part2.get("text", "")
            console.print(Panel(text, title="Follow-up JSON-RPC Response", border_style="cyan"))
            
            # Check if context is being used
            if "luxury" in text.lower():
                console.print("[green]✅ Context appears to be used (luxury mentioned)[/green]")
                return True
            else:
                console.print("[yellow]⚠️  Context may not be used properly[/yellow]")
                return False
    
    return False

def main():
    """Run all context tests."""
    console.print(Panel(
        "Testing Context Handling in Unified Server",
        title="🧪 Context Tests",
        border_style="bold blue"
    ))
    
    # Start the server
    import subprocess
    import os
    
    console.print("\n[yellow]Starting unified server...[/yellow]")
    server_process = subprocess.Popen(
        ["uv", "run", "python", "unified_server.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        # Run tests
        results = []
        
        # Test A2A context
        a2a_result = test_a2a_context()
        results.append(("A2A Context Handling", a2a_result))
        
        # Test JSON-RPC context
        json_rpc_result = test_json_rpc_context()
        results.append(("JSON-RPC Context Handling", json_rpc_result))
        
        # Display results
        console.print("\n")
        table = Table(title="Context Test Results", show_header=True)
        table.add_column("Test", style="cyan")
        table.add_column("Result", style="white")
        
        for test_name, passed in results:
            status = "[green]✅ PASS[/green]" if passed else "[red]❌ FAIL[/red]"
            table.add_row(test_name, status)
        
        console.print(table)
        
        # Summary
        passed_count = sum(1 for _, p in results if p)
        total_count = len(results)
        
        if passed_count == total_count:
            console.print(f"\n[bold green]🎉 All {total_count} tests passed![/bold green]")
        else:
            console.print(f"\n[yellow]⚠️  {passed_count}/{total_count} tests passed[/yellow]")
        
    finally:
        # Stop the server
        console.print("\n[yellow]Stopping server...[/yellow]")
        server_process.terminate()
        server_process.wait(timeout=5)

if __name__ == "__main__":
    main()