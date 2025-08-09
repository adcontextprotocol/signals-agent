#!/usr/bin/env python3
"""
Test full LiveRamp catalog sync with intelligent search
"""
import json
from adapters.liveramp import LiveRampAdapter
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

console = Console()

def test_full_sync():
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    liveramp_config = config['platforms']['liveramp']
    
    console.print("\n[bold blue]LiveRamp Full Catalog Sync Test[/bold blue]\n")
    
    # Initialize enhanced adapter
    adapter = LiveRampAdapter(liveramp_config)
    
    # Check current status
    stats = adapter.get_statistics()
    console.print(f"Current cache: {stats['total_segments']} segments")
    
    if stats['sync_status'].get('status') != 'never_synced':
        last_sync = stats['sync_status'].get('last_sync', 'Unknown')
        console.print(f"Last sync: {last_sync}")
    
    # Perform sync (limiting for test)
    console.print("\n[yellow]Starting catalog sync (this may take a few minutes)...[/yellow]")
    
    # For testing, let's just sync first few pages
    result = adapter.sync_all_segments(force_refresh=True)
    
    console.print(f"\n[green]✓ Sync complete![/green]")
    console.print(f"  Total segments: {result['total_segments']}")
    console.print(f"  Sync duration: {result['sync_duration']:.1f} seconds")
    
    # Test search functionality
    console.print("\n[yellow]Testing search functionality...[/yellow]\n")
    
    test_queries = [
        "automotive luxury cars",
        "health wellness fitness",
        "technology software developers",
        "travel vacation hotels",
        "financial services banking"
    ]
    
    for query in test_queries:
        console.print(f"[cyan]Searching for: '{query}'[/cyan]")
        results = adapter.search_segments(query, limit=5)
        
        if results:
            table = Table(title=f"Top results for '{query}'")
            table.add_column("Name", style="magenta", max_width=50)
            table.add_column("Provider", style="green")
            table.add_column("Coverage", style="yellow")
            table.add_column("Relevance", style="cyan")
            
            for segment in results[:3]:
                table.add_row(
                    segment['name'][:50] + "..." if len(segment['name']) > 50 else segment['name'],
                    segment['provider'][:20],
                    f"{segment['coverage_percentage']:.1f}%" if segment['coverage_percentage'] else "Unknown",
                    f"{abs(segment['relevance_score']):.2f}"
                )
            
            console.print(table)
        else:
            console.print(f"  No results found")
        
        console.print()
    
    # Show statistics
    final_stats = adapter.get_statistics()
    console.print("\n[bold green]Cache Statistics:[/bold green]")
    console.print(f"  Total segments: {final_stats['total_segments']}")
    console.print(f"  Segments with pricing: {final_stats['segments_with_pricing']}")
    console.print(f"  Segments with reach data: {final_stats['segments_with_reach']}")
    
    console.print("\n[bold green]Top Data Providers:[/bold green]")
    for provider in final_stats['top_providers'][:5]:
        console.print(f"  {provider['provider_name']}: {provider['count']} segments")

if __name__ == "__main__":
    test_full_sync()