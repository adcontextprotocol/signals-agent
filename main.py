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
from rich.console import Console

from database import init_db
from schemas import *
from adapters.manager import AdapterManager
from config_loader import load_config


# In-memory storage for custom segments and activations
custom_segments: Dict[str, Dict] = {}
segment_activations: Dict[str, Dict] = {}
discovery_contexts: Dict[str, Dict] = {}


def get_db_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect('signals_agent.db')
    conn.row_factory = sqlite3.Row
    return conn


def generate_context_id() -> str:
    """Generate unique context ID for tracking discovery and activation sessions."""
    timestamp = int(datetime.now().timestamp())
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"ctx_{timestamp}_{random_suffix}"


def store_discovery_context(context_id: str, signal_spec: str, results: List[str], principal_id: Optional[str] = None):
    """Store discovery context for later reference in activations."""
    discovery_contexts[context_id] = {
        "signal_spec": signal_spec,
        "discovered_signals": results,
        "principal_id": principal_id,
        "timestamp": datetime.now().isoformat(),
        "activations": []
    }
    
    # Clean up old contexts (older than 7 days to accommodate 72-hour activation windows)
    cutoff = datetime.now() - timedelta(days=7)
    expired_contexts = [
        cid for cid, ctx in discovery_contexts.items()
        if datetime.fromisoformat(ctx["timestamp"]) < cutoff
    ]
    for cid in expired_contexts:
        del discovery_contexts[cid]


def link_activation_to_context(context_id: str, signal_id: str, platform: str, account: Optional[str] = None):
    """Link an activation to its discovery context."""
    if context_id in discovery_contexts:
        discovery_contexts[context_id]["activations"].append({
            "signal_id": signal_id,
            "platform": platform,
            "account": account,
            "activated_at": datetime.now().isoformat()
        })


