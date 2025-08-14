"""Main MCP server implementation for the Signals Activation Protocol."""

import json
import sqlite3
import sys
import os
import random
import string
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import google.generativeai as genai
from fastmcp import FastMCP
from fastapi import Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from rich.console import Console
import time

from database import init_db
from schemas import *
from adapters.manager import AdapterManager
from config_loader import load_config


# In-memory storage for custom segments and activations
custom_segments: Dict[str, Dict] = {}
segment_activations: Dict[str, Dict] = {}


def get_db_connection():
    """Get database connection with row factory."""
    db_path = os.environ.get('DATABASE_PATH', 'signals_agent.db')
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def generate_context_id() -> str:
    """Generate a unique context ID in format ctx_<timestamp>_<random>."""
    timestamp = int(datetime.now().timestamp())
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"ctx_{timestamp}_{random_suffix}"


def store_discovery_context(context_id: str, query: str, principal_id: Optional[str], 
                          signal_ids: List[str], search_parameters: Dict[str, Any]) -> None:
    """Store discovery context in unified contexts table with 7-day expiration."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    created_at = datetime.now()
    expires_at = created_at + timedelta(days=7)
    
    # Store metadata as JSON
    metadata = {
        "query": query,
        "signal_ids": signal_ids,
        "search_parameters": search_parameters
    }
    
    cursor.execute("""
        INSERT INTO contexts 
        (context_id, context_type, parent_context_id, principal_id, metadata, created_at, expires_at)
        VALUES (?, 'discovery', NULL, ?, ?, ?, ?)
    """, (
        context_id,
        principal_id,
        json.dumps(metadata),
        created_at.isoformat(),
        expires_at.isoformat()
    ))
    
    conn.commit()
    conn.close()


def store_activation_context(parent_context_id: Optional[str], signal_id: str, 
                           platform: str, account: Optional[str]) -> str:
    """Store activation context in unified contexts table, optionally linking to discovery."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Generate new context ID for this activation
    context_id = generate_context_id()
    
    created_at = datetime.now()
    expires_at = created_at + timedelta(days=30)  # Activations have longer expiration
    
    # Store metadata as JSON
    metadata = {
        "signal_id": signal_id,
        "platform": platform,
        "account": account,
        "activated_at": created_at.isoformat()
    }
    
    # Get principal from parent context if available
    principal_id = None
    if parent_context_id:
        cursor.execute("SELECT principal_id FROM contexts WHERE context_id = ?", (parent_context_id,))
        result = cursor.fetchone()
        if result:
            principal_id = result['principal_id']
    
    cursor.execute("""
        INSERT INTO contexts 
        (context_id, context_type, parent_context_id, principal_id, metadata, created_at, expires_at)
        VALUES (?, 'activation', ?, ?, ?, ?, ?)
    """, (
        context_id,
        parent_context_id,
        principal_id,
        json.dumps(metadata),
        created_at.isoformat(),
        expires_at.isoformat()
    ))
    
    conn.commit()
    conn.close()
    
    return context_id


def generate_activation_message(segment_name: str, platform: str, status: str, 
                              duration_minutes: Optional[int] = None) -> str:
    """Generate a human-readable summary of activation status."""
    if status == "deployed":
        return f"Signal '{segment_name}' is now live on {platform} and ready for immediate use."
    elif status == "activating":
        if duration_minutes:
            return f"Signal '{segment_name}' is being activated on {platform}. Estimated completion time: {duration_minutes} minutes."
        else:
            return f"Signal '{segment_name}' is being activated on {platform}."
    elif status == "failed":
        return f"Failed to activate signal '{segment_name}' on {platform}. Please check the error details."
    else:
        return f"Signal '{segment_name}' activation status on {platform}: {status}"


def generate_discovery_message(signal_spec: str, signals: List[SignalResponse], 
                             custom_proposals: Optional[List[CustomSegmentProposal]]) -> str:
    """Generate a human-readable summary of discovery results."""
    total_found = len(signals)
    
    if total_found == 0 and not custom_proposals:
        return f"No signals found matching '{signal_spec}'. Try broadening your search or checking platform availability."
    
    message_parts = []
    
    if total_found > 0:
        # Summarize coverage range
        coverages = [s.coverage_percentage for s in signals if s.coverage_percentage]
        if coverages:
            min_coverage = min(coverages)
            max_coverage = max(coverages)
            coverage_str = f"{min_coverage:.1f}%-{max_coverage:.1f}%" if min_coverage != max_coverage else f"{min_coverage:.1f}%"
        else:
            coverage_str = "unknown coverage"
        
        # Summarize CPM range
        cpms = [s.pricing.cpm for s in signals if s.pricing.cpm]
        if cpms:
            min_cpm = min(cpms)
            max_cpm = max(cpms)
            cpm_str = f"${min_cpm:.2f}-${max_cpm:.2f}" if min_cpm != max_cpm else f"${min_cpm:.2f}"
        else:
            cpm_str = "pricing varies"
        
        # Count unique platforms with live deployments
        live_platforms = set()
        for s in signals:
            for d in s.deployments:
                if d.is_live:
                    live_platforms.add(d.platform)
        
        platform_count = len(live_platforms)
        if platform_count > 0:
            platform_str = f"available on {platform_count} platform{'s' if platform_count != 1 else ''}"
        else:
            platform_str = "requiring activation"
        
        message_parts.append(
            f"Found {total_found} signal{'s' if total_found != 1 else ''} for '{signal_spec}' with {coverage_str} coverage, "
            f"{cpm_str} CPM, {platform_str}."
        )
    
    if custom_proposals:
        message_parts.append(
            f"Additionally, {len(custom_proposals)} custom segment{'s' if len(custom_proposals) > 1 else ''} "
            f"can be created to better match your specific targeting needs."
        )
    
    return " ".join(message_parts)


