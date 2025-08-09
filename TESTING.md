# Testing Guide for Signals Agent

This document describes the comprehensive testing suite for the Signals Agent.

## Quick Start

```bash
# Run pre-deployment checks
make pre-deploy

# Deploy with validation
make deploy

# Test production
make test-prod
```

## Test Suite Components

### 1. End-to-End Tests (`test_e2e.py`)

Comprehensive test suite that validates:
- All endpoints are accessible
- A2A protocol compliance
- MCP protocol compliance  
- Context handling
- Error handling
- Performance

**Usage:**
```bash
# Test local server
uv run python test_e2e.py http://localhost:8000

# Test production
uv run python test_e2e.py --production
```

### 2. Routing Tests (`test_routing.py`)

Specifically tests all routing endpoints to ensure they're accessible and returning correct status codes.

**Usage:**
```bash
# Test local
uv run python test_routing.py http://localhost:8000

# Test production
uv run python test_routing.py https://audience-agent.fly.dev
```

### 3. Pre-Deployment Validation (`pre_deploy_check.py`)

Run before deploying to ensure everything works correctly:
- Syntax checking
- Import validation
- Database verification
- Local server testing
- Full E2E test suite
- Dockerfile validation

**Usage:**
```bash
make pre-deploy
```

### 4. Post-Deployment Verification (`post_deploy_verify.py`)

Run after deploying to ensure deployment was successful:
- Health checks
- Full E2E test suite
- SSL certificate validation
- Production-specific checks

**Usage:**
```bash
make post-deploy
```

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make setup` | Install dependencies and initialize database |
| `make test` | Run all tests locally |
| `make test-local` | Run E2E tests against local server |
| `make test-prod` | Run E2E tests against production |
| `make pre-deploy` | Run pre-deployment validation |
| `make deploy` | Deploy with full validation |
| `make post-deploy` | Verify deployment |
| `make clean` | Clean up temporary files |
| `make run-local` | Start local server for development |
| `make db-reset` | Reset the database |
| `make db-inspect` | Inspect database contents |

## Testing Workflow

### Before Making Changes

1. Run tests to ensure baseline:
   ```bash
   make test-local
   ```

### After Making Changes

1. Run pre-deployment validation:
   ```bash
   make pre-deploy
   ```

2. If all tests pass, deploy:
   ```bash
   make deploy
   ```

3. The deploy command automatically runs post-deployment verification

### Testing Individual Components

```bash
# Test just A2A protocol
uv run python -c "from test_e2e import E2ETestSuite; suite = E2ETestSuite('http://localhost:8000'); suite.test_a2a_protocol()"

# Test just context handling
uv run python -c "from test_e2e import E2ETestSuite; suite = E2ETestSuite('http://localhost:8000'); suite.test_context_handling()"
```

## Common Issues and Solutions

### Issue: 404 on /a2a/jsonrpc endpoint

**Cause:** Route registration issue in FastAPI
**Solution:** Ensure using `APIRouter` and `include_router()` properly

### Issue: 500 errors on subsequent requests

**Cause:** Module-level initialization in imported modules
**Solution:** Use lazy imports inside functions

### Issue: Context handling not working

**Cause:** Context ID not being passed correctly or AI not detecting contextual queries
**Solution:** Check contextId is in params for JSON-RPC, improve contextual detection

### Issue: Tests pass locally but fail in production

**Cause:** Environment differences, missing dependencies, or deployment issues
**Solution:** Run `make pre-deploy` before deploying, check Fly.io logs

## Adding New Tests

To add new tests, edit `test_e2e.py` and add a new test method to the `E2ETestSuite` class:

```python
def test_my_feature(self):
    """Test my new feature."""
    print(f"\n{Colors.BOLD}X. My Feature Test{Colors.ENDC}")
    
    try:
        # Your test logic here
        response = self.session.get(f"{self.base_url}/my-endpoint")
        if response.status_code == 200:
            self.results.add_pass("My feature works")
        else:
            self.results.add_fail("My feature", f"Status {response.status_code}")
    except Exception as e:
        self.results.add_fail("My feature test", str(e))
```

Then call it from `run_all_tests()`.

## CI/CD Integration

The test suite is integrated with GitHub Actions. See `.github/workflows/test.yml` for the configuration.

Tests run automatically on:
- Pull requests to main branch
- Can be triggered manually

## Performance Benchmarks

Expected performance metrics:
- Health check: < 200ms
- Agent card retrieval: < 500ms
- Simple query: < 2s
- Contextual query: < 1s
- Concurrent requests: Should handle 3+ simultaneous requests

## Security Testing

The test suite includes basic security checks:
- Invalid input rejection
- Error message sanitization
- SSL certificate validation (production only)

For more comprehensive security testing, consider additional tools like:
- OWASP ZAP
- Burp Suite
- Custom penetration testing