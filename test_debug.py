#!/usr/bin/env python3
"""Debug custom segments in responses."""

import requests
import json
from rich.console import Console

console = Console()

def test_sports_fans():
    """Test sports fans query to see if custom segments are returned."""
    response = requests.post("http://localhost:8000/a2a/task", json={
        "type": "discovery",
        "parameters": {
            "query": "sports fans"
        }
    })
    
    if response.status_code == 200:
        result = response.json()
        
        # Check the data part for custom segments
        status = result.get("status", {})
        message = status.get("message", {})
        parts = message.get("parts", [])
        
        for part in parts:
            if part.get("kind") == "data":
                data = part.get("data", {})
                custom_proposals = data.get("custom_segment_proposals")
                console.print(f"[bold]Custom proposals in data:[/bold] {custom_proposals}")
                
                if custom_proposals:
                    console.print("[green]✅ Custom segments found in response data[/green]")
                    for i, proposal in enumerate(custom_proposals, 1):
                        console.print(f"\n{i}. {proposal.get('name', 'Unknown')}")
                        console.print(f"   - {proposal.get('rationale', '')}")
                else:
                    console.print("[yellow]⚠️  No custom segments in response data[/yellow]")
                break
        
        # Check the text message
        text_part = next((p for p in parts if p.get("kind") == "text"), None)
        if text_part:
            text = text_part.get("text", "")
            console.print(f"\n[bold]Text message:[/bold] {text}")
            
            if "custom segment" in text.lower():
                console.print("[green]✅ Custom segments mentioned in text[/green]")
            else:
                console.print("[yellow]⚠️  Custom segments not mentioned in text[/yellow]")

if __name__ == "__main__":
    import subprocess
    import time
    
    # Start server
    console.print("[yellow]Starting server...[/yellow]")
    server = subprocess.Popen(
        ["uv", "run", "python", "unified_server.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    time.sleep(3)
    
    try:
        test_sports_fans()
    finally:
        server.terminate()
        server.wait(timeout=5)
        console.print("\n[yellow]Server stopped[/yellow]")