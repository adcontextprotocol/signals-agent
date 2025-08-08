#!/usr/bin/env python3
"""Test client for A2A protocol implementation."""

import json
import requests
from typing import Optional
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import argparse

console = Console()


def test_agent_card(base_url: str = "http://localhost:8080"):
    """Test fetching the agent card."""
    console.print("\n[bold blue]Testing Agent Card Retrieval[/bold blue]")
    
    try:
        response = requests.get(f"{base_url}/agent-card")
        response.raise_for_status()
        
        agent_card = response.json()
        
        console.print(Panel(
            f"[bold green]✓ Agent Card Retrieved[/bold green]\n\n"
            f"Agent ID: {agent_card.get('agentId', 'N/A')}\n"
            f"Name: {agent_card.get('name', 'N/A')}\n"
            f"Description: {agent_card.get('description', 'N/A')}\n"
            f"Version: {agent_card.get('version', 'N/A')}\n"
            f"Protocols: {', '.join(agent_card.get('protocols', []))}\n"
            f"Endpoint: {agent_card.get('endpoint', 'N/A')}",
            title="Agent Card",
            border_style="green"
        ))
        
        # Display capabilities
        if 'capabilities' in agent_card:
            console.print("\n[bold]Capabilities:[/bold]")
            for cap_name, cap_info in agent_card['capabilities'].items():
                console.print(f"  • {cap_name}: {cap_info.get('description', 'N/A')}")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Failed to retrieve agent card: {e}[/red]")
        return False


def test_discovery(base_url: str = "http://localhost:8080", query: str = "sports fans"):
    """Test discovery task."""
    console.print(f"\n[bold blue]Testing Discovery Task[/bold blue]")
    console.print(f"Query: {query}")
    
    task = {
        "taskId": f"test_discovery_{int(datetime.now().timestamp())}",
        "type": "discovery",
        "parameters": {
            "query": query,
            "deliver_to": {
                "platforms": "all",
                "countries": ["US"]
            },
            "max_results": 5
        }
    }
    
    try:
        response = requests.post(f"{base_url}/a2a/task", json=task)
        response.raise_for_status()
        
        result = response.json()
        
        # Display task status
        console.print(Panel(
            f"Task ID: {result.get('taskId', 'N/A')}\n"
            f"Status: {result.get('status', 'N/A')}\n"
            f"Completed At: {result.get('completedAt', 'N/A')}",
            title="Task Result",
            border_style="green"
        ))
        
        # Extract content from parts
        if 'parts' in result and result['parts']:
            content = result['parts'][0].get('content', {})
            
            # Handle string content (error messages)
            if isinstance(content, str):
                console.print(f"\n[red]Error: {content}[/red]")
                return None
            
            # Display message
            if 'message' in content:
                console.print(f"\n[bold]Summary:[/bold] {content['message']}")
            
            # Display context ID
            if 'context_id' in content:
                console.print(f"[dim]Context ID: {content['context_id']}[/dim]")
            
            # Display signals
            if 'signals' in content and content['signals']:
                console.print(f"\n[bold green]Found {len(content['signals'])} signals:[/bold green]")
                
                table = Table(show_header=True, header_style="bold cyan")
                table.add_column("Signal ID", style="yellow")
                table.add_column("Name", style="white")
                table.add_column("Coverage", justify="right")
                table.add_column("CPM", justify="right")
                
                for signal in content['signals'][:5]:  # Show first 5
                    pricing = signal.get('pricing', {})
                    cpm = pricing.get('cpm', 'N/A')
                    if isinstance(cpm, (int, float)):
                        cpm = f"${cpm:.2f}"
                    
                    table.add_row(
                        signal.get('signals_agent_segment_id', 'N/A'),
                        signal.get('name', 'N/A')[:40],
                        f"{signal.get('coverage_percentage', 0):.1f}%",
                        str(cpm)
                    )
                
                console.print(table)
            
            return content.get('context_id')
        
    except Exception as e:
        console.print(f"[red]✗ Discovery task failed: {e}[/red]")
        return None


def test_activation(base_url: str = "http://localhost:8080", 
                   signal_id: str = "sports_enthusiasts_public",
                   platform: str = "the-trade-desk",
                   context_id: Optional[str] = None):
    """Test activation task."""
    console.print(f"\n[bold blue]Testing Activation Task[/bold blue]")
    console.print(f"Signal: {signal_id}")
    console.print(f"Platform: {platform}")
    
    task = {
        "taskId": f"test_activation_{int(datetime.now().timestamp())}",
        "type": "activation",
        "parameters": {
            "signal_id": signal_id,
            "platform": platform
        }
    }
    
    if context_id:
        task["parameters"]["context_id"] = context_id
        console.print(f"Context: {context_id}")
    
    try:
        response = requests.post(f"{base_url}/a2a/task", json=task)
        response.raise_for_status()
        
        result = response.json()
        
        # Display task status
        status_color = "green" if result.get('status') == 'completed' else "yellow"
        console.print(Panel(
            f"Task ID: {result.get('taskId', 'N/A')}\n"
            f"Status: {result.get('status', 'N/A')}\n"
            f"Completed At: {result.get('completedAt', 'N/A')}",
            title="Task Result",
            border_style=status_color
        ))
        
        # Extract content from parts
        if 'parts' in result and result['parts']:
            content = result['parts'][0].get('content', {})
            
            # Handle string content (error messages)
            if isinstance(content, str):
                console.print(f"\n[red]Error: {content}[/red]")
                return None
            
            # Display message
            if 'message' in content:
                console.print(f"\n[bold]Result:[/bold] {content['message']}")
            
            # Display activation details
            if 'decisioning_platform_segment_id' in content:
                console.print(f"\nPlatform Segment ID: {content['decisioning_platform_segment_id']}")
            
            if 'status' in content:
                status_emoji = {
                    'deployed': '🟢',
                    'activating': '🟡',
                    'failed': '🔴'
                }.get(content['status'], '⚪')
                console.print(f"Activation Status: {status_emoji} {content['status'].upper()}")
            
            if content.get('estimated_activation_duration_minutes'):
                console.print(f"Estimated Duration: {content['estimated_activation_duration_minutes']} minutes")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Activation task failed: {e}[/red]")
        return False


def main():
    """Run A2A protocol tests."""
    parser = argparse.ArgumentParser(description="Test A2A Protocol Implementation")
    parser.add_argument('--url', default='http://localhost:8080', help='A2A server URL')
    parser.add_argument('--query', default='luxury car buyers', help='Discovery query')
    parser.add_argument('--signal', default='sports_enthusiasts_public', help='Signal ID to activate')
    parser.add_argument('--platform', default='the-trade-desk', help='Platform for activation')
    parser.add_argument('--test', choices=['all', 'card', 'discovery', 'activation'], 
                       default='all', help='Which test to run')
    
    args = parser.parse_args()
    
    console.print(Panel(
        "[bold cyan]🎯 A2A Protocol Test Client[/bold cyan]\n"
        f"Testing server at: {args.url}",
        border_style="blue"
    ))
    
    # Run tests based on selection
    if args.test in ['all', 'card']:
        test_agent_card(args.url)
    
    context_id = None
    if args.test in ['all', 'discovery']:
        context_id = test_discovery(args.url, args.query)
    
    if args.test in ['all', 'activation']:
        test_activation(args.url, args.signal, args.platform, context_id)
    
    console.print("\n[bold green]✓ Tests completed[/bold green]")


if __name__ == "__main__":
    from datetime import datetime
    from typing import Optional
    
    main()