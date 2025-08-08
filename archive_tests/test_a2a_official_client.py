#!/usr/bin/env python3
"""Test client using official A2A SDK."""

import asyncio
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import argparse

# Note: This requires installing the official A2A SDK
# Install with: uv add a2a-sdk or pip install a2a-sdk
try:
    from a2a import Client, Task, TaskStatus
    A2A_AVAILABLE = True
except ImportError:
    A2A_AVAILABLE = False
    print("Error: a2a-sdk not installed. Install with: uv add a2a-sdk")
    exit(1)

console = Console()


async def test_discovery(client: Client, query: str = "luxury car buyers"):
    """Test discovery using official A2A client."""
    console.print(f"\n[bold blue]Testing Discovery Task (Official SDK)[/bold blue]")
    console.print(f"Query: {query}")
    
    # Create discovery task
    task = Task(
        task_id=f"discovery_{int(datetime.now().timestamp())}",
        metadata={"type": "discovery"},
        input_data={
            "query": query,
            "deliver_to": {
                "platforms": "all",
                "countries": ["US"]
            },
            "max_results": 5
        }
    )
    
    try:
        # Submit task to agent
        result = await client.submit_task(task)
        
        # Wait for completion
        while result.status == TaskStatus.IN_PROGRESS:
            await asyncio.sleep(0.5)
            result = await client.get_task_status(result.task_id)
        
        # Display results
        if result.status == TaskStatus.COMPLETED:
            console.print(Panel(
                f"Task ID: {result.task_id}\n"
                f"Status: COMPLETED\n"
                f"Context ID: {result.metadata.get('context_id', 'N/A')}\n"
                f"Signals Found: {result.metadata.get('signal_count', 0)}",
                title="Task Result",
                border_style="green"
            ))
            
            # Extract content from output
            if result.output and result.output.parts:
                content = result.output.parts[0].content
                
                # Display message
                if 'message' in content:
                    console.print(f"\n[bold]Summary:[/bold] {content['message']}")
                
                # Display signals
                if 'signals' in content and content['signals']:
                    console.print(f"\n[bold green]Signals:[/bold green]")
                    
                    table = Table(show_header=True, header_style="bold cyan")
                    table.add_column("Signal ID", style="yellow")
                    table.add_column("Name", style="white")
                    table.add_column("Coverage", justify="right")
                    table.add_column("CPM", justify="right")
                    
                    for signal in content['signals'][:5]:
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
                
                return result.metadata.get('context_id')
        else:
            console.print(f"[red]Task failed: {result.error}[/red]")
            return None
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return None


async def test_activation(client: Client, 
                         signal_id: str = "sports_enthusiasts_public",
                         platform: str = "the-trade-desk",
                         context_id: Optional[str] = None):
    """Test activation using official A2A client."""
    console.print(f"\n[bold blue]Testing Activation Task (Official SDK)[/bold blue]")
    console.print(f"Signal: {signal_id}")
    console.print(f"Platform: {platform}")
    
    # Create activation task
    task_data = {
        "signal_id": signal_id,
        "platform": platform
    }
    
    if context_id:
        task_data["context_id"] = context_id
        console.print(f"Context: {context_id}")
    
    task = Task(
        task_id=f"activation_{int(datetime.now().timestamp())}",
        metadata={"type": "activation"},
        input_data=task_data
    )
    
    try:
        # Submit task to agent
        result = await client.submit_task(task)
        
        # Wait for initial response
        await asyncio.sleep(1)
        result = await client.get_task_status(result.task_id)
        
        # Display results
        status_color = "green" if result.status == TaskStatus.COMPLETED else "yellow"
        console.print(Panel(
            f"Task ID: {result.task_id}\n"
            f"Status: {result.status.name}\n"
            f"Activation Status: {result.metadata.get('activation_status', 'N/A')}\n"
            f"Context ID: {result.metadata.get('context_id', 'N/A')}",
            title="Task Result",
            border_style=status_color
        ))
        
        # Extract content from output
        if result.output and result.output.parts:
            content = result.output.parts[0].content
            
            # Display message
            if 'message' in content:
                console.print(f"\n[bold]Result:[/bold] {content['message']}")
            
            # Display activation details
            if 'decisioning_platform_segment_id' in content:
                console.print(f"\nPlatform Segment ID: {content['decisioning_platform_segment_id']}")
            
            if content.get('estimated_activation_duration_minutes'):
                console.print(f"Estimated Duration: {content['estimated_activation_duration_minutes']} minutes")
        
        return True
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return False


async def main():
    """Run tests using official A2A SDK."""
    parser = argparse.ArgumentParser(description="Test A2A Protocol with Official SDK")
    parser.add_argument('--agent-url', default='http://localhost:8080', help='Agent URL')
    parser.add_argument('--query', default='luxury car buyers', help='Discovery query')
    parser.add_argument('--signal', default='sports_enthusiasts_public', help='Signal ID')
    parser.add_argument('--platform', default='the-trade-desk', help='Platform')
    
    args = parser.parse_args()
    
    console.print(Panel(
        "[bold cyan]🎯 A2A Protocol Test Client (Official SDK)[/bold cyan]\n"
        f"Connecting to agent at: {args.agent_url}",
        border_style="blue"
    ))
    
    # Create A2A client
    client = Client(agent_url=args.agent_url)
    
    try:
        # Test discovery
        context_id = await test_discovery(client, args.query)
        
        # Test activation
        if context_id:
            await test_activation(client, args.signal, args.platform, context_id)
        
        console.print("\n[bold green]✓ Tests completed[/bold green]")
        
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/red]")
    
    finally:
        await client.close()


if __name__ == "__main__":
    from datetime import datetime
    from typing import Optional
    
    if not A2A_AVAILABLE:
        print("Error: a2a-sdk not installed. Install with: uv add a2a-sdk")
        exit(1)
    
    asyncio.run(main())