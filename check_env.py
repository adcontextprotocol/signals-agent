#!/usr/bin/env python
"""Quick script to check which environment variables are set in production."""

import os

def check_env():
    """Check which relevant environment variables are set."""
    
    print("=== Environment Check ===\n")
    
    # LiveRamp variables
    print("LiveRamp Configuration:")
    liveramp_vars = [
        'LIVERAMP_CLIENT_ID',
        'LIVERAMP_ACCOUNT_ID', 
        'LIVERAMP_SECRET_KEY',
        'LIVERAMP_TOKEN_URI',
        'LIVERAMP_OWNER_ORG',
        'LIVERAMP_UID'
    ]
    
    for var in liveramp_vars:
        value = os.environ.get(var)
        if value:
            # Mask the value for security
            masked = value[:4] + '...' + value[-4:] if len(value) > 8 else '***'
            print(f"  {var}: ✓ (set to {masked})")
        else:
            print(f"  {var}: ✗ (not set)")
    
    print("\nOther Important Variables:")
    other_vars = [
        'GEMINI_API_KEY',
        'IX_USERNAME',
        'IX_PASSWORD',
        'DATABASE_PATH',
        'FLY_APP_NAME',
        'FLY_REGION'
    ]
    
    for var in other_vars:
        value = os.environ.get(var)
        if value:
            if 'PASSWORD' in var or 'KEY' in var:
                masked = value[:4] + '...' + value[-4:] if len(value) > 8 else '***'
                print(f"  {var}: ✓ (set to {masked})")
            else:
                print(f"  {var}: ✓ ({value})")
        else:
            print(f"  {var}: ✗ (not set)")
    
    # Check if we're in Fly.io
    if os.environ.get('FLY_APP_NAME'):
        print("\n✓ Running in Fly.io environment")
        print(f"  App: {os.environ.get('FLY_APP_NAME')}")
        print(f"  Region: {os.environ.get('FLY_REGION')}")
    else:
        print("\n✗ Not running in Fly.io environment")
    
    # Check database location
    print("\nDatabase Locations:")
    possible_paths = [
        ('/data/signals_agent.db', 'Fly.io production'),
        ('signals_agent.db', 'Local development'),
    ]
    
    for path, desc in possible_paths:
        if os.path.exists(path):
            print(f"  ✓ {desc}: {path} exists")
            # Check size
            size = os.path.getsize(path)
            print(f"    Size: {size:,} bytes")
        else:
            print(f"  ✗ {desc}: {path} not found")

if __name__ == "__main__":
    check_env()