def determine_search_strategy(signal_spec: str) -> tuple[str, bool]:
    """Determine the best search mode and whether to use query expansion.
    
    Returns:
        Tuple of (search_mode, use_expansion)
        - search_mode: 'rag', 'fts', or 'hybrid'
        - use_expansion: whether to use AI query expansion
    
    Decision logic for search mode:
    - Conceptual/semantic queries → RAG (e.g., "eco-friendly", "luxury lifestyle")
    - Exact matches/technical terms → FTS (e.g., segment IDs, company names)
    - Natural language descriptions → Hybrid (e.g., "parents with young children")
    - Behavioral/intent queries → RAG (e.g., "likely to buy", "interested in")
    """
    
    # Check for technical/exact match patterns
    if any(op in signal_spec.upper() for op in [' AND ', ' OR ', ' NOT ', '"', "'"]):
        # Boolean operators indicate FTS is better
        return ('fts', False)
    
    # Check for segment IDs or technical codes
    if signal_spec.replace('-', '').replace('_', '').replace('.', '').isalnum() and \
       any(c.isdigit() for c in signal_spec) and len(signal_spec) > 8:
        # Looks like a technical ID
        return ('fts', False)
    
    # Check for company/brand names (usually capitalized, specific)
    words = signal_spec.split()
    capitalized_count = sum(1 for w in words if w and w[0].isupper())
    if capitalized_count >= len(words) * 0.6 and len(words) <= 3:
        # Likely company/brand names
        return ('fts', False)
    
    # Check for behavioral/intent indicators → RAG is best
    intent_indicators = [
        'interested', 'likely', 'intent', 'looking', 'seeking', 'want',
        'lifestyle', 'behavior', 'habit', 'preference', 'affinity',
        'enthusiast', 'lover', 'fan', 'conscious', 'aware', 'minded'
    ]
    if any(indicator in signal_spec.lower() for indicator in intent_indicators):
        return ('rag', True)
    
    # Check for conceptual/thematic queries → RAG is best
    conceptual_terms = [
        'luxury', 'premium', 'budget', 'eco', 'green', 'sustainable',
        'health', 'wellness', 'fitness', 'active', 'affluent', 'trendy',
        'modern', 'traditional', 'conservative', 'progressive'
    ]
    if any(term in signal_spec.lower() for term in conceptual_terms):
        return ('rag', True)
    
    # Check for demographic queries → Hybrid works well
    demographic_terms = [
        'age', 'gender', 'income', 'education', 'parent', 'family',
        'married', 'single', 'retired', 'student', 'professional',
        'homeowner', 'renter', 'urban', 'suburban', 'rural'
    ]
    if any(term in signal_spec.lower() for term in demographic_terms):
        # Hybrid search with expansion for demographic queries
        return ('hybrid', len(words) <= 3)  # Expand if query is short
    
    # Default strategy based on query length
    word_count = len(words)
    
    if word_count == 1:
        # Single word - use RAG with expansion
        return ('rag', True)
    elif word_count == 2:
        # Two words - use hybrid with expansion
        return ('hybrid', True)
    elif word_count <= 4:
        # Medium query - use hybrid, expansion depends on specificity
        has_specific_terms = any(w.lower() in ['with', 'without', 'only', 'not', 'except'] for w in words)
        return ('hybrid', not has_specific_terms)
    else:
        # Long query - use hybrid without expansion
        return ('hybrid', False)


def should_use_query_expansion(signal_spec: str) -> bool:
    """Legacy function - use determine_search_strategy instead.
    
    Logic:
    - Short queries (1-2 words): YES - likely need expansion
    - Vague/general terms: YES - benefit from related terms
    - Very specific queries (4+ words): NO - already detailed
    - Technical IDs/codes: NO - exact match needed
    - Queries with operators (AND, OR, quotes): NO - user has specific intent
    """
    # Check for operators that indicate specific intent
    if any(op in signal_spec.upper() for op in [' AND ', ' OR ', ' NOT ', '"', "'"]):
        return False
    
    # Check for technical IDs (all numbers or alphanumeric codes)
    if signal_spec.replace('-', '').replace('_', '').isalnum() and any(c.isdigit() for c in signal_spec):
        return False
    
    words = signal_spec.split()
    word_count = len(words)
    
    # Short queries benefit from expansion
    if word_count <= 2:
        return True
    
    # Very specific queries don't need expansion
    if word_count >= 5:
        return False
    
    # Check for vague terms that benefit from expansion
    vague_terms = ['people', 'users', 'customers', 'buyers', 'interested', 'looking', 'shopping', 'seeking']
    if any(term in signal_spec.lower() for term in vague_terms):
        return True
    
    # Medium-length queries (3-4 words) - use expansion by default
    return True


