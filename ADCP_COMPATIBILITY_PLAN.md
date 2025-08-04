# AdCP Spec Compatibility Plan

This document outlines the changes needed to make the signals-agent compatible with the proposed AdCP specification changes in PR #19.

## Overview

The AdCP spec is moving towards a task-based, protocol-agnostic architecture that supports multiple protocols (MCP, A2A, REST). Since we have no active users, we can make breaking changes without migration concerns.

## Key Changes Required

### 1. Consolidate Signal Status Checking
**Current:** Separate `check_signal_status` tool
**New:** Status checking integrated into `activate_signal` lifecycle
**Action:** Remove `check_signal_status` and enhance `activate_signal` to return status information

### 2. Terminology Updates
**Current:** Tool-based terminology
**New:** Task-based terminology
**Action:** Update all references from "tools" to "tasks"

### 3. Multi-Protocol Support
**Current:** MCP-only implementation using FastMCP
**New:** Support for MCP and A2A protocols
**Action:** Add A2A server implementation alongside existing MCP

## Implementation Tasks

### High Priority

1. **Consolidate Signal Status into Activation**
   - Remove `check_signal_status` function
   - Enhance `activate_signal` to return status information
   - Update response model to include activation status

### Medium Priority

2. **Add A2A Protocol Support**
   - Install a2a-python SDK
   - Create A2A server wrapper for signals agent
   - Map MCP tasks to A2A methods
   - Enable running both MCP and A2A servers concurrently

3. **Update Terminology**
   - Change "tools" to "tasks" throughout codebase
   - Update documentation and comments
   - Rename decorator from `@mcp.tool` to task-oriented naming if needed

### Low Priority

4. **Protocol Abstraction Layer**
   - Create common interface for task implementation
   - Allow tasks to be protocol-agnostic
   - Prepare for future REST API support

## A2A Integration Analysis

### About A2A SDK
The A2A (Agent2Agent) SDK is a framework for building agentic applications, not just a protocol implementation. Key findings:

1. **Database Integrations Purpose**
   - Optional feature for state persistence
   - Supports PostgreSQL, MySQL, SQLite via `a2a-sdk[sql]`
   - Likely used for:
     - Conversation context storage
     - Agent state management
     - Task history/tracking
   - **For our use case**: We already have SQLite for signal data, so we probably don't need A2A's database features

2. **Installation Options**
   ```bash
   # Basic installation (recommended for us)
   uv pip install a2a-sdk
   
   # With optional features we probably don't need
   uv pip install "a2a-sdk[grpc,telemetry,sql]"
   ```

3. **Integration Approach**
   - Create A2A server wrapper for our existing logic
   - Map our MCP tasks to A2A methods
   - Share core business logic between protocols
   - Run both servers concurrently (different ports)

### Considerations
- A2A SDK appears more heavyweight than MCP (includes state management, persistence)
- We should start with minimal installation and add features as needed
- Our existing SQLite database should suffice - no need for A2A's database integrations
- Documentation/examples are limited, may require experimentation

## Simplified Architecture

```
┌─────────────┐     ┌─────────────┐
│  MCP Client │     │  A2A Client │
└──────┬──────┘     └──────┬──────┘
       │                   │
┌──────▼──────┐     ┌──────▼──────┐
│ MCP Server  │     │ A2A Server  │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 │
         ┌───────▼────────┐
         │  Core Logic    │
         │  - Discover    │
         │  - Activate    │
         │  - Adapters    │
         └────────────────┘
```

## Timeline

- Remove `check_signal_status`: 1 hour
- Update terminology: 2 hours
- A2A integration: 1-2 days
- Testing: 1 day

Total: ~3 days

## Notes

- No backward compatibility needed (no active users)
- `promoted_offering` and `policy_compliance` are media buy spec only - not needed for signals
- Focus on clean implementation of multi-protocol support

## Recommendation

Given the limited documentation for A2A SDK and its seemingly heavyweight nature (with built-in state management and database features we don't need), I recommend:

1. **Phase 1: Core AdCP Compliance (1-2 days)**
   - Remove `check_signal_status` 
   - Update terminology from tools to tasks
   - Test with existing MCP implementation

2. **Phase 2: A2A Evaluation (1 day)**
   - Install basic A2A SDK
   - Create minimal proof-of-concept
   - Assess integration complexity

3. **Phase 3: Full Multi-Protocol Support (2-3 days if viable)**
   - Only proceed if A2A POC is successful
   - Implement protocol abstraction layer
   - Deploy dual-protocol support

This phased approach lets us achieve AdCP compliance quickly while deferring the more complex A2A integration until we better understand its requirements and benefits.