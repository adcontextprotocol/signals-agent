# Context ID Design for Signals Agent

## Overview

Context IDs maintain conversation state across the signal discovery and activation workflow. This is especially important for:
- Multi-protocol support (MCP doesn't have built-in context, A2A does)
- Tracking user intent through multi-step workflows
- Analytics and debugging
- Future conversational AI integrations

## Current State

Our MCP implementation currently has no context tracking. Each request is stateless.

## Proposed Implementation

### 1. Context ID Flow

```
User discovers signals → Context ID generated → Returned in response
        ↓
User activates signal → Provides context ID → Links to discovery
        ↓
User checks status → Provides context ID → Full workflow tracked
```

### 2. Context ID Format

```
context_id: "ctx_<timestamp>_<random>"
Example: "ctx_1735650000_a1b2c3d4"
```

### 3. Schema Changes

#### GetSignalsRequest
```python
class GetSignalsRequest(BaseModel):
    # ... existing fields ...
    context_id: Optional[str] = Field(
        None,
        description="Optional context ID from previous interaction"
    )
```

#### GetSignalsResponse
```python
class GetSignalsResponse(BaseModel):
    signals: List[SignalResponse]
    custom_segment_proposals: Optional[List[CustomSegmentProposal]] = None
    context_id: str = Field(
        ...,
        description="Context ID for this discovery session"
    )
```

#### ActivateSignalRequest
```python
class ActivateSignalRequest(BaseModel):
    signals_agent_segment_id: str
    platform: str
    account: Optional[str] = None
    context_id: Optional[str] = Field(
        None,
        description="Context ID from discovery session"
    )
```

### 4. Implementation Details

#### Context Storage
```python
# In-memory context storage (could be Redis in production)
discovery_contexts: Dict[str, Dict] = {}

def generate_context_id() -> str:
    """Generate unique context ID."""
    timestamp = int(datetime.now().timestamp())
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"ctx_{timestamp}_{random_suffix}"

def store_discovery_context(context_id: str, signal_spec: str, results: List[str]):
    """Store discovery context for later reference."""
    discovery_contexts[context_id] = {
        "signal_spec": signal_spec,
        "discovered_signals": results,
        "timestamp": datetime.now().isoformat(),
        "activations": []
    }

def link_activation_to_context(context_id: str, signal_id: str, platform: str):
    """Link an activation to its discovery context."""
    if context_id in discovery_contexts:
        discovery_contexts[context_id]["activations"].append({
            "signal_id": signal_id,
            "platform": platform,
            "activated_at": datetime.now().isoformat()
        })
```

#### Updated get_signals
```python
@mcp.tool
def get_signals(..., context_id: Optional[str] = None) -> GetSignalsResponse:
    # ... existing logic ...
    
    # Generate or reuse context ID
    if not context_id:
        context_id = generate_context_id()
    
    # Store discovery context
    store_discovery_context(
        context_id,
        signal_spec,
        [s["signals_agent_segment_id"] for s in signals]
    )
    
    return GetSignalsResponse(
        signals=signals,
        custom_segment_proposals=custom_proposals,
        context_id=context_id
    )
```

#### Updated activate_signal
```python
@mcp.tool
def activate_signal(
    signals_agent_segment_id: str,
    platform: str,
    account: Optional[str] = None,
    principal_id: Optional[str] = None,
    context_id: Optional[str] = None
) -> ActivateSignalResponse:
    # ... existing logic ...
    
    # Link to discovery context if provided
    if context_id:
        link_activation_to_context(context_id, signals_agent_segment_id, platform)
    
    # ... rest of activation logic ...
```

### 5. Benefits

1. **Workflow Tracking**: Full visibility into discovery → activation flow
2. **Analytics**: Understand which discoveries lead to activations
3. **Multi-Protocol Ready**: A2A requires context IDs, this prepares us
4. **Debugging**: Easier to trace issues through the full workflow
5. **Future Features**: Enable "activate all from this search" type features

### 6. Migration Path

1. **Phase 1**: Add optional context_id fields (backward compatible)
2. **Phase 2**: Generate and return context IDs in responses
3. **Phase 3**: Use context IDs for workflow tracking
4. **Phase 4**: Add context-based features (bulk actions, etc.)

### 7. A2A Compatibility

When we add A2A support, we can map our context IDs to A2A's contextId:
```python
# MCP context_id → A2A contextId
a2a_request = {
    "contextId": mcp_context_id,
    # ... other A2A fields
}
```

This ensures seamless protocol interoperability.