def rank_signals_with_ai(signal_spec: str, segments: List[Dict], max_results: int = 10) -> List[Dict]:
    """Use Gemini to intelligently rank signals based on the specification."""
    if not segments:
        return []
    
    # LIMIT segments to prevent "Expression tree too large" error
    MAX_SEGMENTS_FOR_PROMPT = int(os.environ.get('MAX_SEGMENTS_FOR_PROMPT', 50))  # Configurable
    
    if len(segments) > MAX_SEGMENTS_FOR_PROMPT:
        console.print(f"[dim]Reducing {len(segments)} segments to {MAX_SEGMENTS_FOR_PROMPT} for AI processing[/dim]")
        segments = segments[:MAX_SEGMENTS_FOR_PROMPT]
    
    # Prepare segment data for AI analysis - keep it concise
    segment_data = []
    for i, segment in enumerate(segments):
        # Truncate long names/descriptions to reduce prompt size
        name = segment.get("name", "")[:100]
        desc = segment.get("description", "")[:150]
        
        segment_data.append({
            "id": segment["id"],
            "name": name,
            "desc": desc,  # Shortened key name
            "cov": round(segment.get("coverage_percentage", 0), 1),  # Shortened and rounded
            "cpm": round(segment.get("base_cpm", 0), 2)  # Rounded
        })
    
    # Create a more concise prompt
    prompt = f"""
    Rank segments for: "{signal_spec}"
    
    Top {len(segment_data)} segments:
    {json.dumps(segment_data)}
    
    Return top {max_results} as JSON:
    [{{"segment_id": "id", "relevance_score": 0.9, "match_reason": "why"}}]
    """
    
    try:
        response = model.generate_content(prompt)
        clean_json_str = response.text.strip().replace("```json", "").replace("```", "").strip()
        ai_rankings = json.loads(clean_json_str)
        
        # Reorder segments based on AI ranking
        ranked_segments = []
        for ranking in ai_rankings:
            segment_id = ranking.get("segment_id")
            match_reason = ranking.get("match_reason", "Relevant to your query")
            
            # Find the matching segment
            for segment in segments:
                if segment["id"] == segment_id:
                    # Add the match reason to the segment
                    segment_copy = segment.copy()
                    segment_copy["match_reason"] = match_reason
                    ranked_segments.append(segment_copy)
                    break
        
        return ranked_segments
        
    except Exception as e:
        console.print(f"[yellow]AI ranking failed ({e}), using basic text matching[/yellow]")
        # Fallback to basic text matching
        return segments[:max_results]


def generate_custom_segment_proposals(signal_spec: str, existing_segments: List[Dict]) -> List[Dict]:
    """Use Gemini to propose custom segments that could be created for this query."""
    
    existing_names = [seg["name"] for seg in existing_segments]
    
    prompt = f"""
    You are a contextual signal targeting expert. A client is looking for: "{signal_spec}"
    
    We found these existing Peer39 segments:
    {json.dumps(existing_names, indent=2)}
    
    Based on the client's request, propose 2-3 NEW custom contextual segments that Peer39 could create to better serve this targeting need. These should be segments that don't currently exist but would be valuable.
    
    For each proposal, consider:
    - What specific contextual signals could be used
    - What makes this segment unique from existing ones
    - How this targeting delivers value through precision and relevance
    
    Return your response as a JSON array:
    [
      {{
        "proposed_name": "Specific segment name",
        "description": "Detailed description of what content/context this targets",
        "target_signals": "What signals this captures (audiences, contexts, behaviors)",
        "estimated_coverage_percentage": 2.5,
        "estimated_cpm": 6.50,
        "creation_rationale": "How this segment enables precise targeting and what signals would be used"
      }}
    ]
    
    Focus on specific, impactful segments that deliver measurable results.
    """
    
    try:
        response = model.generate_content(prompt)
        clean_json_str = response.text.strip().replace("```json", "").replace("```", "").strip()
        proposals = json.loads(clean_json_str)
        return proposals
        
    except Exception as e:
        console.print(f"[yellow]Custom segment proposal generation failed ({e})[/yellow]")
        return []


# --- Application Setup ---
config = load_config()
# init_db() moved to if __name__ == "__main__" section

# Initialize Gemini
genai.configure(api_key=config.get("gemini_api_key", "your-api-key-here"))
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Initialize platform adapters
adapter_manager = AdapterManager(config)

