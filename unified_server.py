#!/usr/bin/env python3
"""Unified HTTP server supporting both MCP and A2A protocols."""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import A2A types for proper validation
try:
    from a2a.types import AgentCard, AgentSkill, AgentCapabilities
    A2A_TYPES_AVAILABLE = True
except ImportError:
    A2A_TYPES_AVAILABLE = False

from schemas import (
    GetSignalsRequest, GetSignalsResponse,
    ActivateSignalRequest, ActivateSignalResponse
)
from database import init_db
from config_loader import load_config
from adapters.manager import AdapterManager
from contextual_ai import generate_contextual_response, analyze_query_intent

# Import the MCP tools
import main

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="Signals Agent Unified Server",
    description="Supports both MCP and A2A protocols",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in production, adjust as needed
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)


# ===== Shared Business Logic =====

def get_business_logic():
    """Get initialized business logic components."""
    config = load_config()
    adapter_manager = AdapterManager(config)
    return config, adapter_manager


# ===== A2A Protocol Endpoints =====

@app.get("/")
async def root():
    """Root endpoint - return basic info or redirect to agent card."""
    return {
        "name": "Signals Activation Agent",
        "description": "AI agent for discovering and activating audience signals",
        "version": "1.0.0",
        "agent_card": "/agent-card",
        "protocols": ["a2a", "mcp"]
    }

@app.post("/")
async def handle_a2a_root_task(request: Dict[str, Any]):
    """Handle A2A task requests at root endpoint (A2A standard)."""
    # Check if this is a JSON-RPC message from A2A Inspector
    if "jsonrpc" in request and request.get("method") == "message/send":
        # Extract the actual message from JSON-RPC format
        params = request.get("params", {})
        message = params.get("message", {})
        message_parts = message.get("parts", [])
        
        # Extract text from message parts
        query = ""
        for part in message_parts:
            if part.get("kind") == "text":
                query = part.get("text", "")
                break
        
        # Convert to our expected task format
        # Assume it's a discovery task since that's the most common
        task_request = {
            "taskId": request.get("id"),
            "type": "discovery",
            "contextId": params.get("contextId"),  # Pass through context from JSON-RPC
            "parameters": {
                "query": query
            }
        }
        
        # Process the task
        task_result = await handle_a2a_task(task_request)
        
        # For message/send requests, return Message format instead of Task format
        # Extract the response data from task result
        # The task response has the message parts in status.message.parts
        task_status = task_result.get("status", {})
        task_message = task_status.get("message", {})
        task_parts = task_message.get("parts", [])
        
        # Build proper A2A Message with correct parts format
        message_parts = []
        
        if task_parts:
            # Copy the parts from the task response
            for part in task_parts:
                if part.get("kind") == "text":
                    message_parts.append({
                        "kind": "text",
                        "text": part.get("text", "")
                    })
                elif part.get("kind") == "data":
                    # Get the data part
                    data = part.get("data", {})
                    message_parts.append({
                        "kind": "data", 
                        "data": {
                            "contentType": "application/json",
                            "content": data
                        }
                    })
        
        message_response = {
            "kind": "message",
            "message_id": f"msg_{datetime.now().timestamp()}",  # Fixed: use message_id not messageId
            "parts": message_parts,
            "role": "agent"  # Fixed: use 'agent' instead of 'assistant'
        }
        
        # Wrap response in JSON-RPC format
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": message_response
        }
    else:
        # Standard A2A task format
        return await handle_a2a_task(request)

@app.get("/.well-known/agent.json")
@app.get("/agent-card")
async def get_agent_card(request: Request):
    """Return the A2A Agent Card compliant with the official spec."""
    # Build base URL dynamically, respecting proxy headers
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    if forwarded_proto:
        # We're behind a proxy, use the forwarded protocol
        host = request.headers.get("Host", request.base_url.hostname)
        base_url = f"{forwarded_proto}://{host}"
    else:
        # Direct connection, use the request's base URL
        base_url = str(request.base_url).rstrip('/')
    
    # Build the agent card following A2A spec
    agent_card = {
        # Note: 'agentId' is not in the official spec - the field is just 'name'
        "name": "Signals Activation Agent", 
        "description": "AI agent for discovering and activating audience signals",
        "version": "1.0.0",
        "url": base_url,  # Dynamic URL based on request
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "capabilities": {  # Required by spec - using fields from AgentCapabilities
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
            "extensions": []
        },
        "skills": [
            {
                "id": "discovery",
                "name": "Signal Discovery",
                "description": "Discover audience signals using natural language",
                "tags": ["search", "discovery", "audience", "signals"],
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query for signal discovery"
                        },
                        "deliver_to": {
                            "type": "object",
                            "description": "Delivery specification"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return"
                        },
                        "principal_id": {
                            "type": "string",
                            "description": "Principal identifier for access control"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "id": "activation",
                "name": "Signal Activation",
                "description": "Activate a signal on a platform",
                "tags": ["activation", "deployment", "platform", "signals"],
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "signal_id": {
                            "type": "string",
                            "description": "ID of the signal to activate"
                        },
                        "platform": {
                            "type": "string",
                            "description": "Target platform for activation"
                        },
                        "account": {
                            "type": "string",
                            "description": "Platform account identifier"
                        },
                        "context_id": {
                            "type": "string",
                            "description": "Context ID from discovery"
                        }
                    },
                    "required": ["signal_id", "platform"]
                }
            }
        ]
    }
    
    # Add optional fields that help with discovery
    agent_card["protocolVersion"] = "0.2"  # A2A protocol version
    agent_card["provider"] = {
        "organization": "Signals Agent Team",  # Required field per A2A spec
        "url": base_url
    }
    
    # If we have the official types, validate the card
    if A2A_TYPES_AVAILABLE:
        try:
            # Validate using official AgentCard type
            validated = AgentCard(**agent_card)
            return validated.model_dump(exclude_none=True)
        except Exception as e:
            logger.warning(f"Agent card validation failed: {e}")
            # Return unvalidated card if validation fails
    
    return agent_card


