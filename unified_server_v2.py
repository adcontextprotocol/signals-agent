#!/usr/bin/env python3
"""Unified server v2 - Simplified AI-driven approach with existing structure."""

import asyncio
import logging
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from schemas import GetSignalsRequest, GetSignalsResponse
from database import init_db
from config_loader import load_config
from adapters.manager import AdapterManager
import main

logger = logging.getLogger(__name__)

# Check if we're in test mode
TEST_MODE = os.environ.get("TEST_MODE", "").lower() == "true"

if TEST_MODE:
    # Use mock for testing
    from test_helpers import create_mock_genai_module
    genai = create_mock_genai_module()
    config = {"gemini_api_key": "test-key", "test_mode": True}
else:
    # Use real Gemini
    import google.generativeai as genai
    config = load_config()

# Initialize Gemini
genai.configure(api_key=config.get("gemini_api_key", ""))
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Simple conversation store
conversations = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    init_db()
    yield


app = FastAPI(
    title="Signals Agent Unified Server v2",
    description="AI-driven MCP and A2A protocols",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def ai_process_query(query: str, context_id: Optional[str], history: list) -> Dict[str, Any]:
    """AI processes the query and determines what to do."""
    
    prompt = f"""
    Analyze this audience discovery query:
    
    Query: "{query}"
    Has context: {bool(context_id)}
    Recent history: {json.dumps(history[-2:], indent=2) if history else "None"}
    
    Determine:
    1. What should we search for? (might be different from the query if it's a follow-up)
    2. What's the user's intent?
    
    Return JSON:
    {{
        "search_query": "what to search for",
        "intent": "discovery|details|comparison|pricing|platforms",
        "is_follow_up": true/false
    }}
    """
    
    response = model.generate_content(prompt)
    return json.loads(response.text.strip().replace("```json", "").replace("```", ""))


def ai_generate_message(query: str, results: GetSignalsResponse, ai_intent: Dict[str, Any]) -> str:
    """AI generates the response message."""
    
    # Prepare data for AI
    signals_summary = [{
        "name": s.name,
        "coverage": s.coverage_percentage,
        "cpm": s.pricing.cpm,
        "provider": s.data_provider
    } for s in results.signals[:5]]
    
    custom_summary = [{
        "name": p.name,
        "rationale": p.rationale
    } for p in (results.custom_segment_proposals or [])[:3]]
    
    prompt = f"""
    Generate a helpful response for this query.
    
    User asked: "{query}"
    AI Intent: {json.dumps(ai_intent)}
    
    Results:
    - Signals: {json.dumps(signals_summary)}
    - Custom proposals: {json.dumps(custom_summary)}
    
    Create a natural, conversational response that:
    - Directly answers their question
    - Mentions key details (coverage, pricing, platforms)
    - Notes custom segments if relevant
    - Is concise (2-3 sentences max)
    
    Return only the text, no formatting.
    """
    
    response = model.generate_content(prompt)
    return response.text.strip()


@app.post("/")
@app.post("/a2a/task")
async def handle_a2a_task(request: Dict[str, Any]):
    """Handle all A2A tasks with AI."""
    
    # Extract query and context
    task_id = request.get("taskId", f"task_{datetime.now().timestamp()}")
    context_id = request.get("contextId")
    
    # Handle different request formats
    if "jsonrpc" in request and request.get("method") == "message/send":
        # JSON-RPC format
        params = request.get("params", {})
        message = params.get("message", {})
        query = ""
        for part in message.get("parts", []):
            if part.get("kind") == "text":
                query = part.get("text", "")
                break
        context_id = params.get("contextId", context_id)
    else:
        # Standard A2A format
        params = request.get("parameters", {})
        query = params.get("query", request.get("query", ""))
    
    # Get conversation history
    history = conversations.get(context_id, []) if context_id else []
    
    # Let AI process the query
    ai_intent = ai_process_query(query, context_id, history)
    
    # Search based on AI's decision
    search_query = ai_intent.get("search_query", query)
    
    # Perform search
    response = main.get_signals.fn(
        signal_spec=search_query,
        deliver_to=params.get("deliver_to", {"platforms": "all", "countries": ["US"]}),
        filters=params.get("filters"),
        max_results=params.get("max_results", 10),
        principal_id=params.get("principal_id"),
        context_id=context_id
    )
    
    # Use response's context_id if we didn't have one
    if not context_id:
        context_id = response.context_id
    
    # Generate AI message
    message_text = ai_generate_message(query, response, ai_intent)
    
    # Update conversation history
    if context_id not in conversations:
        conversations[context_id] = []
    conversations[context_id].append({
        "query": query,
        "search": search_query,
        "response": message_text
    })
    
    # Build response
    response_data = {
        "id": task_id,
        "kind": "task",
        "contextId": context_id,
        "status": {
            "state": "completed",
            "timestamp": datetime.now().isoformat(),
            "message": {
                "kind": "message",
                "message_id": f"msg_{datetime.now().timestamp()}",
                "parts": [
                    {"kind": "text", "text": message_text},
                    {"kind": "data", "data": response.model_dump()}
                ],
                "role": "agent"
            }
        },
        "metadata": {
            "ai_intent": ai_intent,
            "signal_count": len(response.signals)
        }
    }
    
    # For JSON-RPC, wrap the response
    if "jsonrpc" in request:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": response_data["status"]["message"]
        }
    
    return response_data


