#!/usr/bin/env python3
"""Test context ID preservation and platform deduplication."""

import requests
import json
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def test_context_preservation():
    """Test that context ID is preserved throughout conversation."""
    base_url = "http://localhost:8000"
    
    console.print(Panel(
        "Testing Context ID Preservation & Platform Deduplication",
        title="🔄 Context Continuity Test",
        border_style="bold cyan"
    ))
    
    # Track context IDs through conversation
    context_ids = []
    
    # 1. Initial query
    console.print("\n[bold]1. Initial Query:[/bold] 'sports audiences'")
    response1 = requests.post(f"{base_url}/a2a/task", json={
        "type": "discovery",
        "parameters": {
            "query": "sports audiences"
        }
    })
    
    if response1.status_code == 200:
        result1 = response1.json()
        ctx1 = result1.get("contextId")
        context_ids.append(("Initial query", ctx1))
        console.print(f"[green]✓ Context ID: {ctx1}[/green]")
        
        # Check for duplicate platforms
        status = result1.get("status", {})
        message = status.get("message", {})
        parts = message.get("parts", [])
        if parts:
            text_part = next((p for p in parts if p.get("kind") == "text"), None)
            if text_part and text_part.get("text"):
                text = text_part.get("text", "")
                # Check for duplicates in text
                if "the-trade-desk, the-trade-desk" in text or "index-exchange, index-exchange" in text:
                    console.print("[red]⚠️  Duplicate platforms detected in response![/red]")
                else:
                    console.print("[green]✓ No duplicate platforms[/green]")
    
    # 2. Follow-up with context
    console.print("\n[bold]2. Follow-up Query:[/bold] 'tell me more about coverage'")
    response2 = requests.post(f"{base_url}/a2a/task", json={
        "type": "discovery",
        "contextId": ctx1,  # Use the context from first query
        "parameters": {
            "query": "tell me more about coverage"
        }
    })
    
    if response2.status_code == 200:
        result2 = response2.json()
        ctx2 = result2.get("contextId")
        context_ids.append(("Follow-up query", ctx2))
        console.print(f"[green]✓ Context ID: {ctx2}[/green]")
    
    # 3. Another follow-up
    console.print("\n[bold]3. Another Follow-up:[/bold] 'what about pricing?'")
    response3 = requests.post(f"{base_url}/a2a/task", json={
        "type": "discovery",
        "contextId": ctx2,  # Should still be the same
        "parameters": {
            "query": "what about pricing?"
        }
    })
    
    if response3.status_code == 200:
        result3 = response3.json()
        ctx3 = result3.get("contextId")
        context_ids.append(("Second follow-up", ctx3))
        console.print(f"[green]✓ Context ID: {ctx3}[/green]")
    
    # 4. New query WITHOUT context (should get new ID)
    console.print("\n[bold]4. New Query (no context):[/bold] 'luxury car buyers'")
    response4 = requests.post(f"{base_url}/a2a/task", json={
        "type": "discovery",
        "parameters": {
            "query": "luxury car buyers"
        }
    })
    
    if response4.status_code == 200:
        result4 = response4.json()
        ctx4 = result4.get("contextId")
        context_ids.append(("New query (no context)", ctx4))
        console.print(f"[green]✓ Context ID: {ctx4}[/green]")
    
    # Display results
    console.print("\n")
    table = Table(title="Context ID Analysis", show_header=True)
    table.add_column("Query", style="cyan")
    table.add_column("Context ID", style="white")
    table.add_column("Status", style="white")
    
    # Check if context was preserved
    if len(context_ids) >= 3:
        # First three should have same context
        if context_ids[0][1] == context_ids[1][1] == context_ids[2][1]:
            for i in range(3):
                table.add_row(context_ids[i][0], context_ids[i][1][:20] + "...", "[green]✓ Preserved[/green]")
        else:
            for i in range(3):
                status = "[green]✓ Preserved[/green]" if i > 0 and context_ids[i][1] == context_ids[i-1][1] else "[red]✗ Changed[/red]"
                table.add_row(context_ids[i][0], context_ids[i][1][:20] + "..." if context_ids[i][1] else "None", status)
        
        # Fourth should be different
        if len(context_ids) > 3:
            is_different = context_ids[3][1] != context_ids[0][1]
            status = "[green]✓ New context[/green]" if is_different else "[red]✗ Should be new[/red]"
            table.add_row(context_ids[3][0], context_ids[3][1][:20] + "..." if context_ids[3][1] else "None", status)
    
    console.print(table)
    
    # Summary
    if len(context_ids) >= 3 and context_ids[0][1] == context_ids[1][1] == context_ids[2][1]:
        console.print("\n[bold green]✅ Context preservation working correctly![/bold green]")
        console.print("[dim]The same context ID was maintained throughout the conversation.[/dim]")
    else:
        console.print("\n[bold yellow]⚠️  Context preservation issue detected[/bold yellow]")
        console.print("[dim]Context IDs are changing when they should be preserved.[/dim]")

def main():
    """Run the context preservation test."""
    import subprocess
    
    # Start server
    console.print("[yellow]Starting unified server...[/yellow]")
    server_process = subprocess.Popen(
        ["uv", "run", "python", "unified_server.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        test_context_preservation()
    finally:
        # Stop server
        console.print("\n[yellow]Stopping server...[/yellow]")
        server_process.terminate()
        server_process.wait(timeout=5)

if __name__ == "__main__":
    main()