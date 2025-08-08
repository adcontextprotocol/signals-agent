#!/usr/bin/env python3
"""Test 'what is the audience like?' contextual query."""

import requests
import json
import time
from rich.console import Console
from rich.panel import Panel

console = Console()

def test_audience_like():
    """Test contextual query detection for 'what is the audience like?'."""
    base_url = "http://localhost:8000"
    
    console.print(Panel(
        "Testing 'what is the audience like?' Context Preservation",
        title="🎯 Context Detection Test",
        border_style="bold cyan"
    ))
    
    # 1. Initial query
    console.print("\n[bold]1. Initial Query:[/bold] 'sports fans'")
    response1 = requests.post(f"{base_url}/a2a/task", json={
        "type": "discovery",
        "parameters": {
            "query": "sports fans"
        }
    })
    
    if response1.status_code == 200:
        result1 = response1.json()
        ctx1 = result1.get("contextId")
        
        # Display initial response
        status = result1.get("status", {})
        message = status.get("message", {})
        parts = message.get("parts", [])
        if parts:
            text_part = next((p for p in parts if p.get("kind") == "text"), None)
            if text_part:
                console.print(Panel(text_part.get("text", ""), border_style="green"))
        
        console.print(f"[green]✓ Context ID: {ctx1}[/green]")
        
        # 2. Follow-up with "what is the audience like?"
        console.print("\n[bold]2. Follow-up Query:[/bold] 'what is the audience like?'")
        response2 = requests.post(f"{base_url}/a2a/task", json={
            "type": "discovery",
            "contextId": ctx1,
            "parameters": {
                "query": "what is the audience like?"
            }
        })
        
        if response2.status_code == 200:
            result2 = response2.json()
            ctx2 = result2.get("contextId")
            
            # Display follow-up response
            status2 = result2.get("status", {})
            message2 = status2.get("message", {})
            parts2 = message2.get("parts", [])
            if parts2:
                text_part2 = next((p for p in parts2 if p.get("kind") == "text"), None)
                if text_part2:
                    text = text_part2.get("text", "")
                    console.print(Panel(text, border_style="cyan"))
            
            console.print(f"[green]✓ Context ID: {ctx2}[/green]")
            
            # Check metadata
            metadata = result2.get("metadata", {})
            response_type = metadata.get("response_type")
            original_query = metadata.get("original_query")
            
            # Verify context preservation
            if ctx1 == ctx2:
                console.print("[bold green]✅ SUCCESS: Context ID preserved![/bold green]")
                console.print(f"[dim]Same context maintained: {ctx1}[/dim]")
            else:
                console.print("[bold red]❌ FAILED: Context ID changed![/bold red]")
                console.print(f"[dim]Original: {ctx1}[/dim]")
                console.print(f"[dim]New: {ctx2}[/dim]")
            
            if response_type == "contextual_response":
                console.print("[green]✅ Detected as contextual response[/green]")
                if original_query:
                    console.print(f"[dim]Original query recalled: {original_query}[/dim]")
            else:
                console.print("[red]❌ Not detected as contextual[/red]")
                console.print("[dim]Performed new search instead of using context[/dim]")
        
        # 3. Try more variations
        test_queries = [
            "who are these audiences?",
            "how many people does this reach?",
            "what platforms work best?",
            "tell me about coverage"
        ]
        
        console.print("\n[bold]Testing more contextual queries:[/bold]")
        all_preserved = True
        
        for query in test_queries:
            response = requests.post(f"{base_url}/a2a/task", json={
                "type": "discovery",
                "contextId": ctx1,
                "parameters": {
                    "query": query
                }
            })
            
            if response.status_code == 200:
                result = response.json()
                ctx_new = result.get("contextId")
                metadata = result.get("metadata", {})
                response_type = metadata.get("response_type")
                
                preserved = ctx_new == ctx1
                contextual = response_type == "contextual_response"
                
                if preserved and contextual:
                    console.print(f"  [green]✓[/green] '{query}' - Context preserved & contextual")
                elif preserved:
                    console.print(f"  [yellow]⚠[/yellow] '{query}' - Context preserved but not contextual")
                else:
                    console.print(f"  [red]✗[/red] '{query}' - Context changed (new: {ctx_new[:20]}...)")
                    all_preserved = False
            
            time.sleep(0.5)  # Small delay between requests
        
        # Summary
        console.print("\n" + "="*50)
        if all_preserved:
            console.print("[bold green]✨ All queries preserved context correctly![/bold green]")
        else:
            console.print("[bold yellow]⚠️  Some queries didn't preserve context[/bold yellow]")

def main():
    """Run the test."""
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
        test_audience_like()
    finally:
        # Stop server
        console.print("\n[yellow]Stopping server...[/yellow]")
        server_process.terminate()
        server_process.wait(timeout=5)

if __name__ == "__main__":
    main()