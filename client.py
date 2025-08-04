#!/usr/bin/env python3
"""Interactive client for testing the Signals Activation Protocol."""

import asyncio
import json
import sys
from typing import Dict, Any
from fastmcp.client import Client
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from schemas import *

console = Console()

def print_banner():
    """Print the client banner."""
    console.print(Panel(
        "[bold cyan]🎯 Signals Activation Protocol Client[/bold cyan]\n"
        "Interactive client for testing signal discovery and activation",
        border_style="blue"
    ))

def print_help():
    """Print available commands."""
    console.print("\n[bold]Available Commands:[/bold]")
    
    commands = Table()
    commands.add_column("Command", style="cyan", width=20)
    commands.add_column("Description", style="white")
    
    commands.add_row("discover", "Discover signals with natural language")
    commands.add_row("activate", "Activate a signal on a platform (shows current status)")
    commands.add_row("status", "Check signal status (redirects to activate)")
    commands.add_row("help", "Show this help message")
    commands.add_row("quit", "Exit the client")
    
    console.print(commands)

async def discover_signals(client: Client):
    """Interactive signal discovery."""
    console.print("\n[bold blue]🔍 Signal Discovery[/bold blue]")
    
    # Get signal specification
    signal_spec = Prompt.ask("Describe the signals you're looking for")
    
    # Get platforms
    console.print("\nSelect platforms:")
    console.print("1. Specific platforms")
    console.print("2. All platforms")
    
    platform_choice = Prompt.ask("Choice", choices=["1", "2"], default="2")
    
    if platform_choice == "1":
        available_platforms = [
            "the-trade-desk", "index-exchange", "openx", 
            "pubmatic", "google-dv360", "amazon-dsp"
        ]
        console.print(f"\nAvailable platforms: {', '.join(available_platforms)}")
        platform_input = Prompt.ask("Enter platforms (comma-separated)")
        platforms = [{"platform": p.strip()} for p in platform_input.split(",")]
    else:
        platforms = "all"
    
    # Get filters
    max_cpm = Prompt.ask("Maximum CPM (optional)", default="")
    data_provider = Prompt.ask("Data provider filter (optional)", default="")
    max_results = Prompt.ask("Number of results", default="5")
    
    # Build request
    try:
        max_results_int = int(max_results)
    except ValueError:
        max_results_int = 5
        console.print("[yellow]Invalid number, using default of 5[/yellow]")
    
    request_data = {
        "signal_spec": signal_spec,
        "deliver_to": {
            "platforms": platforms,
            "countries": ["US"]
        },
        "max_results": max_results_int
    }
    
    filters = {}
    if max_cpm:
        try:
            filters["max_cpm"] = float(max_cpm)
        except ValueError:
            console.print("[red]Invalid CPM value, ignoring[/red]")
    
    if data_provider:
        filters["data_providers"] = [data_provider]
    
    if filters:
        request_data["filters"] = filters
    
    # Make request via MCP
    try:
        console.print("\n[dim]Searching for signals...[/dim]")
        result = await client.call_tool("get_signals", request_data)
        # Extract the actual response data - use structured_content which is already a dict
        if hasattr(result, 'structured_content') and result.structured_content:
            response = result.structured_content
        elif hasattr(result, 'data') and result.data:
            response = result.data.model_dump()
        else:
            # Fallback - shouldn't happen
            response = {"signals": [], "custom_segment_proposals": []}
        
        if not response.get("signals"):
            console.print("[yellow]No signals found matching your criteria[/yellow]")
            return
        
        # Display results in an attractive table format
        console.print(f"\n[bold green]🎯 Found {len(response['signals'])} signals[/bold green]")
        
        # Create main results table
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("#", style="dim", width=3)
        table.add_column("Signal", style="bold", min_width=20)
        table.add_column("Provider", style="blue", width=12)
        table.add_column("Coverage", justify="right", width=8)
        table.add_column("CPM", justify="right", width=8)
        table.add_column("Status", width=12)
        
        for i, signal in enumerate(response["signals"], 1):
            # Determine status from deployments
            live_count = sum(1 for dep in signal["deployments"] if dep["is_live"])
            total_count = len(signal["deployments"])
            
            if live_count == total_count:
                status = "🟢 All Live"
            elif live_count > 0:
                status = f"🟡 {live_count}/{total_count} Live"
            else:
                status = "⚪ Needs Setup"
            
            # Format pricing
            pricing = signal["pricing"]
            # Check if we have pricing data
            if signal.get("has_pricing_data") is False:
                cpm_str = "Unknown"
            elif "cpm" in pricing and pricing["cpm"] is not None:
                if pricing["cpm"] == 0:
                    cpm_str = "Free"
                else:
                    cpm_str = f"${pricing['cpm']:.2f}"
            elif pricing.get("revenue_share_percentage"):
                cpm_str = f"{pricing['revenue_share_percentage']:.1f}%"
            else:
                cpm_str = "Unknown"
            
            table.add_row(
                str(i),
                signal['name'][:40] + "..." if len(signal['name']) > 40 else signal['name'],
                signal['data_provider'],
                "Unknown" if signal.get('has_coverage_data') is False else f"{signal['coverage_percentage']:.1f}%",
                cpm_str,
                status
            )
        
        console.print(table)
        
        # Show detailed match reasons
        if any(sig.get("match_reason") for sig in response["signals"]):
            console.print("\n[bold yellow]🧠 AI Match Explanations[/bold yellow]")
            for i, signal in enumerate(response["signals"], 1):
                if signal.get("match_reason"):
                    console.print(f"[dim]{i}.[/dim] [bold]{signal['name']}[/bold]")
                    console.print(f"   [italic]{signal['match_reason']}[/italic]\n")
        
        # Show custom segment proposals if available
        if response.get("custom_segment_proposals"):
            console.print(f"\n[bold yellow]💡 Custom Segment Proposals[/bold yellow]")
            console.print("[dim]AI-suggested segments that could be created for better targeting:[/dim]\n")
            
            # Create proposals table
            proposals_table = Table(show_header=True, header_style="bold yellow", box=None)
            proposals_table.add_column("Proposed Segment", style="bold", min_width=25)
            proposals_table.add_column("Coverage", justify="right", width=10)
            proposals_table.add_column("Est. CPM", justify="right", width=10)
            proposals_table.add_column("Rationale", style="dim", min_width=30)
            
            for proposal in response["custom_segment_proposals"]:
                proposals_table.add_row(
                    proposal['proposed_name'],
                    f"{proposal['estimated_coverage_percentage']:.1f}%",
                    f"${proposal['estimated_cpm']:.2f}",
                    proposal['creation_rationale'][:60] + "..." if len(proposal['creation_rationale']) > 60 else proposal['creation_rationale']
                )
            
            console.print(proposals_table)
            
            # Show IDs for activation
            console.print("\n[dim]To activate a custom segment, use the activate command with these IDs:[/dim]")
            for proposal in response["custom_segment_proposals"]:
                console.print(f"  [cyan]{proposal['custom_segment_id']}[/cyan] - {proposal['proposed_name']}")
        
        return response["signals"]
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return None

