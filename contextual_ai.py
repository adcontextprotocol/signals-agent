"""AI-powered contextual response generation using Gemini.

This module uses the Gemini API for intelligent response generation.
The API key is loaded from (in order of priority):
1. GEMINI_API_KEY environment variable (used in Fly.dev deployment)
2. config.json file (for local development)
3. Falls back to simpler responses if no key is available
"""

import json
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from config_loader import load_config

# Load config and initialize Gemini
# The config_loader automatically checks environment variables first
config = load_config()
api_key = config.get("gemini_api_key", "your-api-key-here")

# Only configure Gemini if we have a valid API key
if api_key and api_key != "your-api-key-here":
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
else:
    model = None  # Will trigger fallback behavior


def generate_contextual_response(
    follow_up_query: str,
    original_query: str,
    signals: List[Dict[str, Any]],
    custom_proposals: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Generate an intelligent contextual response using Gemini AI.
    
    Args:
        follow_up_query: The user's follow-up question
        original_query: The original search query
        signals: List of signals from the original search
        custom_proposals: Optional list of custom segment proposals
    
    Returns:
        A natural language response addressing the follow-up query
    """
    
    # Prepare signal data for the prompt
    signal_summaries = []
    for signal in signals[:5]:  # Limit to top 5 for context length
        summary = {
            "name": signal.get("name", "Unknown"),
            "description": signal.get("description", ""),
            "coverage": signal.get("coverage_percentage"),
            "cpm": signal.get("pricing", {}).get("cpm") if isinstance(signal.get("pricing"), dict) else None,
            "provider": signal.get("data_provider", "Unknown"),
            "platforms": [d.get("platform") for d in signal.get("deployments", []) if d.get("is_live")],
            "id": signal.get("signals_agent_segment_id")
        }
        signal_summaries.append(summary)
    
    # Prepare custom proposals if available
    custom_summaries = []
    if custom_proposals:
        for proposal in custom_proposals[:3]:  # Limit to top 3
            custom_summaries.append({
                "name": proposal.get("name"),
                "rationale": proposal.get("rationale"),
                "estimated_coverage": proposal.get("estimated_coverage_percentage"),
                "estimated_cpm": proposal.get("estimated_cpm"),
                "id": proposal.get("custom_segment_id")
            })
    
    prompt = f"""
    You are an expert audience targeting assistant helping a user understand their signal discovery results.
    
    CONTEXT:
    - Original search: "{original_query}"
    - User's follow-up question: "{follow_up_query}"
    
    DISCOVERED SIGNALS:
    {json.dumps(signal_summaries, indent=2)}
    
    {"CUSTOM SEGMENT PROPOSALS:" if custom_summaries else ""}
    {json.dumps(custom_summaries, indent=2) if custom_summaries else ""}
    
    Please provide a helpful, conversational response that:
    1. Directly addresses the user's follow-up question
    2. References specific signals or proposals when relevant
    3. Provides insights about coverage, pricing, or targeting strategy if asked
    4. Suggests next steps or alternatives if appropriate
    5. Is concise but informative (2-3 paragraphs max)
    
    Focus on being helpful and specific. If the user asks about "these signals" or "the audience", 
    refer to the actual signals found. If they ask about custom segments, explain those proposals.
    
    Do not use markdown formatting, just plain text with bullet points if needed.
    """
    
    try:
        if model:
            response = model.generate_content(prompt)
            return response.text.strip()
        else:
            # No API key configured, use fallback
            raise Exception("Gemini API key not configured")
    except Exception as e:
        # Fallback to a basic response if AI fails or is not configured
        fallback = f"Based on your search for '{original_query}', "
        
        if "custom" in follow_up_query.lower() and custom_summaries:
            fallback += f"I found {len(custom_summaries)} custom segment proposals that could be created. "
            fallback += "These are AI-generated audience combinations designed to better match your specific targeting needs. "
            for i, custom in enumerate(custom_summaries[:2], 1):
                fallback += f"\n\n{i}. {custom['name']}: {custom['rationale']}"
        else:
            fallback += f"I found {len(signal_summaries)} relevant signals. "
            if signal_summaries:
                top_signal = signal_summaries[0]
                fallback += f"\n\nThe top match is '{top_signal['name']}' "
                if top_signal.get('coverage'):
                    fallback += f"with {top_signal['coverage']:.1f}% coverage "
                if top_signal.get('cpm'):
                    fallback += f"at ${top_signal['cpm']:.2f} CPM "
                if top_signal.get('platforms'):
                    fallback += f"available on {', '.join(top_signal['platforms'])}"
        
        return fallback


def analyze_query_intent(follow_up_query: str, context_id: str) -> Dict[str, Any]:
    """
    Analyze the user's follow-up query to understand their intent.
    
    Returns:
        Dictionary with:
        - is_contextual: Whether this is a contextual follow-up
        - focus_area: What aspect they're asking about (signals, custom, pricing, coverage, etc.)
        - needs_fresh_data: Whether we should re-run the original search
    """
    
    prompt = f"""
    Analyze this follow-up query to understand the user's intent:
    Query: "{follow_up_query}"
    Context ID: {context_id if context_id else "None"}
    
    Determine:
    1. Is this a contextual follow-up to a previous search? (true/false)
    2. What is the focus area? (one of: signals, custom_segments, pricing, coverage, platforms, general)
    3. Do we need fresh data from a new search? (true/false)
    
    Return as JSON:
    {{
        "is_contextual": true/false,
        "focus_area": "string",
        "needs_fresh_data": true/false,
        "reasoning": "brief explanation"
    }}
    """
    
    try:
        if model:
            response = model.generate_content(prompt)
            clean_json = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(clean_json)
        else:
            # No API key configured, use fallback
            raise Exception("Gemini API key not configured")
    except Exception as e:
        # Fallback to keyword-based detection when AI is unavailable
        query_lower = follow_up_query.lower()
        
        is_contextual = context_id and any([
            "tell me" in query_lower,
            "more about" in query_lower,
            "these" in query_lower,
            "those" in query_lower,
            "the signal" in query_lower,
            "explain" in query_lower,
            "what about" in query_lower
        ])
        
        focus_area = "general"
        if "custom" in query_lower:
            focus_area = "custom_segments"
        elif "price" in query_lower or "cpm" in query_lower or "cost" in query_lower:
            focus_area = "pricing"
        elif "coverage" in query_lower or "reach" in query_lower:
            focus_area = "coverage"
        elif "platform" in query_lower or "deploy" in query_lower:
            focus_area = "platforms"
        elif "signal" in query_lower or "audience" in query_lower:
            focus_area = "signals"
        
        return {
            "is_contextual": is_contextual,
            "focus_area": focus_area,
            "needs_fresh_data": is_contextual,
            "reasoning": "Keyword-based analysis fallback"
        }