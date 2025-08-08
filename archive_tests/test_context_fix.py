#!/usr/bin/env python3
"""Test that context_id is properly preserved."""

import requests
import json
import time
from rich.console import Console
from rich.panel import Panel

console = Console()

def test_context_preservation():
    """Test context preservation for 'can you tell me about the custom segments?' query."""
    base_url = "http://localhost:8000"
    
    console.print(Panel(
        "Testing Context ID Preservation Fix",
        title="🔧 Context Fix Test",
        border_style="bold cyan"
    ))
    
    # 1. Initial query
    console.print("\n[bold]1. Initial Query:[/bold] 'I want sports audiences'")
    response1 = requests.post(f"{base_url}/a2a/task", json={
        "type": "discovery",
        "parameters": {
            "query": "I want sports audiences"
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
                text = text_part.get("text", "")
                console.print(Panel(text, border_style="green"))
                # Check for custom segments mention
                if "custom segment" in text.lower():
                    console.print("[green]✓ Custom segments mentioned[/green]")
        
        console.print(f"[bold]Context ID: {ctx1}[/bold]")
        
        # 2. Follow-up query about custom segments
        console.print("\n[bold]2. Follow-up Query:[/bold] 'can you tell me about the custom segments?'")
        response2 = requests.post(f"{base_url}/a2a/task", json={
            "type": "discovery",
            "contextId": ctx1,  # Pass the context from first query
            "parameters": {
                "query": "can you tell me about the custom segments?"
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
            
            console.print(f"[bold]Context ID: {ctx2}[/bold]")
            
            # Check metadata
            metadata = result2.get("metadata", {})
            response_type = metadata.get("response_type")
            original_query = metadata.get("original_query")
            
            # Verify context preservation
            console.print("\n[bold]Analysis:[/bold]")
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
                
                # Check if it's actually about custom segments
                if parts2:
                    text_part = next((p for p in parts2 if p.get("kind") == "text"), None)
                    if text_part:
                        text = text_part.get("text", "")
                        if "custom" in text.lower() and ("segment" in text.lower() or "proposal" in text.lower()):
                            console.print("[green]✅ Response is about custom segments[/green]")
                        else:
                            console.print("[yellow]⚠️  Response doesn't mention custom segments[/yellow]")
            else:
                console.print("[red]❌ Not detected as contextual[/red]")
                console.print("[dim]Performed new search instead of using context[/dim]")
            
            # Summary
            console.print("\n" + "="*50)
            if ctx1 == ctx2 and response_type == "contextual_response":
                console.print("[bold green]✨ Context handling is working correctly![/bold green]")
            else:
                console.print("[bold yellow]⚠️  Context handling needs improvement[/bold yellow]")

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
        test_context_preservation()
    finally:
        # Stop server
        console.print("\n[yellow]Stopping server...[/yellow]")
        server_process.terminate()
        server_process.wait(timeout=5)

if __name__ == "__main__":
    main()