mcp = FastMCP(name="SignalsActivationAgent")
console = Console()


# --- MCP Tasks ---

@mcp.tool
def get_signal_examples() -> Dict[str, Any]:
    """
    Get examples of how to use the signal discovery tasks.
    
    Returns common usage patterns and platform configurations.
    """
    return {
        "description": "Examples for using the Signals Activation Protocol",
        "get_signals_examples": [
            {
                "description": "Search all platforms for luxury signals",
                "request": {
                    "signal_spec": "luxury car buyers in California",
                    "deliver_to": {
                        "platforms": "all",
                        "countries": ["US"]
                    }
                }
            },
            {
                "description": "Search specific platforms with account",
                "request": {
                    "signal_spec": "parents with young children",
                    "deliver_to": {
                        "platforms": [
                            {"platform": "the-trade-desk"},
                            {"platform": "index-exchange", "account": "1489997"}
                        ],
                        "countries": ["US", "UK"]
                    },
                    "principal_id": "acme_corp"
                }
            },
            {
                "description": "Search with price filters",
                "request": {
                    "signal_spec": "budget-conscious travelers",
                    "deliver_to": {
                        "platforms": "all",
                        "countries": ["US"]
                    },
                    "filters": {
                        "max_cpm": 5.0,
                        "min_coverage_percentage": 10.0
                    }
                }
            }
        ],
        "available_platforms": [
            "the-trade-desk",
            "index-exchange",
            "liveramp",
            "openx",
            "pubmatic",
            "google-dv360",
            "amazon-dsp"
        ],
        "principal_ids": [
            "acme_corp (personalized catalog)",
            "premium_partner (personalized catalog)",
            "enterprise_client (private catalog)"
        ]
    }


