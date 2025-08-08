"""Unified handler for all queries using conversation history."""

import json
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from config_loader import load_config
from schemas import GetSignalsRequest, GetSignalsResponse

# Load config and initialize Gemini
config = load_config()
api_key = config.get("gemini_api_key", "your-api-key-here")

if api_key and api_key != "your-api-key-here":
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
else:
    model = None


def determine_query_intent(
    current_query: str,
    conversation_history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Use AI to determine the intent of the current query based on conversation history.
    
    Returns:
        Dict with:
        - is_follow_up: bool - Is this about previous results?
        - search_query: str - What to search for (original or new)
        - focus_area: str - What aspect to focus on
    """
    
    if not model:
        # Fallback: Simple keyword detection
        query_lower = current_query.lower()
        
        # Check if it's asking about previous results
        is_follow_up = any([
            "custom segment" in query_lower,
            "these" in query_lower,
            "those" in query_lower,
            "the audience" in query_lower,
            "the signal" in query_lower,
            "tell me more" in query_lower,
            "what about" in query_lower
        ]) and len(conversation_history) > 0
        
        if is_follow_up and conversation_history:
            # Use the original query from history
            last_search = conversation_history[-1].get("query", current_query)
            return {
                "is_follow_up": True,
                "search_query": last_search,
                "focus_area": "details",
                "reasoning": "Fallback detection"
            }
        
        return {
            "is_follow_up": False,
            "search_query": current_query,
            "focus_area": "new_search",
            "reasoning": "Fallback detection"
        }
    
    # Use AI to understand intent
    history_summary = json.dumps(conversation_history[-3:], indent=2) if conversation_history else "No previous queries"
    
    prompt = f"""
    Analyze this query in the context of the conversation:
    
    Current query: "{current_query}"
    
    Recent conversation history:
    {history_summary}
    
    Determine:
    1. Is this a follow-up question about previous results? (true/false)
    2. What should we search for? (the original query or the new query)
    3. What aspect is the user asking about? (signals, custom_segments, coverage, pricing, platforms, or new_search)
    
    Return as JSON:
    {{
        "is_follow_up": true/false,
        "search_query": "what to search for",
        "focus_area": "aspect",
        "reasoning": "brief explanation"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        clean_json = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        # Fallback to simple detection
        return determine_query_intent(current_query, conversation_history)


def generate_unified_response(
    query: str,
    signals: List[Any],
    custom_proposals: List[Any],
    conversation_history: List[Dict[str, Any]],
    intent: Dict[str, Any]
) -> str:
    """
    Generate a response that naturally handles both new searches and follow-ups.
    
    The response adapts based on intent and conversation history.
    """
    
    if not model:
        # Simple response generation
        if intent.get("is_follow_up") and intent.get("focus_area") == "custom_segments":
            if custom_proposals:
                response = f"Based on your search, here are {len(custom_proposals)} custom segment proposals:\n\n"
                for i, proposal in enumerate(custom_proposals[:3], 1):
                    name = proposal.get("name") or proposal.get("proposed_name", "Unknown")
                    rationale = proposal.get("rationale") or proposal.get("creation_rationale", "")
                    response += f"{i}. {name}\n"
                    if rationale:
                        response += f"   {rationale}\n\n"
                return response
            else:
                return "No custom segments were proposed for this search."
        
        # Default response for signals
        if signals:
            return f"Found {len(signals)} signal(s) matching your criteria."
        else:
            return "No signals found matching your criteria."
    
    # Use AI to generate natural response
    signals_data = [{"name": s.name, "coverage": s.coverage_percentage, "cpm": s.pricing.cpm} for s in signals[:5]]
    custom_data = [{"name": p.get("name"), "rationale": p.get("rationale")} for p in custom_proposals[:3]] if custom_proposals else []
    
    prompt = f"""
    Generate a helpful response for this audience discovery query.
    
    Query: "{query}"
    Intent: {json.dumps(intent)}
    Conversation history: {len(conversation_history)} previous exchanges
    
    Results found:
    - Signals: {json.dumps(signals_data, indent=2)}
    - Custom proposals: {json.dumps(custom_data, indent=2)}
    
    Create a natural, conversational response that:
    1. Directly addresses what the user is asking
    2. Provides relevant details based on their focus area
    3. Feels like a continuation of the conversation if it's a follow-up
    4. Is concise but informative (2-3 paragraphs max)
    
    Do not use markdown formatting, just plain text.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        # Fallback to simple response
        return generate_unified_response(query, signals, custom_proposals, conversation_history, intent)


class UnifiedQueryHandler:
    """Handles all queries with unified logic."""
    
    def __init__(self):
        self.conversation_store = {}  # In production, use database
    
    def handle_query(
        self,
        query: str,
        context_id: Optional[str] = None,
        **search_params
    ) -> Dict[str, Any]:
        """
        Handle any query - new search or follow-up.
        
        The handler:
        1. Retrieves conversation history if context_id exists
        2. Determines intent using AI or fallback logic
        3. Performs search (using original or new query as appropriate)
        4. Generates unified response considering context
        """
        
        # Get conversation history
        history = self.conversation_store.get(context_id, []) if context_id else []
        
        # Determine intent
        intent = determine_query_intent(query, history)
        
        # Get the appropriate search query
        search_query = intent.get("search_query", query)
        
        # Perform search (this would call main.get_signals)
        # For now, returning mock data
        signals = []  # Would be actual search results
        custom_proposals = []  # Would be actual proposals
        
        # Generate response considering history and intent
        response_text = generate_unified_response(
            query,
            signals,
            custom_proposals,
            history,
            intent
        )
        
        # Update conversation history
        if context_id:
            if context_id not in self.conversation_store:
                self.conversation_store[context_id] = []
            self.conversation_store[context_id].append({
                "query": query,
                "search_query": search_query,
                "intent": intent,
                "response": response_text
            })
        
        return {
            "message": response_text,
            "context_id": context_id,
            "intent": intent,
            "signals": signals,
            "custom_proposals": custom_proposals
        }