@app.post("/a2a/task")
async def handle_a2a_task(request: Dict[str, Any]):
    """Handle A2A task requests following the official spec."""
    # Extract task metadata
    task_id = request.get("taskId") or f"task_{datetime.now().timestamp()}"
    task_type = request.get("type")
    context_id = request.get("contextId")
    
    # Handle both standard A2A format (with parameters) and simplified format
    if "parameters" in request:
        params = request.get("parameters", {})
    else:
        # For simplified format, treat the whole request as parameters
        params = {k: v for k, v in request.items() if k not in ["taskId", "type", "contextId"]}
    
    try:
        if task_type == "discovery":
            # Convert to internal format
            # Support 'query' at root level or in parameters
            query = params.get("query", request.get("query", ""))
            
            # Use AI to analyze query intent
            intent_analysis = analyze_query_intent(query, context_id)
            
            # If this is a contextual query, retrieve and use previous context
            if intent_analysis.get('is_contextual') and context_id:
                # Try to retrieve the previous context from database
                import sqlite3
                conn = sqlite3.connect('signals_agent.db', timeout=30.0)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT metadata FROM contexts 
                    WHERE context_id = ? AND context_type = 'discovery'
                """, (context_id,))
                
                context_result = cursor.fetchone()
                conn.close()
                
                if context_result:
                    # Parse the stored metadata
                    import json as json_lib
                    metadata = json_lib.loads(context_result['metadata'])
                    original_query = metadata.get('query', '')
                    signal_ids = metadata.get('signal_ids', [])
                    
                    # Now perform a new search with the original query to get fresh data
                    # This ensures we have the latest information
                    internal_request = GetSignalsRequest(
                        signal_spec=original_query,  # Use original query, not the follow-up
                        deliver_to=params.get("deliver_to", {"platforms": "all", "countries": ["US"]}),
                        filters=params.get("filters"),
                        max_results=params.get("max_results", 10),
                        principal_id=params.get("principal_id")
                    )
                    
                    # Call business logic with original query
                    response = main.get_signals.fn(
                        signal_spec=internal_request.signal_spec,
                        deliver_to=internal_request.deliver_to,
                        filters=internal_request.filters,
                        max_results=internal_request.max_results,
                        principal_id=internal_request.principal_id
                    )
                    
                    # Convert response objects to dictionaries for AI processing
                    signals_dict = [signal.model_dump() for signal in response.signals]
                    custom_dict = [proposal.model_dump() for proposal in response.custom_segment_proposals] if response.custom_segment_proposals else None
                    
                    # Use AI to generate contextual response
                    text_response = generate_contextual_response(
                        follow_up_query=query,
                        original_query=original_query,
                        signals=signals_dict,
                        custom_proposals=custom_dict
                    )
                    
                    # Build response with contextual information
                    parts = [{
                        "kind": "text",
                        "text": text_response
                    }]
                    
                    # Also include the data part with full response
                    parts.append({
                        "kind": "data",
                        "data": response.model_dump()
                    })
                    
                    status_message = {
                        "kind": "message",
                        "message_id": f"msg_{datetime.now().timestamp()}",
                        "parts": parts,
                        "role": "agent"
                    }
                    
                    task_response = {
                        "id": task_id,
                        "kind": "task",
                        "contextId": context_id,  # Preserve the existing context_id for continuity
                        "status": {
                            "state": "completed",
                            "timestamp": datetime.now().isoformat(),
                            "message": status_message
                        },
                        "metadata": {
                            "response_type": "contextual_response",
                            "original_query": original_query,
                            "signal_count": len(response.signals),
                            "focus_area": intent_analysis.get('focus_area', 'general'),
                            "ai_reasoning": intent_analysis.get('reasoning', '')
                        }
                    }
                    
                    return task_response
                else:
                    # Context not found or expired, fall through to regular search
                    logger.warning(f"Context {context_id} not found or query not contextual, performing new search")
            
            # Not a contextual query or no context found - perform regular search
            internal_request = GetSignalsRequest(
                signal_spec=query,
                deliver_to=params.get("deliver_to", {"platforms": "all", "countries": ["US"]}),
                filters=params.get("filters"),
                max_results=params.get("max_results", 10),
                principal_id=params.get("principal_id")
            )
            
            # Call business logic
            response = main.get_signals.fn(
                signal_spec=internal_request.signal_spec,
                deliver_to=internal_request.deliver_to,
                filters=internal_request.filters,
                max_results=internal_request.max_results,
                principal_id=internal_request.principal_id
            )
            
            # Build A2A SDK-compliant response
            # Create parts for the message
            parts = []
            if response.message:
                parts.append({
                    "kind": "text",
                    "text": response.message
                })
            
            # Add data part with structured response
            parts.append({
                "kind": "data",
                "data": response.model_dump()
            })
            
            # Create the status message
            status_message = {
                "kind": "message",
                "message_id": f"msg_{datetime.now().timestamp()}",
                "parts": parts,
                "role": "agent"
            }
            
            # Build the task response with proper status structure
            # For new queries, use the existing context_id if provided, otherwise use the new one from response
            # This maintains conversation continuity when context_id is passed
            final_context_id = context_id if context_id else response.context_id
            
            task_response = {
                "id": task_id,
                "kind": "task",
                "contextId": final_context_id,
                "status": {
                    "state": "completed",  # Using TaskState enum value
                    "timestamp": datetime.now().isoformat(),
                    "message": status_message
                },
                "metadata": {
                    "signal_count": len(response.signals),
                    "context_id": final_context_id
                }
            }
            
            return task_response
            
        elif task_type == "activation":
            # Convert to internal format
            internal_request = ActivateSignalRequest(
                signals_agent_segment_id=params.get("signal_id", ""),
                platform=params.get("platform", ""),
                account=params.get("account"),
                context_id=params.get("context_id") or context_id
            )
            
            # Call business logic
            response = main.activate_signal.fn(
                signals_agent_segment_id=internal_request.signals_agent_segment_id,
                platform=internal_request.platform,
                account=internal_request.account,
                context_id=internal_request.context_id
            )
            
            # Build A2A SDK-compliant response
            # Determine state based on our status
            task_state = "completed" if response.status == "deployed" else "working"
            
            # Create parts for the message
            parts = []
            if response.message:
                parts.append({
                    "kind": "text",
                    "text": response.message
                })
            
            # Add data part with structured response
            parts.append({
                "kind": "data",
                "data": response.model_dump()
            })
            
            # Create the status message
            status_message = {
                "kind": "message",
                "message_id": f"msg_{datetime.now().timestamp()}",
                "parts": parts,
                "role": "agent"
            }
            
            # Build the task response with proper status structure
            task_response = {
                "id": task_id,
                "kind": "task",
                "contextId": context_id or response.context_id,
                "status": {
                    "state": task_state,
                    "timestamp": datetime.now().isoformat(),
                    "message": status_message
                },
                "metadata": {
                    "activation_status": response.status,
                    "platform": internal_request.platform
                }
            }
            
            return task_response
            
        else:
            # Unknown or missing task type
            error_message = f"Unknown or missing task type: {task_type}"
            logger.warning(error_message)
            return {
                "id": task_id,
                "kind": "task",
                "status": "Failed",
                "contextId": context_id,
                "status": {
                    "state": "failed",
                    "timestamp": datetime.now().isoformat(),
                    "message": {
                        "kind": "message",
                        "message_id": f"msg_{datetime.now().timestamp()}",
                        "parts": [{
                            "kind": "text",
                            "text": error_message
                        }],
                        "role": "agent"
                    }
                },
                "metadata": {
                    "error_code": -32602,
                    "error_message": error_message
                }
            }
            
    except HTTPException as he:
        # Pass through HTTP exceptions
        raise he
    except Exception as e:
        logger.error(f"Task failed: {e}")
        # Return A2A-compliant error response with numeric code
        return {
            "id": task_id,
            "kind": "task",
            "status": "Failed",  # Proper A2A status
            "contextId": context_id,
            "status": {
                "state": "failed",
                "timestamp": datetime.now().isoformat(),
                "message": {
                    "kind": "message",
                    "message_id": f"msg_{datetime.now().timestamp()}",
                    "parts": [{
                        "kind": "text",
                        "text": str(e)
                    }],
                    "role": "agent"
                }
            },
            "metadata": {
                "error_code": -32603,
                "error_message": str(e)
            }
        }


# ===== MCP Protocol Endpoints =====

@app.get("/mcp")
@app.get("/mcp/")
async def mcp_discovery():
    """Return MCP server information for discovery."""
    return {
        "mcp_version": "1.0",
        "server_name": "audience-agent",
        "server_version": "1.0.0",
        "capabilities": {
            "tools": True,
            "resources": False,
            "prompts": False
        }
    }

@app.post("/mcp")
@app.post("/mcp/")
async def handle_mcp_request(request: Request):
    """Handle MCP JSON-RPC requests over HTTP."""
    try:
        # Get JSON-RPC request
        json_rpc = await request.json()
        
        method = json_rpc.get("method")
        params = json_rpc.get("params", {})
        request_id = json_rpc.get("id")
        
        # Route to appropriate handler
        if method == "initialize":
            # Handle MCP initialization
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "audience-agent",
                    "version": "1.0.0"
                }
            }
            
        elif method == "tools/list":
            # Return available tools
            result = {
                "tools": [
                    {
                        "name": "get_signals",
                        "description": "Discover relevant signals",
                        "inputSchema": main.get_signals.parameters
                    },
                    {
                        "name": "activate_signal", 
                        "description": "Activate a signal",
                        "inputSchema": main.activate_signal.parameters
                    }
                ]
            }
            
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_params = params.get("arguments", {})
            
            if tool_name == "get_signals":
                # Validate and convert deliver_to dict to proper object
                from schemas import DeliverySpecification
                from pydantic import ValidationError
                
                try:
                    # Handle missing deliver_to - provide default
                    if 'deliver_to' not in tool_params:
                        tool_params['deliver_to'] = DeliverySpecification(
                            platforms='all',
                            countries=['US']
                        )
                    elif isinstance(tool_params['deliver_to'], dict):
                        # Try to create DeliverySpecification directly
                        tool_params['deliver_to'] = DeliverySpecification(**tool_params['deliver_to'])
                    
                    result = main.get_signals.fn(**tool_params)
                    
                except ValidationError as e:
                    # Return helpful error message with expected format
                    error_details = []
                    for error in e.errors():
                        field = '.'.join(str(x) for x in error['loc'])
                        error_details.append(f"  - {field}: {error['msg']}")
                    
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32602,
                            "message": "Invalid parameters for deliver_to",
                            "data": {
                                "validation_errors": error_details,
                                "expected_format": {
                                    "deliver_to": {
                                        "platforms": "all | [{platform: string, account?: string}, ...]",
                                        "countries": ["US", "UK", "CA", "..."]
                                    }
                                },
                                "examples": [
                                    {
                                        "description": "Search all platforms",
                                        "deliver_to": {
                                            "platforms": "all",
                                            "countries": ["US"]
                                        }
                                    },
                                    {
                                        "description": "Search specific platform",
                                        "deliver_to": {
                                            "platforms": [{"platform": "index-exchange"}],
                                            "countries": ["US"]
                                        }
                                    },
                                    {
                                        "description": "Platform with account",
                                        "deliver_to": {
                                            "platforms": [{"platform": "index-exchange", "account": "123456"}],
                                            "countries": ["US", "UK"]
                                        }
                                    }
                                ]
                            }
                        },
                        "id": request_id
                    })
            elif tool_name == "activate_signal":
                result = main.activate_signal.fn(**tool_params)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
                
            # Convert response to dict
            result = result.model_dump() if hasattr(result, 'model_dump') else result
            
        else:
            raise ValueError(f"Unknown method: {method}")
            
        # Return JSON-RPC response
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id
        })
        
    except Exception as e:
        logger.error(f"MCP request failed: {e}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": str(e)
            },
            "id": request_id if 'request_id' in locals() else None
        })


@app.get("/mcp/sse")
async def mcp_sse_endpoint():
    """MCP Server-Sent Events endpoint for streaming."""
    async def event_generator():
        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connection', 'status': 'connected'})}\n\n"
        
        # Keep connection alive
        while True:
            await asyncio.sleep(30)
            yield f": keepalive\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ===== Health Check =====

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "protocols": ["mcp", "a2a"],
        "timestamp": datetime.now().isoformat()
    }


# ===== Main =====

def run_unified_server(host: str = "localhost", port: int = 8000):
    """Run the unified server supporting both protocols."""
    logger.info(f"Starting Unified Server on {host}:{port}")
    logger.info(f"- A2A Agent Card: http://{host}:{port}/agent-card")
    logger.info(f"- A2A Tasks: http://{host}:{port}/a2a/task")
    logger.info(f"- MCP Endpoint: http://{host}:{port}/mcp")
    logger.info(f"- MCP SSE: http://{host}:{port}/mcp/sse")
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    run_unified_server()