@mcp.tool
def get_signals(
    signal_spec: str,
    deliver_to: DeliverySpecification,
    filters: Optional[SignalFilters] = None,
    max_results: Optional[int] = 10,
    principal_id: Optional[str] = None
) -> GetSignalsResponse:
    """
    Discover relevant signals based on a marketing specification.
    
    This task uses AI to match your natural language signal description with available segments
    across multiple decisioning platforms.
    
    Args:
        signal_spec: Natural language description of your target signals
                      Examples: "luxury car buyers", "parents with young children", 
                                "high-income travelers"
        
        deliver_to: Where to search for signals
                    - Set platforms to "all" to search across all platforms
                    - Or specify specific platforms like:
                      {"platforms": [{"platform": "the-trade-desk"}, 
                                     {"platform": "index-exchange", "account": "1489997"}]}
        
        filters: Optional filters to refine results (max_cpm, min_coverage, etc.)
        
        max_results: Number of signals to return (1-100, default 10)
        
        principal_id: Your account ID for accessing private catalogs and custom pricing
                      Examples: "acme_corp", "agency_123"
    
    Returns:
        List of matching signals with deployment status, pricing, and AI-generated
        match explanations. Also includes custom segment proposals when relevant.
    """
    
    # Input validation
    if not signal_spec or not isinstance(signal_spec, str):
        raise ValueError("signal_spec must be a non-empty string")
    
    # Validate and constrain max_results
    if max_results is None:
        max_results = 10
    elif not isinstance(max_results, int) or max_results < 1:
        raise ValueError("max_results must be a positive integer")
    elif max_results > 100:
        console.print(f"[yellow]Warning: Limiting max_results from {max_results} to 100[/yellow]")
        max_results = 100
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Determine catalog access based on principal
    principal_access_level = 'public'  # Default
    if principal_id:
        cursor.execute("SELECT access_level FROM principals WHERE principal_id = ?", (principal_id,))
        principal_row = cursor.fetchone()
        if principal_row:
            principal_access_level = principal_row['access_level']
    
    # Build query based on principal access level
    if principal_access_level == 'public':
        catalog_filter = "catalog_access = 'public'"
    elif principal_access_level == 'personalized':
        catalog_filter = "catalog_access IN ('public', 'personalized')"
    else:  # private
        catalog_filter = "catalog_access IN ('public', 'personalized', 'private')"
    
    query = f"""
        SELECT * FROM signal_segments 
        WHERE {catalog_filter}
    """
    params = []
    
    if filters:
        if filters.catalog_types:
            placeholders = ','.join('?' * len(filters.catalog_types))
            query += f" AND signal_type IN ({placeholders})"
            params.extend(filters.catalog_types)
        
        if filters.data_providers:
            placeholders = ','.join('?' * len(filters.data_providers))
            query += f" AND data_provider IN ({placeholders})"
            params.extend(filters.data_providers)
        
        if filters.max_cpm:
            query += " AND base_cpm <= ?"
            params.append(filters.max_cpm)
        
        if filters.min_coverage_percentage:
            query += " AND coverage_percentage >= ?"
            params.append(filters.min_coverage_percentage)
    
    # Apply flexible text matching on name and description
    if signal_spec:
        # Split the spec into individual words for better matching
        words = signal_spec.lower().split()
        word_conditions = []
        for word in words:
            word_conditions.append("(LOWER(name) LIKE ? OR LOWER(description) LIKE ?)")
            word_pattern = f"%{word}%"
            params.extend([word_pattern, word_pattern])
        
        if word_conditions:
            # Use OR to match any of the words
            query += " AND (" + " OR ".join(word_conditions) + ")"
    
    query += f" ORDER BY coverage_percentage DESC LIMIT ?"
    params.append(max_results or 10)
    
    cursor.execute(query, params)
    db_segments = [dict(row) for row in cursor.fetchall()]
    
    # Get segments from platform adapters
    platform_segments = []
    platform_errors = []
    
    # Determine the best search strategy for this query
    search_mode, use_expansion = determine_search_strategy(signal_spec)
    console.print(f"[dim]Search strategy: {search_mode.upper()} mode with {'AI expansion' if use_expansion else 'exact matching'}[/dim]")
    
    # Log the decision reasoning for transparency
    if search_mode == 'rag':
        console.print(f"[dim]→ Using RAG for conceptual/semantic search[/dim]")
    elif search_mode == 'fts':
        console.print(f"[dim]→ Using FTS for exact/technical matching[/dim]")
    else:  # hybrid
        console.print(f"[dim]→ Using Hybrid to combine semantic and keyword matching[/dim]")
    
    try:
        # TODO: Pass search_mode and use_expansion to adapters that support it
        # For now, adapters will use their default search method
        platform_segments = adapter_manager.get_all_segments(
            deliver_to.model_dump(), 
            principal_id,
            signal_spec  # Pass search query for LiveRamp and other adapters
        )
        if platform_segments:
            console.print(f"[green]✓ Found {len(platform_segments)} segments from platform APIs[/green]")
        else:
            console.print(f"[yellow]⚠ No segments from platform APIs (check if adapters are enabled and data is synced)[/yellow]")
    except Exception as e:
        error_msg = f"Platform adapter error: {e}"
        console.print(f"[red]✗ {error_msg}[/red]")
        platform_errors.append(error_msg)
    
    # Log segment counts for debugging
    console.print(f"[dim]Search summary - Database: {len(db_segments)} segments, Platforms: {len(platform_segments)} segments[/dim]")
    
    # Check if we have any data sources
    if len(db_segments) == 0 and len(platform_segments) == 0:
        console.print(f"[red]WARNING: No segments available from any source![/red]")
        console.print(f"[yellow]Possible causes:[/yellow]")
        console.print(f"[yellow]  1. Database not initialized (run: uv run python database.py)[/yellow]")
        console.print(f"[yellow]  2. LiveRamp not synced (run: uv run python sync_liveramp_catalog.py)[/yellow]")
        console.print(f"[yellow]  3. Platform adapters not configured (check environment variables)[/yellow]")
    
    # Combine database and platform segments
    all_segments = db_segments + platform_segments
    
    # IMPORTANT: Limit segments before sending to AI to avoid "Expression tree too large" error
    # Take top segments based on existing relevance scores or coverage
    MAX_SEGMENTS_FOR_AI = int(os.environ.get('MAX_SEGMENTS_FOR_AI', 100))  # Configurable via env
    
    if len(all_segments) > MAX_SEGMENTS_FOR_AI:
        console.print(f"[dim]Pre-filtering {len(all_segments)} segments to top {MAX_SEGMENTS_FOR_AI} for AI ranking[/dim]")
        
        # Calculate text relevance score for each segment
        query_words = set(signal_spec.lower().split())
        
        def calculate_relevance(segment):
            """Calculate relevance score based on query match."""
            name = segment.get('name', '').lower()
            desc = segment.get('description', '').lower()
            
            # Exact phrase match gets highest score
            if signal_spec.lower() in name:
                text_score = 10.0
            elif signal_spec.lower() in desc:
                text_score = 8.0
            else:
                # Count word matches
                name_words = set(name.split())
                desc_words = set(desc.split())
                
                name_matches = len(query_words & name_words)
                desc_matches = len(query_words & desc_words)
                
                # Score based on word matches (name matches worth more)
                text_score = (name_matches * 2.0) + (desc_matches * 1.0)
            
            # Combine with existing scores
            relevance = segment.get('relevance_score', 0)  # FTS score from LiveRamp
            coverage = segment.get('coverage_percentage', 0) / 100.0  # Normalize to 0-1
            
            # Weighted combination: text match is most important
            final_score = (text_score * 10.0) + (relevance * 5.0) + (coverage * 1.0)
            
            return final_score
        
        # Sort by calculated relevance
        all_segments.sort(key=calculate_relevance, reverse=True)
        all_segments = all_segments[:MAX_SEGMENTS_FOR_AI]
        
        console.print(f"[dim]Top segment after filtering: {all_segments[0].get('name', 'Unknown')[:50]}...[/dim]")
    
    # Use AI to rank segments by relevance to the signal spec
    if all_segments:
        ranked_segments = rank_signals_with_ai(signal_spec, all_segments, max_results or 10)
    else:
        console.print(f"[yellow]Warning: No segments found to rank for query '{signal_spec}'[/yellow]")
        ranked_segments = []
    
    signals = []
    for segment in ranked_segments:
        platform_deployments = []
        
        # Handle platform adapter segments differently than database segments
        if segment.get('platform'):
            # This is a platform adapter segment
            platform_name = segment['platform']
            account_id = segment.get('account_id')
            
            # Check if this platform was requested
            if isinstance(deliver_to.platforms, str) and deliver_to.platforms == "all":
                # Include all platforms
                include_platform = True
            else:
                # Check if this platform is in the requested list
                requested_platforms = set()
                for p in deliver_to.platforms:
                    if hasattr(p, 'platform'):  # PlatformSpecification object
                        requested_platforms.add(p.platform)
                    elif isinstance(p, dict):  # Legacy dict format
                        requested_platforms.add(p.get('platform'))
                    else:  # String format
                        requested_platforms.add(p)
                include_platform = platform_name in requested_platforms
            
            if include_platform:
                # Create a deployment record for the platform segment
                platform_deployments = [PlatformDeployment(
                    signals_agent_segment_id=segment['id'],
                    platform=platform_name,
                    account=account_id,
                    decisioning_platform_segment_id=segment.get('platform_segment_id', segment['id']),
                    scope="account-specific" if account_id else "platform-wide",
                    is_live=True,  # Platform adapter segments are assumed live
                    deployed_at=datetime.now().isoformat(),
                    estimated_activation_duration_minutes=15
                )]
        else:
            # This is a database segment - get platform deployments as before
            cursor.execute("""
                SELECT * FROM platform_deployments 
                WHERE signals_agent_segment_id = ?
            """, (segment['id'],))
            deployments = [dict(row) for row in cursor.fetchall()]
            
            # Filter deployments based on requested platforms
            if isinstance(deliver_to.platforms, str) and deliver_to.platforms == "all":
                # Return all deployments
                platform_deployments = [PlatformDeployment(**dep) for dep in deployments]
            else:
                # Filter deployments by requested platforms
                requested_platforms = set()
                for p in deliver_to.platforms:
                    if hasattr(p, 'platform'):  # PlatformSpecification object
                        requested_platforms.add(p.platform)
                    elif isinstance(p, dict):  # Legacy dict format
                        requested_platforms.add(p.get('platform'))
                    else:  # String format
                        requested_platforms.add(p)
                platform_deployments = []
                
                for dep in deployments:
                    if dep['platform'] in requested_platforms:
                        platform_deployments.append(PlatformDeployment(**dep))
        
        if platform_deployments:
            # Check for custom pricing for this principal
            cpm = segment['base_cpm']
            if principal_id and not segment.get('platform'):
                # Only check database for custom pricing on database segments
                cursor.execute("""
                    SELECT custom_cpm FROM principal_segment_access 
                    WHERE principal_id = ? AND signals_agent_segment_id = ? AND custom_cpm IS NOT NULL
                """, (principal_id, segment['id']))
                custom_pricing = cursor.fetchone()
                if custom_pricing:
                    cpm = custom_pricing['custom_cpm']
            
            signal = SignalResponse(
                signals_agent_segment_id=segment['id'],
                name=segment['name'],
                description=segment['description'],
                signal_type=segment.get('signal_type', segment.get('audience_type', 'audience')),
                data_provider=segment['data_provider'],
                coverage_percentage=segment['coverage_percentage'],
                deployments=platform_deployments,
                pricing=PricingModel(
                    cpm=cpm,
                    revenue_share_percentage=segment['revenue_share_percentage']
                ),
                has_coverage_data=segment.get('has_coverage_data', True),  # Database segments have coverage
                has_pricing_data=segment.get('has_pricing_data', True)  # Database segments have pricing
            )
            signals.append(signal)
    
    # Generate custom segment proposals
    custom_proposals = []
    if signals:  # Only generate proposals if we found some existing segments
        proposal_data = generate_custom_segment_proposals(signal_spec, ranked_segments)
        for proposal in proposal_data:
            # Generate unique ID for custom segment
            custom_id = f"custom_{len(custom_segments) + 1}_{hash(proposal['proposed_name']) % 10000}"
            
            # Store in memory for later activation
            custom_segments[custom_id] = {
                "id": custom_id,
                "name": proposal['proposed_name'],
                "description": f"Custom segment: {proposal.get('target_signals', proposal.get('target_audience', ''))}",
                "signal_type": "custom",
                "data_provider": "Custom AI Generated",
                "coverage_percentage": proposal['estimated_coverage_percentage'],
                "base_cpm": proposal['estimated_cpm'],
                "revenue_share_percentage": 0.0,
                "catalog_access": "personalized",
                "creation_rationale": proposal['creation_rationale'],
                "created_at": datetime.now().isoformat()
            }
            
            # Add the custom ID to the proposal
            proposal_with_id = CustomSegmentProposal(
                **proposal,
                custom_segment_id=custom_id
            )
            custom_proposals.append(proposal_with_id)
    
    # Generate context ID
    context_id = generate_context_id()
    
    # Store discovery context
    signal_ids = [signal.signals_agent_segment_id for signal in signals]
    search_parameters = {
        "signal_spec": signal_spec,
        "deliver_to": deliver_to.model_dump(),
        "filters": filters.model_dump() if filters else None,
        "max_results": max_results,
        "principal_id": principal_id
    }
    store_discovery_context(context_id, signal_spec, principal_id, signal_ids, search_parameters)
    
    # Generate human-readable message
    message = generate_discovery_message(signal_spec, signals, custom_proposals)
    
    # Check if clarification might help
    clarification_needed = None
    if len(signals) < 3 and not custom_proposals:
        clarification_needed = "Consider being more specific about your target audience characteristics, such as demographics, interests, or behaviors."
    elif len(signals) == 0:
        clarification_needed = "No matching signals found. Try broadening your search terms or checking available platforms."
    
    conn.close()
    return GetSignalsResponse(
        message=message,
        context_id=context_id,
        signals=signals,
        custom_segment_proposals=custom_proposals if custom_proposals else None,
        clarification_needed=clarification_needed
    )


