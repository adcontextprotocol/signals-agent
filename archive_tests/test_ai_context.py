#!/usr/bin/env python3
"""Test AI-powered contextual responses."""

import requests
import json
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def test_ai_contextual_responses():
    """Test various types of contextual queries with AI."""
    base_url = "http://localhost:8000"
    
    console.print(Panel(
        "Testing AI-Powered Contextual Responses",
        title="🤖 Gemini AI Context Tests",
        border_style="bold cyan"
    ))
    
    # 1. Initial discovery
    console.print("\n[bold]1. Initial Discovery:[/bold] 'tech-savvy millennials interested in gaming'")
    response1 = requests.post(f"{base_url}/a2a/task", json={
        "type": "discovery",
        "parameters": {
            "query": "tech-savvy millennials interested in gaming"
        }
    })
    
    result1 = response1.json()
    context_id = result1.get("contextId")
    
    # Show initial response
    status = result1.get("status", {})
    message = status.get("message", {})
    parts = message.get("parts", [])
    if parts:
        text_part = next((p for p in parts if p.get("kind") == "text"), None)
        if text_part:
            console.print(Panel(text_part.get("text", ""), border_style="green"))
    
    console.print(f"[dim]Context ID: {context_id}[/dim]\n")
    
    # Test different types of follow-up queries
    test_queries = [
        {
            "query": "tell me more about the coverage and pricing for these segments",
            "description": "Coverage & Pricing Focus"
        },
        {
            "query": "what custom segments could work better for my campaign?",
            "description": "Custom Segments Focus"
        },
        {
            "query": "which platforms would be best for reaching this audience?",
            "description": "Platform Strategy Focus"
        },
        {
            "query": "explain why these signals match my requirements",
            "description": "Match Reasoning Focus"
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_queries, 2):
        console.print(f"\n[bold]{i}. {test['description']}:[/bold] '{test['query']}'")
        
        response = requests.post(f"{base_url}/a2a/task", json={
            "type": "discovery",
            "contextId": context_id,
            "parameters": {
                "query": test["query"]
            }
        })
        
        if response.status_code == 200:
            result = response.json()
            
            # Extract response
            status = result.get("status", {})
            message = status.get("message", {})
            parts = message.get("parts", [])
            
            if parts:
                text_part = next((p for p in parts if p.get("kind") == "text"), None)
                if text_part:
                    text = text_part.get("text", "")
                    console.print(Panel(text, border_style="cyan"))
                    
                    # Check metadata
                    metadata = result.get("metadata", {})
                    response_type = metadata.get("response_type")
                    focus_area = metadata.get("focus_area")
                    ai_reasoning = metadata.get("ai_reasoning")
                    
                    console.print(f"[dim]Response Type: {response_type}[/dim]")
                    console.print(f"[dim]Focus Area: {focus_area}[/dim]")
                    if ai_reasoning:
                        console.print(f"[dim]AI Reasoning: {ai_reasoning}[/dim]")
                    
                    # Determine if AI was used (not fallback)
                    is_ai_response = (
                        len(text) > 200 and  # AI responses tend to be more detailed
                        "Based on your search for" not in text[:50]  # Fallback starts with this
                    )
                    
                    results.append({
                        "test": test["description"],
                        "ai_used": is_ai_response,
                        "focus_area": focus_area
                    })
                else:
                    results.append({
                        "test": test["description"],
                        "ai_used": False,
                        "focus_area": "unknown"
                    })
        else:
            console.print(f"[red]❌ Request failed: {response.status_code}[/red]")
            results.append({
                "test": test["description"],
                "ai_used": False,
                "focus_area": "error"
            })
        
        time.sleep(1)  # Small delay between requests
    
    # Display results summary
    console.print("\n")
    table = Table(title="AI Context Test Results", show_header=True)
    table.add_column("Test Case", style="cyan")
    table.add_column("AI Used", style="white")
    table.add_column("Focus Area", style="white")
    
    for result in results:
        ai_status = "[green]Yes[/green]" if result["ai_used"] else "[yellow]Fallback[/yellow]"
        table.add_row(result["test"], ai_status, result["focus_area"])
    
    console.print(table)
    
    # Overall assessment
    ai_count = sum(1 for r in results if r["ai_used"])
    total_count = len(results)
    
    if ai_count == total_count:
        console.print(f"\n[bold green]🎉 All {total_count} queries used Gemini AI![/bold green]")
    elif ai_count > 0:
        console.print(f"\n[yellow]⚠️  {ai_count}/{total_count} queries used AI (others used fallback)[/yellow]")
    else:
        console.print(f"\n[yellow]ℹ️  All queries used fallback responses (check Gemini API key)[/yellow]")
        console.print("[dim]To enable AI responses, add your Gemini API key to config.json[/dim]")

def main():
    """Run the AI context tests."""
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
        test_ai_contextual_responses()
    finally:
        # Stop server
        console.print("\n[yellow]Stopping server...[/yellow]")
        server_process.terminate()
        server_process.wait(timeout=5)

if __name__ == "__main__":
    main()