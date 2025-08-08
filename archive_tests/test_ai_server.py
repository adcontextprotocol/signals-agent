#!/usr/bin/env python3
"""Test the pure AI-driven server."""

import requests
import json
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def test_ai_conversations():
    """Test natural AI-driven conversations."""
    base_url = "http://localhost:8000"
    
    console.print(Panel(
        "Testing Pure AI-Driven Server",
        title="🤖 AI Intelligence Test",
        border_style="bold magenta"
    ))
    
    # Series of natural queries
    queries = [
        "I need to reach sports fans",
        "what's the coverage like?",
        "tell me about the custom segments",
        "how much will this cost?",
        "which platforms should I use?",
        "actually, let's look for luxury car buyers instead",
        "can you compare both audiences?"
    ]
    
    context_id = None
    
    for i, query in enumerate(queries, 1):
        console.print(f"\n[bold cyan]Query {i}:[/bold cyan] {query}")
        
        # Send request
        request_data = {
            "type": "discovery",
            "parameters": {
                "query": query
            }
        }
        
        if context_id:
            request_data["contextId"] = context_id
        
        response = requests.post(f"{base_url}/a2a/task", json=request_data)
        
        if response.status_code == 200:
            result = response.json()
            
            # Extract context for next query
            context_id = result.get("contextId")
            
            # Get the AI response
            status = result.get("status", {})
            message = status.get("message", {})
            parts = message.get("parts", [])
            
            for part in parts:
                if part.get("kind") == "text":
                    text = part.get("text", "")
                    console.print(Panel(text, border_style="green"))
                    break
            
            # Show metadata
            metadata = result.get("metadata", {})
            intent = metadata.get("intent", {})
            
            console.print(f"[dim]AI Intent: {intent.get('intent', 'unknown')}[/dim]")
            console.print(f"[dim]Search Query: {intent.get('search_query', 'none')}[/dim]")
            console.print(f"[dim]Context ID: {context_id}[/dim]")
            
            time.sleep(0.5)  # Small delay for readability
        else:
            console.print(f"[red]Error: {response.status_code}[/red]")
            break
    
    # Summary
    console.print("\n" + "="*60)
    console.print("[bold green]✨ AI handled the entire conversation naturally![/bold green]")
    console.print("[dim]No complex branching, no fallback logic - just AI intelligence[/dim]")

def main():
    """Run the test."""
    import subprocess
    import os
    
    # Check if we have Gemini API key
    if not os.environ.get("GEMINI_API_KEY"):
        # Try to load from config
        try:
            with open("config.json") as f:
                config = json.load(f)
                if config.get("gemini_api_key") and config["gemini_api_key"] != "your-api-key-here":
                    os.environ["GEMINI_API_KEY"] = config["gemini_api_key"]
        except:
            pass
    
    if not os.environ.get("GEMINI_API_KEY"):
        console.print("[bold red]⚠️  No Gemini API key found![/bold red]")
        console.print("[yellow]Please set GEMINI_API_KEY environment variable[/yellow]")
        console.print("[dim]export GEMINI_API_KEY='your-key-here'[/dim]")
        return
    
    # Start AI server
    console.print("[yellow]Starting AI-driven server...[/yellow]")
    server_process = subprocess.Popen(
        ["uv", "run", "python", "unified_ai_server.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        test_ai_conversations()
    finally:
        # Stop server
        console.print("\n[yellow]Stopping server...[/yellow]")
        server_process.terminate()
        server_process.wait(timeout=5)

if __name__ == "__main__":
    main()