@mcp.tool
def activate_signal(
    signals_agent_segment_id: str,
    platform: str,
    account: Optional[str] = None,
    principal_id: Optional[str] = None,
    context_id: Optional[str] = None
) -> ActivateSignalResponse:
    """Activate a signal for use on a specific platform/account."""
    
    # Check if this is a custom segment
    if signals_agent_segment_id.startswith("custom_"):
        if signals_agent_segment_id not in custom_segments:
            raise ValueError(f"Custom segment '{signals_agent_segment_id}' not found")
        
        segment = custom_segments[signals_agent_segment_id]
        
        # Check if already activated
        activation_key = f"{signals_agent_segment_id}_{platform}_{account or 'default'}"
        if activation_key in segment_activations:
            existing = segment_activations[activation_key]
            if existing.get('status') == 'deployed':
                # Already deployed - return current status
                activation_context_id = store_activation_context(context_id, signals_agent_segment_id, platform, account)
                return ActivateSignalResponse(
                    message=generate_activation_message(segment['name'], platform, "deployed"),
                    decisioning_platform_segment_id=existing['decisioning_platform_segment_id'],
                    estimated_activation_duration_minutes=0,
                    status="deployed",
                    deployed_at=datetime.fromisoformat(existing.get('deployed_at', existing['activation_started_at'])),
                    context_id=activation_context_id
                )
            elif existing.get('status') == 'activating':
                # Check if enough time has passed to complete the activation
                estimated_completion = datetime.fromisoformat(existing['estimated_completion'])
                if datetime.now() >= estimated_completion:
                    # Mark as deployed
                    existing['status'] = 'deployed'
                    existing['deployed_at'] = datetime.now().isoformat()
                    segment_activations[activation_key] = existing
                    
                    console.print(f"[bold green]Custom segment '{signals_agent_segment_id}' is now live on {platform}[/bold green]")
                    
                    activation_context_id = store_activation_context(context_id, signals_agent_segment_id, platform, account)
                    return ActivateSignalResponse(
                        message=generate_activation_message(segment['name'], platform, "deployed"),
                        decisioning_platform_segment_id=existing['decisioning_platform_segment_id'],
                        estimated_activation_duration_minutes=0,
                        status="deployed",
                        deployed_at=datetime.now(),
                        context_id=activation_context_id
                    )
                else:
                    # Still activating
                    remaining_minutes = int((estimated_completion - datetime.now()).total_seconds() / 60)
                    return ActivateSignalResponse(
                        message=generate_activation_message(segment['name'], platform, "activating", remaining_minutes),
                        decisioning_platform_segment_id=existing['decisioning_platform_segment_id'],
                        estimated_activation_duration_minutes=remaining_minutes,
                        status="activating",
                        context_id=existing.get('activation_context_id', context_id)
                    )
        
        # Generate platform segment ID
        account_suffix = f"_{account}" if account else ""
        decisioning_platform_segment_id = f"{platform}_{signals_agent_segment_id}{account_suffix}"
        
        # Simulate custom segment creation process
        activation_duration = 120  # Custom segments take longer to create
        
        # Store activation record
        segment_activations[activation_key] = {
            "signals_agent_segment_id": signals_agent_segment_id,
            "platform": platform,
            "account": account,
            "decisioning_platform_segment_id": decisioning_platform_segment_id,
            "status": "activating",
            "activation_started_at": datetime.now().isoformat(),
            "estimated_completion": (datetime.now() + timedelta(minutes=activation_duration)).isoformat()
        }
        
        console.print(f"[bold cyan]Creating and activating custom segment '{segment['name']}' on {platform}[/bold cyan]")
        console.print(f"[dim]This involves building the segment from scratch, estimated duration: {activation_duration} minutes[/dim]")
        
        activation_context_id = store_activation_context(context_id, signals_agent_segment_id, platform, account)
        return ActivateSignalResponse(
            message=generate_activation_message(segment['name'], platform, "activating", activation_duration),
            decisioning_platform_segment_id=decisioning_platform_segment_id,
            estimated_activation_duration_minutes=activation_duration,
            status="activating",
            context_id=activation_context_id
        )
    
    # Handle regular database segments
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if segment exists and principal has access
    cursor.execute(
        "SELECT * FROM signal_segments WHERE id = ?",
        (signals_agent_segment_id,)
    )
    segment = cursor.fetchone()
    if not segment:
        raise ValueError(f"Signal segment '{signals_agent_segment_id}' not found")
    
    # Check principal access if specified
    if principal_id:
        cursor.execute("SELECT access_level FROM principals WHERE principal_id = ?", (principal_id,))
        principal_row = cursor.fetchone()
        if principal_row:
            principal_access_level = principal_row['access_level']
            
            # Check if principal can access this segment
            if segment['catalog_access'] == 'private' and principal_access_level != 'private':
                raise ValueError(f"Principal '{principal_id}' does not have access to private segment '{signals_agent_segment_id}'")
            elif segment['catalog_access'] == 'personalized' and principal_access_level == 'public':
                raise ValueError(f"Principal '{principal_id}' does not have access to personalized segment '{signals_agent_segment_id}'")
    
    # Check if already activated
    cursor.execute("""
        SELECT * FROM platform_deployments 
        WHERE signals_agent_segment_id = ? AND platform = ? AND account IS ?
    """, (signals_agent_segment_id, platform, account))
    
    existing = cursor.fetchone()
    if existing:
        if existing['is_live']:
            # Already deployed - return current status instead of error
            conn.close()
            activation_context_id = store_activation_context(context_id, signals_agent_segment_id, platform, account)
            return ActivateSignalResponse(
                message=generate_activation_message(segment['name'], platform, "deployed"),
                decisioning_platform_segment_id=existing['decisioning_platform_segment_id'],
                estimated_activation_duration_minutes=0,
                status="deployed",
                deployed_at=datetime.fromisoformat(existing['deployed_at']) if existing['deployed_at'] else None,
                context_id=activation_context_id
            )
        else:
            # Still activating - for demo purposes, immediately mark as deployed
            cursor.execute("""
                UPDATE platform_deployments 
                SET is_live = 1, deployed_at = ?
                WHERE signals_agent_segment_id = ? AND platform = ? AND account IS ?
            """, (datetime.now().isoformat(), signals_agent_segment_id, platform, account))
            conn.commit()
            conn.close()
            
            activation_context_id = store_activation_context(context_id, signals_agent_segment_id, platform, account)
            return ActivateSignalResponse(
                message=generate_activation_message(segment['name'], platform, "deployed"),
                decisioning_platform_segment_id=existing['decisioning_platform_segment_id'],
                estimated_activation_duration_minutes=0,
                status="deployed",
                deployed_at=datetime.now(),
                context_id=activation_context_id
            )
    
    # Generate platform segment ID
    account_suffix = f"_{account}" if account else ""
    decisioning_platform_segment_id = f"{platform}_{signals_agent_segment_id}{account_suffix}"
    
    # Create or update deployment record
    scope = "account-specific" if account else "platform-wide"
    activation_duration = config.get('deployment', {}).get('default_activation_duration_minutes', 60)
    
    if existing:
        # Update existing record
        cursor.execute("""
            UPDATE platform_deployments 
            SET decisioning_platform_segment_id = ?, is_live = 0, 
                estimated_activation_duration_minutes = ?
            WHERE signals_agent_segment_id = ? AND platform = ? AND account IS ?
        """, (decisioning_platform_segment_id, activation_duration, 
              signals_agent_segment_id, platform, account))
    else:
        # Insert new record
        cursor.execute("""
            INSERT INTO platform_deployments 
            (signals_agent_segment_id, platform, account, decisioning_platform_segment_id, 
             scope, is_live, estimated_activation_duration_minutes)
            VALUES (?, ?, ?, ?, ?, 0, ?)
        """, (signals_agent_segment_id, platform, account, decisioning_platform_segment_id,
              scope, activation_duration))
    
    conn.commit()
    conn.close()
    
    console.print(f"[bold green]Activating signal {signals_agent_segment_id} on {platform}[/bold green]")
    
    activation_context_id = store_activation_context(context_id, signals_agent_segment_id, platform, account)
    return ActivateSignalResponse(
        message=generate_activation_message(segment['name'], platform, "activating", activation_duration),
        decisioning_platform_segment_id=decisioning_platform_segment_id,
        estimated_activation_duration_minutes=activation_duration,
        status="activating",
        context_id=activation_context_id
    )

if __name__ == "__main__":
    init_db()
    mcp.run()