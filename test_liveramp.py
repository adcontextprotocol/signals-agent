#!/usr/bin/env python
"""Test LiveRamp adapter functionality."""

import os
import sqlite3
from config_loader import load_config
from adapters.liveramp import LiveRampAdapter

def test_liveramp():
    """Test LiveRamp adapter and database integration."""
    
    print("\n=== Testing LiveRamp Integration ===\n")
    
    # Load config
    config = load_config()
    lr_config = config.get('platforms', {}).get('liveramp', {})
    
    # Check if LiveRamp is configured
    print("1. Configuration Check:")
    has_client_id = bool(lr_config.get('client_id'))
    has_secret = bool(lr_config.get('secret_key'))
    is_enabled = lr_config.get('enabled', False)
    
    print(f"   - Client ID configured: {'✓' if has_client_id else '✗'}")
    print(f"   - Secret key configured: {'✓' if has_secret else '✗'}")
    print(f"   - Adapter enabled: {'✓' if is_enabled else '✗'}")
    
    if not (has_client_id and has_secret):
        print("\n   ⚠️  LiveRamp not fully configured. Set these environment variables:")
        print("      export LIVERAMP_CLIENT_ID='your-client-id'")
        print("      export LIVERAMP_SECRET_KEY='your-secret-key'")
        print("      export LIVERAMP_ACCOUNT_ID='your-account-id'")
        print("      export LIVERAMP_TOKEN_URI='your-token-uri'")
        print("      export LIVERAMP_OWNER_ORG='your-owner-org'")
    
    # Check database tables
    print("\n2. Database Check:")
    db_path = os.environ.get('DATABASE_PATH', 'signals_agent.db')
    
    if not os.path.exists(db_path):
        print(f"   ✗ Database not found at {db_path}")
        print("     Run: uv run python database.py")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if LiveRamp tables exist
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='liveramp_segments'
    """)
    has_table = cursor.fetchone() is not None
    print(f"   - LiveRamp segments table exists: {'✓' if has_table else '✗'}")
    
    if has_table:
        cursor.execute("SELECT COUNT(*) FROM liveramp_segments")
        count = cursor.fetchone()[0]
        print(f"   - Segments in database: {count}")
        
        if count == 0:
            print("\n   ⚠️  No LiveRamp segments in database. To sync:")
            print("      uv run python sync_liveramp_catalog.py --full")
        else:
            # Show sample segments
            cursor.execute("SELECT name FROM liveramp_segments LIMIT 3")
            samples = cursor.fetchall()
            print("\n   Sample segments:")
            for row in samples:
                print(f"     - {row[0]}")
    
    # Check sync status
    cursor.execute("""
        SELECT sync_completed, total_segments, status 
        FROM liveramp_sync_status 
        ORDER BY id DESC LIMIT 1
    """)
    sync_row = cursor.fetchone()
    
    if sync_row:
        print(f"\n3. Last Sync Status:")
        print(f"   - Completed: {sync_row[0]}")
        print(f"   - Segments synced: {sync_row[1]}")
        print(f"   - Status: {sync_row[2]}")
    else:
        print("\n3. Sync Status: Never synced")
    
    # Test adapter if configured
    if is_enabled and has_client_id and has_secret:
        print("\n4. Testing LiveRamp Adapter:")
        try:
            adapter = LiveRampAdapter(lr_config)
            
            # Test search
            test_query = "finance"
            print(f"   Testing search for '{test_query}'...")
            
            segments = adapter.get_segments(
                account_id=lr_config.get('account_id', 'default'),
                search_query=test_query
            )
            
            print(f"   ✓ Search returned {len(segments)} segments")
            
            if segments and len(segments) > 0:
                print(f"\n   First result:")
                first = segments[0]
                print(f"     Name: {first.get('name')}")
                print(f"     Provider: {first.get('data_provider')}")
                print(f"     CPM: ${first.get('cpm', 'N/A')}")
                
        except Exception as e:
            print(f"   ✗ Adapter test failed: {e}")
    else:
        print("\n4. Adapter Test: Skipped (not configured)")
    
    conn.close()
    
    print("\n=== Summary ===")
    if is_enabled and count > 0:
        print("✓ LiveRamp is configured and has data")
    elif is_enabled and count == 0:
        print("⚠️  LiveRamp is configured but needs data sync")
    elif not is_enabled:
        print("✗ LiveRamp is not enabled (missing configuration)")
    
    print("\nTo enable LiveRamp in production:")
    print("1. Set environment variables (LIVERAMP_CLIENT_ID, etc.)")
    print("2. Run: uv run python database.py")
    print("3. Run: uv run python sync_liveramp_catalog.py --full")
    print("4. Verify: uv run python test_liveramp.py")

if __name__ == "__main__":
    test_liveramp()