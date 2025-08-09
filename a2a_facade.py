"""A2A Protocol Facade.

This module implements the A2A (Agent-to-Agent) protocol using FastAPI,
delegating business logic to the business_logic module.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import json
import asyncio

import business_logic
from schemas import DeliverySpecification

router = APIRouter()


def get_agent_card(base_url: str) -> Dict[str, Any]:
    """Generate the A2A agent card."""
    return {
        "name": "Signals Agent",
        "description": "AI-powered audience discovery and activation agent",
        "version": "2.0.0",
        "url": f"{base_url}/a2a/jsonrpc",  # Required field - points to JSON-RPC endpoint
        "protocolVersion": "a2a/v1",
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": False,
            "extensions": []
        },
        "skills": [{
            "id": "discover",
            "name": "Discover Audiences",
            "description": "Natural language audience discovery",
            "tags": ["search", "discovery", "audience", "signals"]
        }],
        "provider": {
            "name": "Scope3",
            "organization": "Scope3",
            "url": "https://scope3.com"
        }
    }


@router.get("/agent-card")
@router.get("/.well-known/agent.json")
@router.get("/.well-known/agent-card.json")
async def agent_card_endpoint(request: Request):
    """Return the A2A agent card."""
    # Use the proper base URL based on deployment
    forwarded_proto = request.headers.get('x-forwarded-proto', 'http')
    forwarded_host = request.headers.get('x-forwarded-host') or request.headers.get('host')
    
    if forwarded_host:
        base_url = f"{forwarded_proto}://{forwarded_host}"
    else:
        base_url = str(request.base_url).rstrip('/')
    
    return get_agent_card(base_url)


@router.post("/a2a/task")
async def handle_task(request: Dict[str, Any]):
    """Handle A2A task requests."""
    
    # Extract parameters
    query = request.get("query", "")
    context_id = request.get("contextId")
    
    # Generate task ID
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    
    try:
        # Process the discovery query
        result = business_logic.process_discovery_query(
            query=query,
            context_id=context_id
        )
        
        # Format signals for response
        signals_data = []
        for s in result["signals"][:5]:
            signal_info = {
                "name": s.name,
                "id": s.signals_agent_segment_id,
                "coverage": f"{s.coverage_percentage}%" if s.coverage_percentage else "Unknown",
                "cpm": f"${s.pricing.cpm}" if s.pricing and s.pricing.cpm else "Unknown",
                "provider": s.data_provider,
                "deployments": len(s.deployments)
            }
            signals_data.append(signal_info)
        
        # Format custom proposals
        custom_data = []
        for p in (result.get("custom_proposals") or [])[:3]:
            custom_data.append({
                "name": p.proposed_name,
                "description": p.description,
                "coverage": f"{p.estimated_coverage_percentage}%",
                "cpm": f"${p.estimated_cpm}",
                "id": p.custom_segment_id or f"custom_{uuid.uuid4().hex[:8]}"
            })
        
        # Build data part
        data_part = {
            "signals": signals_data,
            "custom_segments": custom_data if custom_data else None,
            "total_found": len(result["signals"])
        }
        
        # Build response
        return {
            "id": task_id,
            "kind": "task",
            "contextId": result["context_id"],
            "status": {
                "state": "completed",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "message": {
                    "kind": "message",
                    "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                    "parts": [
                        {"kind": "text", "text": result["message"]},
                        {"kind": "data", "data": data_part}
                    ],
                    "role": "agent"
                }
            }
        }
        
    except Exception as e:
        return {
            "id": task_id,
            "kind": "task",
            "status": {
                "state": "failed",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
        }


@router.post("/a2a/task/stream")
async def handle_task_stream(request: Dict[str, Any]):
    """Handle streaming A2A task requests."""
    
    query = request.get("query", "")
    context_id = request.get("contextId")
    
    async def stream_response():
        """Generate SSE stream."""
        # Initial status
        yield f"data: {json.dumps({'status': 'working', 'message': 'Processing your query...'})}\n\n"
        await asyncio.sleep(0.1)
        
        # Process query
        result = business_logic.process_discovery_query(
            query=query,
            context_id=context_id
        )
        
        # Stream results
        yield f"data: {json.dumps({'status': 'completed', 'message': result['message']})}\n\n"
        
        # Stream signal details
        for signal in result["signals"][:5]:
            yield f"data: {json.dumps({'signal': signal.name, 'coverage': signal.coverage_percentage})}\n\n"
            await asyncio.sleep(0.05)
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


async def _handle_json_rpc_request(request: Dict[str, Any]):
    """Internal handler for JSON-RPC message/send requests."""
    
    if request.get("jsonrpc") != "2.0":
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": request.get("id")
            },
            status_code=400
        )
    
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")
    
    if method == "message/send":
        # Extract message
        message = params.get("message", {})
        query = ""
        # Handle both direct parts and content.parts formats
        content = message.get("content", {})
        parts = content.get("parts", []) if content else message.get("parts", [])
        for part in parts:
            if part.get("type") == "text" or part.get("kind") == "text":
                query = part.get("text", "")
                break
        
        context_id = params.get("contextId")
        
        # Process query
        result = business_logic.process_discovery_query(
            query=query,
            context_id=context_id
        )
        
        # Build JSON-RPC response
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "result": {
                    "kind": "message",
                    "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                    "parts": [
                        {"kind": "text", "text": result["message"]}
                    ],
                    "role": "agent",
                    "contextId": result["context_id"]
                },
                "id": request_id
            }
        )
    
    return JSONResponse(
        content={
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "id": request_id
        },
        status_code=404
    )


@router.post("/a2a/jsonrpc")
async def handle_json_rpc(request: Dict[str, Any]):
    """Handle JSON-RPC message/send requests at dedicated endpoint."""
    return await _handle_json_rpc_request(request)


@router.post("/")
async def handle_json_rpc_root(request: Dict[str, Any]):
    """Handle JSON-RPC message/send requests at root for compatibility."""
    return await _handle_json_rpc_request(request)