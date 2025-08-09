#!/usr/bin/env python3
"""
Quick test of LiveRamp sync with limited pages
"""
import json
import requests
import time
from adapters.liveramp import LiveRampAdapter
from rich.console import Console

console = Console()

# Load config and authenticate
with open('config.json', 'r') as f:
    config = json.load(f)

adapter = LiveRampAdapter(config['platforms']['liveramp'])
adapter.authenticate()

segments_url = f"{adapter.base_url}/data-marketplace/buyer-api/v3/segments"
headers = {
    'Authorization': f'Bearer {adapter.auth_token}',
    'Accept': 'application/json',
    'LR-Org-Id': adapter.config.get('owner_org', '')
}

console.print("\n[bold blue]Testing LiveRamp Cursor-Based Pagination[/bold blue]\n")

all_segments = []
after_cursor = None
max_pages = 5  # Limit for testing

for page in range(max_pages):
    params = {'limit': 100}
    if after_cursor:
        params['after'] = after_cursor
    
    response = requests.get(segments_url, headers=headers, params=params)
    
    if response.status_code != 200:
        console.print(f"[red]Error on page {page + 1}: {response.status_code}[/red]")
        break
    
    data = response.json()
    segments = data.get('v3_Segments', [])
    all_segments.extend(segments)
    
    # Get next cursor
    pagination = data.get('_pagination', {})
    after_cursor = pagination.get('after')
    
    console.print(f"Page {page + 1}: Retrieved {len(segments)} segments (total: {len(all_segments)})")
    
    # Show sample segment names
    if segments:
        console.print(f"  First: {segments[0]['name'][:50]}...")
        console.print(f"  Last:  {segments[-1]['name'][:50]}...")
    
    if not after_cursor:
        console.print("[green]Reached end of results[/green]")
        break
    
    time.sleep(0.5)  # Be nice to the API

console.print(f"\n[bold green]Summary:[/bold green]")
console.print(f"Total segments fetched: {len(all_segments)}")

# Check for unique providers
providers = set()
for seg in all_segments:
    providers.add(seg.get('providerName', 'Unknown'))

console.print(f"Unique providers: {len(providers)}")
console.print(f"Sample providers: {list(providers)[:5]}")

# Check segment types
segment_types = {}
for seg in all_segments:
    seg_type = seg.get('segmentType', 'Unknown')
    segment_types[seg_type] = segment_types.get(seg_type, 0) + 1

console.print(f"\nSegment types:")
for seg_type, count in segment_types.items():
    console.print(f"  {seg_type}: {count}")