@app.post("/mcp")
async def handle_mcp_request(request: Request):
    """Handle MCP requests with AI."""
    json_rpc = await request.json()
    method = json_rpc.get("method")
    params = json_rpc.get("params", {})
    request_id = json_rpc.get("id")
    
    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "audience-agent-v2", "version": "2.0.0"}
        }
    elif method == "tools/list":
        result = {
            "tools": [{
                "name": "discover",
                "description": "AI-powered audience discovery",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    }
                }
            }]
        }
    elif method == "tools/call":
        # Let AI handle it
        query = params.get("arguments", {}).get("query", "")
        context_id = params.get("arguments", {}).get("context_id")
        
        # Process with AI
        history = conversations.get(context_id, []) if context_id else []
        ai_intent = ai_process_query(query, context_id, history)
        
        # Search
        response = main.get_signals.fn(
            signal_spec=ai_intent.get("search_query", query),
            deliver_to={"platforms": "all", "countries": ["US"]},
            max_results=10,
            context_id=context_id
        )
        
        # Generate message
        message = ai_generate_message(query, response, ai_intent)
        response.message = message
        
        result = response.model_dump()
    else:
        result = {"error": f"Unknown method: {method}"}
    
    return JSONResponse({
        "jsonrpc": "2.0",
        "result": result,
        "id": request_id
    })


@app.get("/agent-card")
@app.get("/.well-known/agent.json")
async def get_agent_card(request: Request):
    """Return agent card."""
    base_url = str(request.base_url).rstrip('/')
    return {
        "name": "Signals Agent v2",
        "description": "AI-powered audience discovery",
        "version": "2.0.0",
        "protocolVersion": "a2a/v1",
        "url": base_url,
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False
        },
        "skills": [{
            "id": "discover",
            "name": "Discover Audiences",
            "description": "Natural language audience discovery",
            "tags": ["search", "discovery", "audience", "signals"]
        }],
        "provider": {
            "name": "Conductor",
            "url": "https://conductor.build"
        }
    }


@app.get("/health")
async def health_check():
    """Health check."""
    return {"status": "healthy", "version": "2.0", "ai": "enabled"}


def run_unified_server_v2(host: str = "localhost", port: int = 8000):
    """Run the simplified v2 server."""
    logger.info(f"Starting Unified Server v2 on {host}:{port}")
    logger.info("AI-driven, no complex branching")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_unified_server_v2()