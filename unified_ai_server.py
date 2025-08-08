#!/usr/bin/env python3
"""Simplified AI-driven unified server - no fallback logic, just AI."""

import asyncio
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import google.generativeai as genai

from schemas import GetSignalsRequest, GetSignalsResponse
from database import init_db
from config_loader import load_config
import main

logger = logging.getLogger(__name__)

# Initialize Gemini - NO FALLBACK
config = load_config()
genai.configure(api_key=config.get("gemini_api_key"))
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Simple in-memory conversation store (use database in production)
conversations = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    init_db()
    yield


app = FastAPI(
    title="AI-Driven Signals Agent",
    description="Pure AI-driven signal discovery",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def ai_understand_query(query: str, context_id: Optional[str]) -> Dict[str, Any]:
    """Let AI understand everything about this query."""
    
    # Get conversation history
    history = conversations.get(context_id, []) if context_id else []
    
    prompt = f"""
    You are an intelligent audience discovery assistant. Analyze this query:
    
    Query: "{query}"
    
    Previous conversation (last 3 exchanges):
    {json.dumps(history[-3:], indent=2) if history else "None"}
    
    Determine:
    1. What is the user really asking for?
    2. If they have previous context, are they asking about those results or searching for something new?
    3. What should we search for in our database?
    
    Return JSON:
    {{
        "intent": "search|details|clarification",
        "search_query": "what to actually search for (could be from history or new)",
        "focus": "what aspect they care about",
        "reasoning": "your understanding"
    }}
    """
    
    response = model.generate_content(prompt)
    return json.loads(response.text.strip().replace("```json", "").replace("```", ""))


def ai_generate_response(
    original_query: str,
    intent: Dict[str, Any],
    search_results: GetSignalsResponse,
    history: List[Dict[str, Any]]
) -> str:
    """Let AI generate the perfect response."""
    
    prompt = f"""
    Generate the perfect response for this user query.
    
    User asked: "{original_query}"
    Intent analysis: {json.dumps(intent, indent=2)}
    
    Search results:
    - {len(search_results.signals)} signals found
    - {len(search_results.custom_segment_proposals or [])} custom proposals available
    - Coverage range: {min([s.coverage_percentage for s in search_results.signals] or [0]):.1f}% - {max([s.coverage_percentage for s in search_results.signals] or [0]):.1f}%
    - Price range: ${min([s.pricing.cpm for s in search_results.signals] or [0]):.2f} - ${max([s.pricing.cpm for s in search_results.signals] or [0]):.2f}
    
    Top signals:
    {json.dumps([{
        "name": s.name,
        "coverage": s.coverage_percentage,
        "cpm": s.pricing.cpm,
        "provider": s.data_provider,
        "platforms": [d.platform for d in s.deployments if d.is_live]
    } for s in search_results.signals[:3]], indent=2)}
    
    Custom proposals:
    {json.dumps([{
        "name": p.name,
        "rationale": p.rationale
    } for p in (search_results.custom_segment_proposals or [])[:3]], indent=2)}
    
    Conversation context: {len(history)} previous exchanges
    
    Create a response that:
    - Directly answers what they're asking
    - Feels natural and conversational
    - Provides the right level of detail
    - Mentions custom segments if relevant
    - Is concise (2-3 sentences ideal, max 1 paragraph)
    
    Just return the text response, no formatting.
    """
    
    response = model.generate_content(prompt)
    return response.text.strip()


@app.post("/")
@app.post("/a2a/task")
async def handle_query(request: Dict[str, Any]):
    """Single endpoint - AI handles everything."""
    
    # Extract basics
    task_id = request.get("taskId", f"task_{datetime.now().timestamp()}")
    context_id = request.get("contextId")
    
    # Get the query - could be in various places
    params = request.get("parameters", {})
    query = params.get("query") or request.get("query", "")
    
    # Special handling for JSON-RPC format
    if "jsonrpc" in request and request.get("method") == "message/send":
        params = request.get("params", {})
        message = params.get("message", {})
        for part in message.get("parts", []):
            if part.get("kind") == "text":
                query = part.get("text", "")
                break
        context_id = params.get("contextId", context_id)
    
    # Let AI understand the query
    intent = ai_understand_query(query, context_id)
    
    # Perform the search based on AI's understanding
    search_query = intent.get("search_query", query)
    
    # Search for signals
    response = main.get_signals.fn(
        signal_spec=search_query,
        deliver_to=params.get("deliver_to", {"platforms": "all", "countries": ["US"]}),
        filters=params.get("filters"),
        max_results=params.get("max_results", 10),
        principal_id=params.get("principal_id"),
        context_id=context_id
    )
    
    # Get conversation history
    history = conversations.get(context_id, []) if context_id else []
    
    # Generate AI response
    message_text = ai_generate_response(query, intent, response, history)
    
    # Store in conversation history
    if not context_id:
        context_id = response.context_id
    
    if context_id not in conversations:
        conversations[context_id] = []
    
    conversations[context_id].append({
        "query": query,
        "search_query": search_query,
        "response": message_text,
        "signals_found": len(response.signals)
    })
    
    # Build response in A2A format
    message_parts = [
        {
            "kind": "text",
            "text": message_text
        },
        {
            "kind": "data",
            "data": response.model_dump()
        }
    ]
    
    # Return A2A task response
    return {
        "id": task_id,
        "kind": "task",
        "contextId": context_id,
        "status": {
            "state": "completed",
            "timestamp": datetime.now().isoformat(),
            "message": {
                "kind": "message",
                "message_id": f"msg_{datetime.now().timestamp()}",
                "parts": message_parts,
                "role": "agent"
            }
        },
        "metadata": {
            "intent": intent,
            "signal_count": len(response.signals),
            "has_custom_proposals": bool(response.custom_segment_proposals)
        }
    }


@app.get("/agent-card")
@app.get("/.well-known/agent.json")
async def get_agent_card(request: Request):
    """Simple agent card."""
    base_url = str(request.base_url).rstrip('/')
    
    return {
        "name": "AI Signals Agent",
        "description": "Pure AI-driven audience discovery",
        "version": "2.0.0",
        "url": base_url,
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False
        },
        "skills": [{
            "id": "discover",
            "name": "Discover Audiences",
            "description": "Natural language audience discovery powered by AI"
        }]
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "ai": "enabled"}


def run_ai_server(host: str = "localhost", port: int = 8000):
    """Run the pure AI server."""
    logger.info(f"Starting AI-Driven Server on {host}:{port}")
    logger.info("No fallback logic - pure AI intelligence")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_ai_server()