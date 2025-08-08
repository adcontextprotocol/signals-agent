#!/usr/bin/env python3
"""Test custom segment contextual queries."""

import requests
import json
import time
from rich.console import Console
from rich.panel import Panel

console = Console()

def test_custom_segments_context():
    """Test contextual queries about custom segments."""
    base_url = "http://localhost:8000"
    
    console.print(Panel(
        "Testing Custom Segment Contextual Queries",
        title="🎯 Custom Segments Test",
        border_style="bold cyan"
    ))
    
    # Test 1: Query with custom segments
    console.print("\n[bold]Test 1: Query that returns custom segments[/bold]")
    console.print("Query: 'sports fans'")
    
    response1 = requests.post(f"{base_url}/a2a/task", json={
        "type": "discovery",
        "parameters": {
            "query": "sports fans"
        }
    })
    
    if response1.status_code == 200:
        result1 = response1.json()
        context_id = result1.get("contextId")
        
        # Display initial response
        status = result1.get("status", {})
        message = status.get("message", {})
        parts = message.get("parts", [])
        if parts:
            text_part = next((p for p in parts if p.get("kind") == "text"), None)
            if text_part:
                console.print(Panel(text_part.get("text", ""), border_style="green"))
        
        console.print(f"[dim]Context ID: {context_id}[/dim]")
        
        # Follow-up about custom segments
        console.print("\n[bold]Follow-up: 'what are the custom segments'[/bold]")
        
        response2 = requests.post(f"{base_url}/a2a/task", json={
            "type": "discovery",
            "contextId": context_id,
            "parameters": {
                "query": "what are the custom segments"
            }
        })
        
        if response2.status_code == 200:
            result2 = response2.json()
            
            # Display follow-up response
            status2 = result2.get("status", {})
            message2 = status2.get("message", {})
            parts2 = message2.get("parts", [])
            if parts2:
                text_part2 = next((p for p in parts2 if p.get("kind") == "text"), None)
                if text_part2:
                    text = text_part2.get("text", "")
                    console.print(Panel(text, border_style="cyan"))
                    
                    # Check if it's contextual
                    metadata = result2.get("metadata", {})
                    response_type = metadata.get("response_type")
                    
                    if response_type == "contextual_response":
                        if "custom segment" in text.lower():
                            console.print("[green]✅ Contextual response about custom segments![/green]")
                        else:
                            console.print("[yellow]⚠️  Contextual but not about custom segments[/yellow]")
                    else:
                        console.print("[red]❌ Not a contextual response - performed new search[/red]")
    
    # Test 2: Query with NO custom segments
    console.print("\n[bold]Test 2: Query with no signals (should have no custom segments)[/bold]")
    console.print("Query: 'big spenders'")
    
    response3 = requests.post(f"{base_url}/a2a/task", json={
        "type": "discovery",
        "parameters": {
            "query": "big spenders"
        }
    })
    
    if response3.status_code == 200:
        result3 = response3.json()
        context_id2 = result3.get("contextId")
        
        # Display response
        status3 = result3.get("status", {})
        message3 = status3.get("message", {})
        parts3 = message3.get("parts", [])
        if parts3:
            text_part3 = next((p for p in parts3 if p.get("kind") == "text"), None)
            if text_part3:
                console.print(Panel(text_part3.get("text", ""), border_style="yellow"))
        
        console.print(f"[dim]Context ID: {context_id2}[/dim]")
        
        # Follow-up about custom segments when there are none
        console.print("\n[bold]Follow-up: 'what custom segments are available?'[/bold]")
        
        response4 = requests.post(f"{base_url}/a2a/task", json={
            "type": "discovery",
            "contextId": context_id2,
            "parameters": {
                "query": "what custom segments are available?"
            }
        })
        
        if response4.status_code == 200:
            result4 = response4.json()
            
            # Display follow-up response
            status4 = result4.get("status", {})
            message4 = status4.get("message", {})
            parts4 = message4.get("parts", [])
            if parts4:
                text_part4 = next((p for p in parts4 if p.get("kind") == "text"), None)
                if text_part4:
                    text = text_part4.get("text", "")
                    console.print(Panel(text, border_style="cyan"))
                    
                    # Check response
                    metadata = result4.get("metadata", {})
                    response_type = metadata.get("response_type")
                    
                    if response_type == "contextual_response":
                        if "no custom segment" in text.lower() or "broader search" in text.lower():
                            console.print("[green]✅ Correctly explains no custom segments available![/green]")
                        else:
                            console.print("[yellow]⚠️  Contextual but doesn't explain absence of custom segments[/yellow]")
                    else:
                        console.print("[red]❌ Not a contextual response[/red]")

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
        test_custom_segments_context()
    finally:
        # Stop server
        console.print("\n[yellow]Stopping server...[/yellow]")
        server_process.terminate()
        server_process.wait(timeout=5)

if __name__ == "__main__":
    main()