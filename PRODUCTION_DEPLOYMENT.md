# Production Deployment Guide

## Issue: "No signals found" in Production - FIXED

### Root Causes Identified and Fixed

1. **LiveRamp table name mismatch** - ✅ Fixed: Tables now use consistent `liveramp_segments` naming
2. **LiveRamp adapter not enabled** - Requires environment variables to activate
3. **LiveRamp database not synced** - No segment data available even when enabled
4. **Silent failures** - ✅ Fixed: Added better error logging and diagnostic messages

### Required Environment Variables

#### For LiveRamp Integration
```bash
export LIVERAMP_CLIENT_ID="your-client-id"
export LIVERAMP_ACCOUNT_ID="your-service-account"
export LIVERAMP_SECRET_KEY="your-secret-key"
export LIVERAMP_TOKEN_URI="your-token-uri"
export LIVERAMP_OWNER_ORG="your-owner-org"
```

#### For Index Exchange Integration
```bash
export IX_USERNAME="your-username@example.com"
export IX_PASSWORD="your-password"
export IX_DEFAULT_ACCOUNT="your-default-account-id"
```

#### For Gemini AI (Required for ranking)
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

#### Database Path (for Fly.io)
```bash
export DATABASE_PATH="/data/signals_agent.db"
```

### Deployment Steps

1. **Set Environment Variables**
   - Add all required environment variables to your Fly.io secrets or deployment environment
   - LiveRamp credentials are REQUIRED for LiveRamp segments to appear

2. **Initialize Database**
   ```bash
   uv run python database.py
   ```
   This creates tables and adds sample segments.

3. **Sync LiveRamp Catalog** (if LiveRamp is enabled)
   ```bash
   uv run python sync_liveramp_catalog.py --full
   ```
   This downloads the entire LiveRamp catalog (~200,000 segments).
   Note: This can take 30-60 minutes for a full sync.

4. **Start the Server**
   ```bash
   uv run python main.py
   ```

### Verification Checklist

Run these commands to verify deployment:

```bash
# Check database has segments
sqlite3 $DATABASE_PATH "SELECT COUNT(*) FROM signal_segments;"
# Should return > 0 (14 with sample data)

# Check LiveRamp segments (if enabled)
sqlite3 $DATABASE_PATH "SELECT COUNT(*) FROM liveramp_segments;"
# Should return > 0 after sync (200,000+ when fully synced)

# Test LiveRamp configuration
uv run python test_liveramp.py

# Test search functionality
uv run python client.py --prompt "finance" --limit 10
```

### Common Issues and Solutions

#### Issue: "No signals found" for any query
**Solution:** 
- Run diagnostic test: `uv run python test_liveramp.py`
- Check if Gemini API key is set (required for AI ranking)
- Verify LiveRamp is enabled and synced
- The system will now show clear error messages indicating what's missing

#### Issue: No LiveRamp segments appearing
**Solution:**
- Check LiveRamp is enabled: Environment variables must be set
- Verify sync has been run: `sqlite3 signals_agent.db "SELECT COUNT(*) FROM liveramp_segments;"`
- Check for sync errors in logs

#### Issue: Platform adapter errors
**Solution:**
- Disable platforms without valid credentials in config.json
- Or provide valid credentials via environment variables

### Production Configuration Example

```json
{
  "platforms": {
    "liveramp": {
      "enabled": true,  // Auto-enabled when LIVERAMP_CLIENT_ID is set
      "base_url": "https://api.liveramp.com"
    },
    "index-exchange": {
      "enabled": true,  // Enable if you have IX credentials
      "test_mode": false
    }
  }
}
```

### Scheduled Jobs (Fly.io)

Add to fly.toml for daily LiveRamp sync:
```toml
[processes]
web = "uv run python main.py"
sync = "uv run python sync_liveramp_catalog.py --scheduled"

[[services]]
  processes = ["web"]
  # ... rest of web service config

[experimental]
  [[experimental.scheduled_machines]]
    schedule = "daily"
    command = "uv run python sync_liveramp_catalog.py --full"
    memory = 2048
```

### Monitoring

Check these metrics in production:
- Total segments in database
- LiveRamp sync status and last sync time
- Search query response times
- Platform adapter connection status

### Emergency Fixes

If search returns no results in production:

1. **Quick Fix - Add sample data:**
   ```bash
   uv run python -c "from database import init_db; init_db()"
   ```

2. **Check adapter status:**
   ```bash
   uv run python -c "
   from config_loader import load_config
   from adapters.manager import AdapterManager
   config = load_config()
   manager = AdapterManager(config)
   print('Loaded adapters:', list(manager.adapters.keys()))
   "
   ```

3. **Force LiveRamp sync (if configured):**
   ```bash
   uv run python sync_liveramp_catalog.py --force
   ```

### Testing Search Functionality

Use the included test script:
```bash
uv run python client.py --prompt "finance bros" --limit 10
```

Expected output should include:
- Finance-related segments from signal_segments table
- LiveRamp segments (if synced and enabled)
- Proper ranking based on relevance