"""MCP Protocol Facade.

This module implements the MCP (Model Context Protocol) using FastAPI,
delegating business logic to the business_logic module.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
import logging

import business_logic
from schemas import DeliverySpecification, SignalFilters

router = APIRouter()
logger = logging.getLogger(__name__)


@router.options("/mcp")
async def handle_mcp_options():
    """Handle CORS preflight for MCP endpoint."""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept",
            "Access-Control-Allow-Credentials": "true"
        }
    )


@router.post("/mcp")
async def handle_mcp_request(request: Dict[str, Any]):
    """Handle MCP JSON-RPC requests."""
    
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")
    
    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "signals-agent",
                    "version": "2.0.0"
                },
                "capabilities": {
                    "tools": True,
                    "prompts": False
                }
            }
        
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "discover",
                        "description": "Discover audience segments matching your targeting needs",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "signal_spec": {
                                    "type": "string",
                                    "description": "Natural language description of your target signals"
                                },
                                "deliver_to": {
                                    "type": "object",
                                    "description": "Where to search for/deliver signals",
                                    "properties": {
                                        "platforms": {
                                            "type": "string",
                                            "enum": ["all"],
                                            "default": "all"
                                        },
                                        "countries": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "default": ["US"]
                                        }
                                    }
                                },
                                "filters": {
                                    "type": "object",
                                    "description": "Optional filters"
                                },
                                "max_results": {
                                    "type": "number",
                                    "default": 10
                                },
                                "principal_id": {
                                    "type": "string",
                                    "description": "Principal ID for private catalogs"
                                }
                            },
                            "required": ["signal_spec", "deliver_to"]
                        }
                    },
                    {
                        "name": "activate",
                        "description": "Activate a signal for use on a specific platform",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "signals_agent_segment_id": {
                                    "type": "string",
                                    "description": "The segment ID from discovery results"
                                },
                                "platform": {
                                    "type": "string",
                                    "description": "Platform identifier (e.g., 'index-exchange')"
                                },
                                "account": {
                                    "type": "string",
                                    "description": "Optional account ID"
                                },
                                "principal_id": {
                                    "type": "string",
                                    "description": "Principal ID"
                                },
                                "context_id": {
                                    "type": "string",
                                    "description": "Context ID from discovery"
                                }
                            },
                            "required": ["signals_agent_segment_id", "platform"]
                        }
                    }
                ]
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if tool_name == "discover":
                # Extract arguments
                signal_spec = tool_args.get("signal_spec", "")
                deliver_to = tool_args.get("deliver_to", {"platforms": "all", "countries": ["US"]})
                filters = tool_args.get("filters")
                max_results = tool_args.get("max_results", 10)
                principal_id = tool_args.get("principal_id")
                
                logger.info(f"MCP discover: signal_spec='{signal_spec}', max_results={max_results}")
                
                # Parse delivery specification
                delivery = DeliverySpecification(
                    platforms=deliver_to.get("platforms", "all"),
                    countries=deliver_to.get("countries", ["US"])
                )
                
                # Parse filters if provided
                filter_obj = None
                if filters:
                    filter_obj = SignalFilters(**filters)
                
                # Call business logic
                response = business_logic.process_discovery_query(
                    query=signal_spec,
                    deliver_to=delivery,
                    filters=filter_obj,
                    max_results=max_results,
                    principal_id=principal_id
                )
                
                # Format response
                signals_data = []
                for s in response["signals"][:5]:
                    signal_info = {
                        "name": s.name,
                        "id": s.signals_agent_segment_id,
                        "coverage": f"{s.coverage_percentage}%" if s.coverage_percentage else "Unknown",
                        "cpm": f"${s.pricing.cpm}" if s.pricing and s.pricing.cpm else "Unknown"
                    }
                    signals_data.append(signal_info)
                
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Found {len(response['signals'])} audience segments matching '{signal_spec}'. "
                                   f"Here are the top results:\n\n" +
                                   "\n".join([f"{i+1}. {s['name']} - Coverage: {s['coverage']}, CPM: {s['cpm']}" 
                                            for i, s in enumerate(signals_data)])
                        }
                    ],
                    "isError": False
                }
            
            elif tool_name == "activate":
                # Extract arguments
                segment_id = tool_args.get("signals_agent_segment_id")
                platform = tool_args.get("platform")
                account = tool_args.get("account")
                principal_id = tool_args.get("principal_id")
                context_id = tool_args.get("context_id")
                
                logger.info(f"MCP activate: segment_id='{segment_id}', platform='{platform}'")
                
                # Call business logic
                activation_response = business_logic.process_activation(
                    segment_id=segment_id,
                    platform=platform,
                    account=account,
                    principal_id=principal_id,
                    context_id=context_id
                )
                
                # Format response
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Signal activation initiated:\n"
                                   f"- Signal ID: {activation_response.signals_agent_segment_id}\n"
                                   f"- Platform: {activation_response.platform}\n"
                                   f"- Status: {activation_response.status}\n"
                                   f"- Context ID: {activation_response.context_id}"
                        }
                    ],
                    "isError": False
                }
            
            else:
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                        "id": request_id
                    },
                    status_code=200,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Credentials": "true"
                    }
                )
        
        else:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": request_id
                },
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Credentials": "true"
                }
            )
        
        # Return successful result
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "true"
            }
        )
        
    except Exception as e:
        logger.error(f"MCP error: {e}", exc_info=True)
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": request_id
            },
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "true"
            }
        )