async def activate_signal(client: Client):
    """Interactive signal activation."""
    console.print("\n[bold blue]🚀 Signal Activation[/bold blue]")
    
    segment_id = Prompt.ask("Signal segment ID")
    platform = Prompt.ask("Platform")
    account = Prompt.ask("Account (optional)", default="")
    principal_id = Prompt.ask("Principal ID (optional)", default="")
    
    request_data = {
        "signals_agent_segment_id": segment_id,
        "platform": platform
    }
    
    if account:
        request_data["account"] = account
    
    if principal_id:
        request_data["principal_id"] = principal_id
    
    try:
        console.print("\n[dim]Activating signal...[/dim]")
        response = await client.call_tool("activate_signal", request_data)
        
        # Display status based on response
        status_emoji = {
            "deployed": "🟢",
            "activating": "🟡", 
            "failed": "🔴"
        }
        
        emoji = status_emoji.get(response.get('status', 'activating'), '🟡')
        status = response.get('status', 'activating').upper()
        
        if response.get('status') == 'deployed':
            console.print(f"[bold green]{emoji} Signal already deployed![/bold green]")
            if response.get('deployed_at'):
                console.print(f"Deployed: {response['deployed_at']}")
        elif response.get('status') == 'activating':
            console.print(f"[bold yellow]{emoji} Activation initiated![/bold yellow]")
            console.print(f"Estimated Duration: {response['estimated_activation_duration_minutes']} minutes")
        else:
            console.print(f"[bold red]{emoji} Activation failed![/bold red]")
            if response.get('error_message'):
                console.print(f"Error: {response['error_message']}")
        
        console.print(f"Platform Segment ID: {response['decisioning_platform_segment_id']}")
        
        return response
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return None

async def check_status(client: Client):
    """Check signal status by re-activating (which now returns current status)."""
    console.print("\n[bold blue]📊 Status Check[/bold blue]")
    console.print("[dim]Note: Status check is now integrated into signal activation[/dim]\n")
    
    # Just call activate_signal which will return the current status
    await activate_signal(client)

async def main():
    """Main client loop."""
    print_banner()
    print_help()
    
    client = Client("main.py")
    
    async with client:
        while True:
            try:
                command = Prompt.ask("\n[bold]Enter command[/bold]", default="discover").lower()
                
                if command in ["quit", "exit", "q"]:
                    console.print("\n[dim]Goodbye! 👋[/dim]")
                    break
                elif command in ["help", "h"]:
                    print_help()
                elif command in ["discover", "d"]:
                    await discover_signals(client)
                elif command in ["activate", "a"]:
                    await activate_signal(client)
                elif command in ["status", "s"]:
                    await check_status(client)
                else:
                    console.print(f"[red]Unknown command: {command}[/red]")
                    print_help()
            
            except KeyboardInterrupt:
                console.print("\n\n[dim]Goodbye! 👋[/dim]")
                break
            except Exception as e:
                console.print(f"[red]Unexpected error: {e}[/red]")

