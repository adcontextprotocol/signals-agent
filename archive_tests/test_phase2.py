#!/usr/bin/env python3
"""Test script for Phase 2 features."""

import sqlite3
import json
from datetime import datetime, timedelta

def test_context_storage():
    """Test that unified context storage is working correctly."""
    conn = sqlite3.connect('signals_agent.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contexts'")
    table = cursor.fetchone()
    
    if table:
        print("✅ Unified contexts table created")
    else:
        print("❌ Contexts table not found")
        return
    
    # Check discovery contexts
    cursor.execute("SELECT * FROM contexts WHERE context_type = 'discovery' ORDER BY created_at DESC")
    discovery_contexts = cursor.fetchall()
    
    if discovery_contexts:
        print(f"\n✅ Found {len(discovery_contexts)} discovery context(s):")
        for ctx in discovery_contexts:
            metadata = json.loads(ctx['metadata'])
            print(f"  - Context ID: {ctx['context_id']}")
            print(f"    Query: {metadata.get('query', 'N/A')}")
            print(f"    Principal: {ctx['principal_id'] or 'Public'}")
            print(f"    Created: {ctx['created_at']}")
            print(f"    Expires: {ctx['expires_at']}")
            
            # Check expiration
            expires = datetime.fromisoformat(ctx['expires_at'])
            days_until_expiry = (expires - datetime.now()).days
            print(f"    Days until expiry: {days_until_expiry}")
            print(f"    Signal count: {len(metadata.get('signal_ids', []))}")
    else:
        print("\n⚠️  No discovery contexts found yet (run a discovery first)")
    
    # Check activation contexts
    cursor.execute("SELECT * FROM contexts WHERE context_type = 'activation' ORDER BY created_at DESC")
    activation_contexts = cursor.fetchall()
    
    if activation_contexts:
        print(f"\n✅ Found {len(activation_contexts)} activation context(s):")
        for ctx in activation_contexts:
            metadata = json.loads(ctx['metadata'])
            print(f"  - Context ID: {ctx['context_id']}")
            print(f"    Signal: {metadata.get('signal_id', 'N/A')} on {metadata.get('platform', 'N/A')}")
            print(f"    Parent context: {ctx['parent_context_id'] or 'None'}")
            print(f"    Activated at: {metadata.get('activated_at', 'N/A')}")
            
            # Check if linked to discovery
            if ctx['parent_context_id']:
                cursor.execute("SELECT * FROM contexts WHERE context_id = ?", (ctx['parent_context_id'],))
                parent = cursor.fetchone()
                if parent:
                    parent_metadata = json.loads(parent['metadata'])
                    print(f"    → Linked to discovery: '{parent_metadata.get('query', 'N/A')}'")
    else:
        print("\n⚠️  No activation contexts found yet (activate a signal with context_id)")
    
    # Show context type distribution
    cursor.execute("SELECT context_type, COUNT(*) as count FROM contexts GROUP BY context_type")
    type_counts = cursor.fetchall()
    
    print("\n📊 Context Type Distribution:")
    for row in type_counts:
        print(f"  - {row['context_type']}: {row['count']}")
    
    conn.close()

if __name__ == "__main__":
    print("🧪 Testing Phase 2 Unified Context Storage\n")
    test_context_storage()