#!/usr/bin/env python3
"""Test environment variable configuration for Gemini API."""

import os
from rich.console import Console
from rich.panel import Panel
from config_loader import load_config

console = Console()

def test_env_config():
    """Test that environment variables override config file."""
    
    console.print(Panel(
        "Testing Environment Variable Configuration",
        title="🔧 Config Test",
        border_style="bold blue"
    ))
    
    # Test 1: Check current config
    console.print("\n[bold]1. Current Configuration:[/bold]")
    config = load_config()
    gemini_key = config.get("gemini_api_key", "not_set")
    
    if gemini_key and gemini_key != "your-api-key-here":
        if gemini_key.startswith("sk-") or len(gemini_key) > 20:
            console.print(f"[green]✅ Gemini API key is configured (key: {gemini_key[:10]}...)[/green]")
        else:
            console.print(f"[yellow]⚠️  Gemini API key found but may be invalid: {gemini_key[:20]}[/yellow]")
    else:
        console.print(f"[yellow]⚠️  No valid Gemini API key found (value: {gemini_key})[/yellow]")
    
    # Test 2: Check environment variable
    console.print("\n[bold]2. Environment Variable Check:[/bold]")
    env_key = os.environ.get("GEMINI_API_KEY")
    
    if env_key:
        console.print(f"[green]✅ GEMINI_API_KEY environment variable is set ({env_key[:10]}...)[/green]")
    else:
        console.print("[yellow]ℹ️  GEMINI_API_KEY environment variable not set[/yellow]")
    
    # Test 3: Test with mock environment variable
    console.print("\n[bold]3. Testing Override Mechanism:[/bold]")
    original_env = os.environ.get("GEMINI_API_KEY")
    
    try:
        # Set a test value
        os.environ["GEMINI_API_KEY"] = "test-key-12345"
        
        # Reload config
        test_config = load_config()
        test_key = test_config.get("gemini_api_key")
        
        if test_key == "test-key-12345":
            console.print("[green]✅ Environment variable override works correctly[/green]")
        else:
            console.print(f"[red]❌ Override failed (got: {test_key})[/red]")
    
    finally:
        # Restore original value
        if original_env:
            os.environ["GEMINI_API_KEY"] = original_env
        else:
            os.environ.pop("GEMINI_API_KEY", None)
    
    # Test 4: Check if AI module can initialize
    console.print("\n[bold]4. Testing AI Module Initialization:[/bold]")
    try:
        import contextual_ai
        console.print("[green]✅ contextual_ai module loaded successfully[/green]")
        
        # Try to use the analyze function
        result = contextual_ai.analyze_query_intent("test query", "test_context")
        if result:
            console.print(f"[green]✅ AI analysis function works (fallback mode: {result.get('reasoning', '')})[/green]")
    except Exception as e:
        console.print(f"[red]❌ AI module error: {e}[/red]")
    
    # Summary
    console.print("\n" + "="*50)
    if env_key or (gemini_key and gemini_key != "your-api-key-here"):
        console.print("[bold green]✨ Configuration is ready for deployment![/bold green]")
        console.print("[dim]The Gemini API key will be loaded from environment on Fly.dev[/dim]")
    else:
        console.print("[bold yellow]⚠️  No API key configured locally[/bold yellow]")
        console.print("[dim]This is fine for local testing - the key will be loaded from Fly.dev secrets in production[/dim]")
        console.print("\n[dim]To test locally with AI, you can:[/dim]")
        console.print("[dim]1. Set GEMINI_API_KEY environment variable[/dim]")
        console.print("[dim]2. Or add your key to config.json[/dim]")

if __name__ == "__main__":
    test_env_config()