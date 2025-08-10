"""Core business logic for the Signals Agent.

This module contains the actual implementation of discovery and activation tasks,
independent of any protocol (A2A, MCP, etc.).
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import logging

# import main  # Removed to avoid module-level execution during import
from schemas import (
    GetSignalsResponse,
    DeliverySpecification,
    SignalFilters,
    ActivateSignalResponse,
    CustomSegmentProposal
)
from rate_limiter import gemini_rate_limiter

logger = logging.getLogger(__name__)

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
    principal_id: Optional[str] = None,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """Process a discovery query and return structured results.
    
    Returns a dict with:
    - signals: List of discovered signals
    - custom_proposals: List of custom segment proposals
    - message: Human-readable summary
    - context_id: Session context ID
    - ai_intent: The AI's interpretation of the query
    """
    
    # Use limit if provided, otherwise max_results
    if limit is not None:
        max_results = limit
    
    # Get or create context ID
    if not context_id:
        context_id = f"ctx_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # Get conversation history
    history = conversations.get(context_id, [])
    
    # Quick check for obvious contextual queries to avoid unnecessary AI calls
    contextual_keywords = [
        "tell me more", "more about", "these signals", "those signals",
        "the signals", "more details", "explain", "what about",
        "those segments", "these segments", "the segments",
        "previous", "last search", "custom segments", "tell me about"
    ]
    
    query_lower = query.lower()
    is_likely_contextual = any(keyword in query_lower for keyword in contextual_keywords)
    
    # If likely contextual and we have a context, try to handle without AI
    if is_likely_contextual and context_id:
        from core_logic import get_discovery_context, get_signals_by_ids
        prev_context = get_discovery_context(context_id)
        
        if prev_context and prev_context.get("signal_ids"):
            # This is definitely a contextual query - handle without AI
            signals = get_signals_by_ids(prev_context["signal_ids"])
            custom_proposals = prev_context.get("custom_proposals", [])
            
            # Create response with the same signals
            response = GetSignalsResponse(
                message=f"Here are more details about the {len(signals)} signals from your previous search",
                signals=signals,
                custom_segment_proposals=[CustomSegmentProposal(**p) for p in custom_proposals] if custom_proposals else None,
                context_id=context_id
            )
            
            # Generate a simple contextual message without AI
            signal_names = [s.name for s in signals[:3]]
            if "custom" in query_lower and custom_proposals:
                custom_names = [p.get("proposed_name", "Custom") if isinstance(p, dict) else p.proposed_name for p in custom_proposals[:2]]
                message_text = f"The custom segments I suggested are: {', '.join(custom_names)}. These combine multiple targeting criteria for better precision. The standard signals include {', '.join(signal_names)} and {len(signals)-3} others."
            else:
                message_text = f"The {len(signals)} signals I found include: {', '.join(signal_names)}. Each offers different coverage and pricing across multiple platforms. Would you like to activate any of these?"
            
            # Store in conversation history and return
            conversations[context_id] = history + [{
                "query": query,
                "response": message_text,
                "timestamp": datetime.utcnow().isoformat()
            }]
            
            response.message = message_text
            return response
    
    # For non-contextual or unclear queries, use AI
    ai_intent = _ai_process_query(query, context_id, history)
    
    # Check if AI determined this is contextual (but we didn't catch it above)
    if ai_intent.get("is_contextual", False) and context_id:
        # This is a follow-up question about previous results
        from core_logic import get_discovery_context, get_signals_by_ids
        
        # Get the previous context
        prev_context = get_discovery_context(context_id)
        
        if prev_context and prev_context.get("signal_ids"):
            # Retrieve the actual signals from the previous search
            signals = get_signals_by_ids(prev_context["signal_ids"])
            custom_proposals = prev_context.get("custom_proposals", [])
            
            # Create a response with the same signals but a contextual message
            response = GetSignalsResponse(
                message=f"Here are more details about the {len(signals)} signals from your previous search",
                signals=signals,
                custom_segment_proposals=[CustomSegmentProposal(**p) for p in custom_proposals] if custom_proposals else None,
                context_id=context_id
            )
            
            # Generate a contextual message that provides more details
            message_text = _generate_contextual_message(query, signals, custom_proposals, ai_intent)
        else:
            # No previous context found, fall back to new search
            ai_intent["is_contextual"] = False
            
    # If not contextual or no previous context, perform a new search
    if not ai_intent.get("is_contextual", False):
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
        
        # Generate AI message for new search results
        message_text = _ai_generate_message(query, response, ai_intent)
    
    # Store in conversation history
    conversations[context_id] = history + [{
        "query": query,
        "response": message_text,
        "timestamp": datetime.utcnow().isoformat()
    }]
    
    # Update the response message and return the response object (not a dict)
    response.message = message_text
    return response


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
    
    # Common contextual phrases
    contextual_indicators = [
        "tell me more", "more about", "details about", "explain",
        "what about", "how about", "these", "those", "that", "this",
        "the signal", "the segment", "the audience", "them"
    ]
    
    # Quick check for obvious contextual queries
    query_lower = query.lower()
    likely_contextual = any(phrase in query_lower for phrase in contextual_indicators)
    
    prompt = f"""
    Analyze this query and determine the user's intent.
    
    Query: {query}
    Has conversation history: {len(history) > 0}
    Likely contextual: {likely_contextual}
    
    Common contextual phrases found: {[p for p in contextual_indicators if p in query_lower]}
    
    Determine if this is:
    1. A follow-up question about previous results (contextual)
    2. A new search query (discovery)
    3. A clarification request
    
    Return a JSON object with:
    {{
        "is_contextual": boolean (true if asking about previous results),
        "search_query": "refined search terms ONLY if new search",
        "intent": "discovery|contextual|clarification",
        "key_terms": ["list", "of", "key", "terms"]
    }}
    
    Be aggressive about marking queries as contextual if they reference previous results.
    """
    
    # Apply rate limiting for Gemini API
    if not gemini_rate_limiter.acquire(timeout=5):
        logger.warning("Rate limit timeout for Gemini API")
        # Return a safe fallback response
        return {
            "is_contextual": False,
            "search_query": query,
            "intent": "discovery",
            "key_terms": query.lower().split()[:5]
        }
    
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text.strip().replace("```json", "").replace("```", ""))
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        # Return a safe fallback response
        return {
            "is_contextual": False,
            "search_query": query,
            "intent": "discovery", 
            "key_terms": query.lower().split()[:5]
        }


def _generate_contextual_message(query: str, signals: List, custom_proposals: List, ai_intent: Dict[str, Any]) -> str:
    """Generate a contextual response about previous results."""
    
    # Build detailed signal information
    signal_details = []
    for s in signals:
        detail = f"**{s.name}**: {s.description}"
        if s.coverage_percentage:
            detail += f" Coverage: {s.coverage_percentage}%."
        if s.pricing and s.pricing.cpm:
            detail += f" CPM: ${s.pricing.cpm}."
        if s.deployments:
            platforms = [d.platform for d in s.deployments]
            detail += f" Available on: {', '.join(platforms)}."
        signal_details.append(detail)
    
    # Build custom proposal details
    custom_details = []
    for p in custom_proposals:
        if isinstance(p, dict):
            custom_details.append(f"**{p.get('proposed_name', 'Custom')}**: {p.get('description', '')} - {p.get('creation_rationale', '')}")
        else:
            custom_details.append(f"**{p.proposed_name}**: {p.description} - {p.creation_rationale}")
    
    prompt = f"""
    The user is asking a follow-up question about signals they previously searched for.
    
    Previous signals found:
    {chr(10).join(signal_details[:3])}
    
    Custom segment proposals:
    {chr(10).join(custom_details[:2]) if custom_details else "None"}
    
    User's follow-up question: {query}
    
    Provide a helpful response that:
    - Directly answers their follow-up question
    - Provides more details about the signals
    - Mentions specific names, coverage, and pricing
    - Is conversational and helpful
    - Is 2-3 sentences max
    
    Return only the text, no formatting.
    """
    
    # Apply rate limiting for Gemini API
    if not gemini_rate_limiter.acquire(timeout=5):
        logger.warning("Rate limit timeout for Gemini API in message generation")
        # Return a safe fallback response based on context
        if 'signals' in locals():
            signal_names = [s.name for s in signals[:3]]
            return f"Here are more details about the {len(signals)} signals from your previous search, including {', '.join(signal_names)}."
        else:
            return "Processing your request. Please try again in a moment."
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API error in message generation: {e}")
        # Return a safe fallback response
        if 'signals' in locals():
            signal_names = [s.name for s in signals[:3]]
            return f"Found {len(signals)} relevant signals for your search."
        else:
            return "Processing your request. Please try again in a moment."


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
    
    # Apply rate limiting for Gemini API
    if not gemini_rate_limiter.acquire(timeout=5):
        logger.warning("Rate limit timeout for Gemini API in message generation")
        # Return a safe fallback response based on context
        if 'signals' in locals():
            signal_names = [s.name for s in signals[:3]]
            return f"Here are more details about the {len(signals)} signals from your previous search, including {', '.join(signal_names)}."
        else:
            return "Processing your request. Please try again in a moment."
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API error in message generation: {e}")
        # Return a safe fallback response
        if 'signals' in locals():
            signal_names = [s.name for s in signals[:3]]
            return f"Found {len(signals)} relevant signals for your search."
        else:
            return "Processing your request. Please try again in a moment."