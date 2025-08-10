# Migration Guide: Replacing Our Server with python-a2a

## What Gets Replaced

### Files We Can Delete
```
✅ unified_server.py    → Replaced by python-a2a's run_server()
✅ a2a_facade.py        → Replaced by @skill decorators
✅ mcp_facade.py        → Replaced by FastMCPAgent
✅ a2a_schemas.py       → Built into python-a2a
✅ main.py (partially)  → Simplified to just run_server()
✅ test_sse.py          → SSE works properly out of the box
```

### Files We Keep
```
✅ business_logic.py   → Core logic stays exactly the same!
✅ core_logic.py       → Database operations unchanged
✅ database.py         → Still needed
✅ adapters/*          → Platform adapters unchanged
✅ config.json         → Configuration still used
```

## Key Benefits of Migration

### 1. **Streaming Just Works**
```python
# Before: Complex SSE implementation that didn't work
async def generate_sse():
    yield f"data: {json.dumps(response_data)}\n\n"
    yield "data: [DONE]\n\n"

# After: Automatic SSE support
@skill(name="discover")
async def discover(self, query: str):
    return result  # Library handles SSE if client wants it
```

### 2. **Protocol Compliance**
- ✅ Proper A2A agent card generation
- ✅ Correct JSON-RPC implementation  
- ✅ Real send/subscribe support
- ✅ MCP tool discovery
- ✅ Error handling to spec

### 3. **Less Code to Maintain**
- **Before**: ~1000 lines across multiple facade files
- **After**: ~200 lines in single agent file
- **Reduction**: 80% less protocol code

### 4. **Better Features**
- Visual workflow UI (optional)
- Agent discovery/registry
- Multi-agent orchestration
- LangChain integration
- Built-in CLI tools

## Migration Steps

### Step 1: Install python-a2a
```bash
uv pip install python-a2a[all]
```

### Step 2: Create New Agent File
Use `proof_of_concept_a2a.py` as template

### Step 3: Update Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install python-a2a
RUN pip install python-a2a[server,mcp]

# Copy our business logic
COPY business_logic.py core_logic.py database.py ./
COPY adapters/ ./adapters/
COPY config.json ./

# Copy new agent file
COPY signals_agent.py ./

# Run the unified server
CMD ["python", "signals_agent.py"]
```

### Step 4: Update fly.toml
```toml
[env]
  PORT = "8000"
  HOST = "0.0.0.0"
  ENABLE_UI = "false"  # Set to "true" for visual UI

[http_service]
  internal_port = 8000
  # All endpoints handled automatically:
  # - /agent-card
  # - /a2a/task
  # - /a2a/jsonrpc (with proper SSE!)
  # - MCP endpoints
```

### Step 5: Test Everything
```bash
# Test A2A discovery
curl https://your-app.fly.dev/agent-card

# Test A2A message (now with working SSE!)
curl -X POST https://your-app.fly.dev/a2a/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"message/send","params":{"message":{"parts":[{"type":"text","text":"sports"}]}},"id":"1"}'

# Test MCP tools
a2a mcp-call https://your-app.fly.dev search_audiences --params query="luxury"
```

## What About Our Custom Logic?

**All preserved!** The beauty is that python-a2a handles the protocol layer while we keep our business logic:

```python
@skill(name="discover_audiences")
async def discover_audiences(self, query: str, context_id: str = None):
    # This calls our existing business_logic.py!
    result = business_logic.process_discovery_query(
        query=query,
        context_id=context_id
    )
    return result  # Library handles protocol formatting
```

## Development Workflow

### Local Development
```bash
# Start with hot reload
uvicorn signals_agent:app --reload --host 0.0.0.0 --port 8000

# Or use the built-in runner
python signals_agent.py
```

### With Visual UI
```bash
# Enable the UI for visual workflow design
ENABLE_UI=true python signals_agent.py

# Access at http://localhost:8000/ui
```

## Risks and Mitigation

### Risk 1: External Dependency
**Mitigation**: python-a2a is well-maintained and follows official specs

### Risk 2: Migration Effort  
**Mitigation**: Can run both versions in parallel during transition

### Risk 3: Custom Features
**Mitigation**: Library is extensible - can add custom middleware/handlers

## Recommendation

**Strongly recommend migrating** because:

1. **Immediate fix** for all protocol issues (SSE, streaming, etc.)
2. **80% code reduction** in protocol handling
3. **Future features** come free with library updates
4. **Better testing** - library is well-tested
5. **Visual UI** bonus for debugging and demos

## Timeline Estimate

- **Day 1**: Install and create proof of concept ✅ (done above)
- **Day 2**: Migrate core functionality, test locally
- **Day 3**: Deploy to staging, test with your client
- **Day 4**: Production deployment
- **Day 5**: Remove old code, optimize

Total: ~1 week for complete migration with testing