def rank_signals_with_ai(signal_spec: str, segments: List[Dict], max_results: int = 10) -> List[Dict]:
    """Use Gemini to intelligently rank signals based on the specification."""
    if not segments:
        return []
    
    # Prepare segment data for AI analysis
    segment_data = []
    for segment in segments:
        segment_data.append({
            "id": segment["id"],
            "name": segment["name"], 
            "description": segment["description"],
            "coverage_percentage": segment["coverage_percentage"],
            "cpm": segment["base_cpm"]
        })
    
    prompt = f"""
    You are an expert signals targeting analyst. A client has requested signals for: "{signal_spec}"
    
    Here are available signal segments from various providers, including different signal types:
    - Audience signals: demographic/behavioral targeting
    - Contextual signals: content-based targeting
    - Geographical signals: location-based targeting
    - Temporal signals: time-based targeting
    - Environmental signals: weather/events/conditions
    - Bidding signals: custom bidding strategies
    
    Available segments:
    {json.dumps(segment_data, indent=2)}
    
    Please:
    1. Rank these segments by relevance to the client's request (most relevant first)
    2. Consider all signal types - the client may benefit from multiple types
    3. Select the top {max_results} most relevant segments
    4. For each selected segment, provide a brief explanation of why it matches the request
    
    Return your response as a JSON array with this structure:
    [
      {{
        "segment_id": "segment_id",
        "relevance_score": 0.95,
        "match_reason": "Brief explanation of why this segment matches the request"
      }}
    ]
    
    Only include segments that have at least some relevance. If none are relevant, return an empty array.
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
    - Why an advertiser would pay a premium for this targeting
    
    Return your response as a JSON array:
    [
      {{
        "proposed_name": "Specific segment name",
        "description": "Detailed description of what content/context this targets",
        "target_signals": "What signals this captures (audiences, contexts, behaviors)",
        "estimated_coverage_percentage": 2.5,
        "estimated_cpm": 6.50,
        "creation_rationale": "Why this segment would be valuable and what signals would be used"
      }}
    ]
    
    Focus on high-value, specific segments that would command premium pricing.
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
init_db()

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
    principal_id: Optional[str] = None,
    context_id: Optional[str] = None
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
    try:
        platform_segments = adapter_manager.get_all_segments(
            deliver_to.model_dump(), 
            principal_id
        )
        if platform_segments:
            console.print(f"[dim]Found {len(platform_segments)} segments from platform APIs[/dim]")
    except Exception as e:
        console.print(f"[yellow]Platform adapter error: {e}[/yellow]")
    
    # Combine database and platform segments
    all_segments = db_segments + platform_segments
    
    # Use AI to rank segments by relevance to the signal spec
    ranked_segments = rank_signals_with_ai(signal_spec, all_segments, max_results or 10)
    
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
    
    conn.close()
    
    # Generate or reuse context ID
    if not context_id:
        context_id = generate_context_id()
    
    # Store discovery context for future activations
    discovered_signal_ids = [s.signals_agent_segment_id for s in signals]
    if custom_proposals:
        discovered_signal_ids.extend([p.custom_segment_id for p in custom_proposals])
    
    store_discovery_context(context_id, signal_spec, discovered_signal_ids, principal_id)
    
    # Generate human-readable message
    signal_count = len(signals)
    proposal_count = len(custom_proposals) if custom_proposals else 0
    
    if signal_count == 0 and proposal_count == 0:
        message = f"No signals found matching '{signal_spec}'. Try broadening your search criteria."
    elif signal_count > 0 and proposal_count > 0:
        platform_count = len(set(d.platform for s in signals for d in s.deployments))
        message = f"Found {signal_count} signals matching '{signal_spec}' across {platform_count} platforms, plus {proposal_count} custom segment proposals"
    elif signal_count > 0:
        platform_count = len(set(d.platform for s in signals for d in s.deployments))
        message = f"Found {signal_count} signals matching '{signal_spec}' across {platform_count} platforms"
    else:
        message = f"No existing signals match '{signal_spec}', but I've proposed {proposal_count} custom segments that could be created"
    
    return GetSignalsResponse(
        message=message,
        signals=signals,
        custom_segment_proposals=custom_proposals if custom_proposals else None,
        context_id=context_id,
        clarification_needed=False  # Could be True if signal_spec is too vague
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
                return ActivateSignalResponse(
                    message=f"Custom segment '{segment['name']}' is already deployed on {platform}",
                    decisioning_platform_segment_id=existing['decisioning_platform_segment_id'],
                    estimated_activation_duration_minutes=0,
                    status="deployed",
                    deployed_at=datetime.fromisoformat(existing.get('deployed_at', existing['activation_started_at'])),
                    context_id=context_id
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
                    
                    return ActivateSignalResponse(
                        message=f"Custom segment '{segment['name']}' is now active on {platform}",
                        decisioning_platform_segment_id=existing['decisioning_platform_segment_id'],
                        estimated_activation_duration_minutes=0,
                        status="deployed",
                        deployed_at=datetime.now(),
                        context_id=context_id
                    )
                else:
                    # Still activating
                    remaining_minutes = int((estimated_completion - datetime.now()).total_seconds() / 60)
                    return ActivateSignalResponse(
                        message=f"Custom segment '{segment['name']}' is still activating on {platform}, {remaining_minutes} minutes remaining",
                        decisioning_platform_segment_id=existing['decisioning_platform_segment_id'],
                        estimated_activation_duration_minutes=remaining_minutes,
                        status="activating",
                        context_id=context_id
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
        
        # Link to discovery context if provided
        if context_id:
            link_activation_to_context(context_id, signals_agent_segment_id, platform, account)
        
        return ActivateSignalResponse(
            message=f"Creating and activating custom segment '{segment['name']}' on {platform}, estimated {activation_duration} minutes",
            decisioning_platform_segment_id=decisioning_platform_segment_id,
            estimated_activation_duration_minutes=activation_duration,
            status="activating",
            context_id=context_id
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
            return ActivateSignalResponse(
                message=f"Signal '{segment['name']}' is already deployed on {platform}",
                decisioning_platform_segment_id=existing['decisioning_platform_segment_id'],
                estimated_activation_duration_minutes=0,
                status="deployed",
                deployed_at=datetime.fromisoformat(existing['deployed_at']) if existing['deployed_at'] else None,
                context_id=context_id
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
            
            return ActivateSignalResponse(
                message=f"Signal '{segment['name']}' has been activated on {platform}",
                decisioning_platform_segment_id=existing['decisioning_platform_segment_id'],
                estimated_activation_duration_minutes=0,
                status="deployed",
                deployed_at=datetime.now(),
                context_id=context_id
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
    
    # Link to discovery context if provided
    if context_id:
        link_activation_to_context(context_id, signals_agent_segment_id, platform, account)
    
    return ActivateSignalResponse(
        message=f"Activating signal '{segment['name']}' on {platform}, estimated {activation_duration} minutes",
        decisioning_platform_segment_id=decisioning_platform_segment_id,
        estimated_activation_duration_minutes=activation_duration,
        status="activating",
        context_id=context_id
    )





if __name__ == "__main__":
    mcp.run()