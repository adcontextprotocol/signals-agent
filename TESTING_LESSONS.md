# Testing Lessons Learned

## Why Our Initial Testing Failed to Catch the Issue

The A2A Inspector found a missing `url` field that our testing didn't catch because:

1. **Incomplete Schema Knowledge**: We were only testing for fields we knew about, not validating against the complete A2A specification.

2. **Manual Field Checking**: Our tests were manually checking for specific fields rather than using a comprehensive schema validator.

3. **No Official Schema Reference**: We didn't have the official A2A schema definition to validate against.

## How to Test More Effectively

### 1. Use Schema-Based Validation

Instead of manually checking fields:
```python
# Bad - Manual checking
if "name" in card and "version" in card:
    print("✓ Has required fields")
```

Use Pydantic schemas:
```python
# Good - Schema validation
from pydantic import BaseModel, HttpUrl

class AgentCardSchema(BaseModel):
    name: str
    url: HttpUrl  # Would have caught the missing field!
    version: str
    # ... all other required fields

try:
    AgentCardSchema(**card)
    print("✓ Valid schema")
except ValidationError as e:
    print(f"✗ Schema errors: {e}")
```

### 2. Test with Official Tools

- **A2A Inspector**: The official validator that checks against the real spec
- **MCP SDK**: Use the official SDK client, not just manual HTTP requests
- **Protocol Test Suites**: If available, run official compliance test suites

### 3. Create Comprehensive Test Files

We now have:
- `test_mcp_official.py` - Tests MCP with proper protocol flow
- `test_a2a_official.py` - Tests A2A with all endpoints
- `test_a2a_validation.py` - Schema-based validation
- `a2a_schemas.py` - Complete Pydantic schemas for validation

### 4. Common A2A Requirements We Missed

- `url` field at root level (agent's base URL)
- Proper header detection for deployed environments
- `message_id` not `messageId` (underscore convention)
- `role: "agent"` not `role: "assistant"`

### 5. Better Deployment Testing

The `url` field was particularly tricky because:
- It worked locally (http://localhost:8000)
- But failed in deployment due to proxy headers
- Solution: Check `X-Forwarded-Proto` and `X-Forwarded-Host` headers

```python
# Proper URL detection for deployed apps
forwarded_proto = request.headers.get('x-forwarded-proto', 'http')
forwarded_host = request.headers.get('x-forwarded-host')
if forwarded_host:
    base_url = f"{forwarded_proto}://{forwarded_host}"
```

### 6. Test Checklist for Protocol Compliance

Before declaring a protocol implementation complete:

- [ ] Run schema validation with Pydantic models
- [ ] Test with official client/inspector tools
- [ ] Verify all endpoints with deployed URL (not just localhost)
- [ ] Check proxy headers and URL construction
- [ ] Validate error responses match spec
- [ ] Test contextual/stateful operations
- [ ] Verify CORS headers for web clients
- [ ] Test streaming endpoints if supported

## Key Takeaway

**Don't assume you know the complete specification.** Always:
1. Find and use official schemas/validators
2. Test with official tools when available
3. Create comprehensive schema-based tests
4. Test in the actual deployment environment, not just locally