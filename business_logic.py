"""Core business logic for the Signals Agent.

This module contains the actual implementation of discovery and activation tasks,
independent of any protocol (A2A, MCP, etc.).
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

# import main  # Removed to avoid module-level execution during import
from schemas import (
    GetSignalsResponse,
    DeliverySpecification,
    SignalFilters,
    ActivateSignalResponse,
    CustomSegmentProposal
)

# Test mode detection
import os
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

if TEST_MODE:
    from test_helpers import MockGeminiModel
    model = MockGeminiModel()
else:
    try:
        import google.generativeai as genai
        from config_loader import load_config
        config = load_config()
        api_key = config.get('gemini_api_key', '')
        
        # Check if API key is a placeholder
        if not api_key or api_key == 'your-gemini-api-key-here':
            # Use mock model if no valid API key
            from test_helpers import MockGeminiModel
            model = MockGeminiModel()
        else:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
    except Exception as e:
        # Fallback to mock model on any error
        from test_helpers import MockGeminiModel
        model = MockGeminiModel()

# Store for conversation history
conversations: Dict[str, List[Dict[str, Any]]] = {}


def process_discovery_query(
    query: str,
    context_id: Optional[str] = None,
    deliver_to: Optional[DeliverySpecification] = None,
    filters: Optional[SignalFilters] = None,
    max_results: int = 10,
    principal_id: Optional[str] = None
) -> Dict[str, Any]:
    """Process a discovery query and return structured results.
    
    Returns a dict with:
    - signals: List of discovered signals
    - custom_proposals: List of custom segment proposals
    - message: Human-readable summary
    - context_id: Session context ID
    - ai_intent: The AI's interpretation of the query
    """
    
    # Get or create context ID
    if not context_id:
        context_id = f"ctx_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # Get conversation history
    history = conversations.get(context_id, [])
    
    # Let AI process the query
    ai_intent = _ai_process_query(query, context_id, history)
    
    # Use AI's refined search query
    search_query = ai_intent.get("search_query", query)
    
    # Default delivery specification
    if not deliver_to:
        deliver_to = DeliverySpecification(platforms="all", countries=["US"])
    
    # Use core logic directly to avoid importing main with its module-level initialization
    from core_logic import get_signals_core
    
    # Perform the actual search
    response = get_signals_core(
        signal_spec=search_query,
        deliver_to=deliver_to,
        filters=filters,
        max_results=max_results,
        principal_id=principal_id,
        context_id=context_id
    )
    
    # Generate AI message
    message_text = _ai_generate_message(query, response, ai_intent)
    
    # Store in conversation history
    conversations[context_id] = history + [{
        "query": query,
        "response": message_text,
        "timestamp": datetime.utcnow().isoformat()
    }]
    
    return {
        "signals": response.signals,
        "custom_proposals": response.custom_segment_proposals,
        "message": message_text,
        "context_id": context_id,
        "ai_intent": ai_intent
    }


def process_activation(
    segment_id: str,
    platform: str,
    account: Optional[str] = None,
    principal_id: Optional[str] = None,
    context_id: Optional[str] = None
) -> ActivateSignalResponse:
    """Process a signal activation request."""
    
    # Use core logic directly to avoid importing main with its module-level initialization
    from core_logic import activate_signal_core
    
    return activate_signal_core(
        signals_agent_segment_id=segment_id,
        platform=platform,
        account=account,
        principal_id=principal_id,
        context_id=context_id
    )


def _ai_process_query(query: str, context_id: str, history: List[Dict]) -> Dict[str, Any]:
    """Use AI to understand query intent."""
    
    prompt = f"""
    Analyze this query and determine the user's intent.
    
    Query: {query}
    Context ID: {context_id}
    Previous conversation: {json.dumps(history[-3:]) if history else "None"}
    
    Return a JSON object with:
    {{
        "is_contextual": boolean (is this a follow-up question?),
        "search_query": "refined search terms if needed",
        "intent": "discovery|contextual|clarification",
        "key_terms": ["list", "of", "key", "terms"]
    }}
    """
    
    response = model.generate_content(prompt)
    return json.loads(response.text.strip().replace("```json", "").replace("```", ""))


def _ai_generate_message(query: str, results: GetSignalsResponse, ai_intent: Dict[str, Any]) -> str:
    """Generate a human-readable message for the results."""
    
    # Prepare summaries
    signals_summary = [{
        "name": s.name,
        "coverage": s.coverage_percentage,
        "cpm": s.pricing.cpm if s.pricing else None,
        "provider": s.data_provider
    } for s in results.signals[:5]]
    
    custom_summary = [{
        "name": p.proposed_name,
        "rationale": p.creation_rationale
    } for p in (results.custom_segment_proposals or [])[:3]]
    
    prompt = f"""
    Generate a helpful response for this query.
    
    Query: {query}
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