async def quick_prompt():
    """Quick prompt mode for one-off queries."""
    max_results = 5
    principal_id = None
    signal_spec = ""
    
    # Parse command line arguments
    i = 2
    args_to_skip = []
    
    while i < len(sys.argv):
        if sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
            max_results = int(sys.argv[i + 1])
            args_to_skip.extend([i, i + 1])
            i += 2
        elif sys.argv[i] == "--principal" and i + 1 < len(sys.argv):
            principal_id = sys.argv[i + 1]
            args_to_skip.extend([i, i + 1])
            i += 2
        else:
            i += 1
    
    # Build signal_spec from remaining arguments
    signal_parts = []
    for i in range(2, len(sys.argv)):
        if i not in args_to_skip:
            signal_parts.append(sys.argv[i])
    
    signal_spec = " ".join(signal_parts)
    
    if not signal_spec:
        signal_spec = Prompt.ask("Describe the signals you're looking for")
    
    request_data = {
        "signal_spec": signal_spec,
        "deliver_to": {
            "platforms": "all",
            "countries": ["US"]
        },
        "max_results": max_results
    }
    
    if principal_id:
        request_data["principal_id"] = principal_id
    
    client = Client("main.py")
    async with client:
        try:
            console.print(f"\n[bold cyan]🔍 Searching for: {signal_spec}[/bold cyan]")
            principal_note = f" (Principal: {principal_id})" if principal_id else " (Public access)"
            console.print(f"[dim]Limiting to top {max_results} results{principal_note}[/dim]\n")
            
            result = await client.call_tool("get_signals", request_data)
            # Extract the actual response data - use structured_content which is already a dict
            if hasattr(result, 'structured_content') and result.structured_content:
                response = result.structured_content
            elif hasattr(result, 'data') and result.data:
                response = result.data.model_dump()
            else:
                # Fallback - shouldn't happen
                response = {"signals": [], "custom_segment_proposals": []}
            
            if not response.get("signals"):
                console.print("[yellow]No signals found matching your criteria[/yellow]")
                return
            
            # Display results using the same attractive format as interactive mode
            console.print(f"[bold green]🎯 Found {len(response['signals'])} signals[/bold green]")
            
            # Create main results table
            table = Table(show_header=True, header_style="bold cyan", box=None)
            table.add_column("#", style="dim", width=3)
            table.add_column("Audience", style="bold", min_width=25)
            table.add_column("Provider", style="blue", width=12)
            table.add_column("Coverage", justify="right", width=8)
            table.add_column("CPM", justify="right", width=8)
            table.add_column("Status", width=12)
            
            for i, signal in enumerate(response["signals"], 1):
                # Determine status from deployments
                live_count = sum(1 for dep in signal["deployments"] if dep["is_live"])
                total_count = len(signal["deployments"])
                
                if live_count == total_count:
                    status = "🟢 All Live"
                elif live_count > 0:
                    status = f"🟡 {live_count}/{total_count} Live"
                else:
                    status = "⚪ Needs Setup"
                
                # Format pricing
                pricing = signal["pricing"]
                # Check if we have pricing data
                if signal.get("has_pricing_data") is False:
                    cpm_str = "Unknown"
                elif pricing.get("cpm"):
                    cpm_str = f"${pricing['cpm']:.2f}"
                elif pricing.get("revenue_share_percentage"):
                    cpm_str = f"{pricing['revenue_share_percentage']:.1f}%"
                else:
                    cpm_str = "Unknown"
                
                table.add_row(
                    str(i),
                    signal['name'][:35] + "..." if len(signal['name']) > 35 else signal['name'],
                    signal['data_provider'],
                    "Unknown" if signal.get('has_coverage_data') is False else f"{signal['coverage_percentage']:.1f}%",
                    cpm_str,
                    status
                )
            
            console.print(table)
            
            # Show AI match explanations
            if any(sig.get("match_reason") for sig in response["signals"]):
                console.print("\n[bold yellow]🧠 AI Match Explanations[/bold yellow]")
                for i, signal in enumerate(response["signals"], 1):
                    if audience.get("match_reason"):
                        console.print(f"[dim]{i}.[/dim] [bold]{audience['name']}[/bold]")
                        console.print(f"   [italic]{audience['match_reason']}[/italic]\n")
            
            # Show custom segment proposals
            if response.get("custom_segment_proposals"):
                console.print(f"\n[bold yellow]💡 Custom Segment Proposals[/bold yellow]")
                console.print("[dim]AI-suggested segments that could be created:[/dim]\n")
                
                for i, proposal in enumerate(response["custom_segment_proposals"], 1):
                    console.print(f"[bold]{i}. {proposal['proposed_name']}[/bold]")
                    console.print(f"   ID: [cyan]{proposal['custom_segment_id']}[/cyan] (use this ID to activate)")
                    console.print(f"   Coverage: {proposal['estimated_coverage_percentage']:.1f}% | CPM: ${proposal['estimated_cpm']:.2f}")
                    console.print(f"   [italic]{proposal['creation_rationale']}[/italic]\n")
                    
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--prompt":
        asyncio.run(quick_prompt())
    else:
        asyncio.run(main())
