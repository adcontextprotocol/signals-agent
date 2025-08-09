"""Core logic extracted from main.py for use by business_logic.py.

This module contains the actual implementation without MCP decorators,
avoiding module-level initialization issues.
"""

import json
import sqlite3
import random
import string
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from schemas import (
    GetSignalsResponse,
    SignalSegment,
    PricingModel,
    PlatformDeployment,
    DeliverySpecification,
    SignalFilters,
    ActivateSignalResponse,
    CustomSegmentProposal
)


def get_db_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect('signals_agent.db', timeout=30.0)
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
                          signal_ids: List[str], search_parameters: Dict[str, Any],
                          custom_proposals: Optional[List[Dict[str, Any]]] = None) -> None:
    """Store discovery context in unified contexts table with 7-day expiration."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    created_at = datetime.now()
    expires_at = created_at + timedelta(days=7)
    
    # Store metadata as JSON
    metadata = {
        "query": query,
        "signal_ids": signal_ids,
        "search_parameters": search_parameters,
        "custom_proposals": custom_proposals
    }
    
    # Use INSERT OR REPLACE to handle existing contexts (for contextual queries that reuse context_id)
    cursor.execute("""
        INSERT OR REPLACE INTO contexts 
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


def get_signals_core(
    signal_spec: str,
    deliver_to: DeliverySpecification,
    filters: Optional[SignalFilters] = None,
    max_results: Optional[int] = 10,
    principal_id: Optional[str] = None,
    context_id: Optional[str] = None
) -> GetSignalsResponse:
    """Core implementation of get_signals without MCP decorator."""
    
    # Generate context ID if not provided
    if not context_id:
        context_id = generate_context_id()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build query
    query = """
        SELECT 
            ss.id as segment_id,
            ss.name,
            ss.description,
            ss.data_provider,
            ss.coverage_percentage,
            ss.signal_type,
            ss.base_cpm,
            ss.revenue_share_percentage
        FROM signal_segments ss
        WHERE 1=1
    """
    
    params = []
    
    # Add basic text search
    if signal_spec:
        query += " AND (name LIKE ? OR description LIKE ?)"
        search_term = f"%{signal_spec}%"
        params.extend([search_term, search_term])
    
    # Add max results
    if max_results:
        query += f" LIMIT {max_results}"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # Build response
    signals = []
    signal_ids = []
    for row in rows:
        # Create pricing object from database columns
        pricing = None
        if row['base_cpm']:
            pricing = PricingModel(
                cpm=row['base_cpm'],
                minimum_spend=None,
                currency='USD',
                pricing_model='CPM'
            )
        
        # Create deployment objects
        deployments = []
        # Assume available on all platforms (since we don't have deployment data in this table)
        if True:  # Always create default deployments
            # Get platforms from deliver_to
            platforms_list = []
            if deliver_to.platforms == "all":
                platforms_list = ["ttd", "dv360", "amazon", "index-exchange"]
            elif isinstance(deliver_to.platforms, list):
                platforms_list = deliver_to.platforms
            elif isinstance(deliver_to.platforms, str):
                platforms_list = [deliver_to.platforms]
            
            for platform in platforms_list:
                deployments.append(PlatformDeployment(
                    platform=platform,
                    status='available'
                ))
        
        signal = SignalSegment(
            signals_agent_segment_id=row['segment_id'],
            name=row['name'],
            description=row['description'],
            data_provider=row['data_provider'],
            coverage_percentage=row['coverage_percentage'] if row['coverage_percentage'] else None,
            tags=[row['signal_type']] if row['signal_type'] else [],
            pricing=pricing,
            deployments=deployments,
            has_coverage_data=row['coverage_percentage'] is not None,
            has_pricing_data=pricing is not None
        )
        signals.append(signal)
        signal_ids.append(row['segment_id'])
    
    conn.close()
    
    # Generate custom segment proposals using AI
    custom_proposals = []
    if signal_spec:
        # For now, create synthetic proposals
        custom_proposals = [
            CustomSegmentProposal(
                proposed_name=f"Custom: {signal_spec} - Premium",
                description=f"High-value audience interested in premium {signal_spec}",
                target_signals=signal_spec,
                estimated_coverage_percentage=8.5,
                estimated_cpm=4.50,
                creation_rationale="Combines purchase intent with demographic targeting",
                custom_segment_id=f"custom_{generate_context_id()[:8]}"
            ),
            CustomSegmentProposal(
                proposed_name=f"Custom: {signal_spec} - Broad",
                description=f"Broad audience with general interest in {signal_spec}",
                target_signals=signal_spec,
                estimated_coverage_percentage=15.0,
                estimated_cpm=2.00,
                creation_rationale="Wider reach with contextual targeting",
                custom_segment_id=f"custom_{generate_context_id()[:8]}"
            )
        ]
    
    # Store context for contextual follow-ups
    store_discovery_context(
        context_id=context_id,
        query=signal_spec,
        principal_id=principal_id,
        signal_ids=signal_ids,
        search_parameters={
            "deliver_to": deliver_to.dict() if deliver_to else None,
            "filters": filters.dict() if filters else None,
            "max_results": max_results
        },
        custom_proposals=[p.dict() for p in custom_proposals] if custom_proposals else None
    )
    
    # Generate a summary message
    message = f"Found {len(signals)} signals"
    if signal_spec:
        message = f"Found {len(signals)} signals matching '{signal_spec}'"
    if custom_proposals:
        message += f" and generated {len(custom_proposals)} custom segment proposals"
    
    return GetSignalsResponse(
        message=message,
        signals=signals,
        custom_segment_proposals=custom_proposals if custom_proposals else None,
        context_id=context_id
    )


def activate_signal_core(
    signals_agent_segment_id: str,
    platform: str,
    account: Optional[str] = None,
    principal_id: Optional[str] = None,
    context_id: Optional[str] = None
) -> ActivateSignalResponse:
    """Core implementation of activate_signal without MCP decorator."""
    
    # For now, simulate activation
    activation_id = f"act_{generate_context_id()[:12]}"
    
    return ActivateSignalResponse(
        signals_agent_segment_id=signals_agent_segment_id,
        platform=platform,
        platform_segment_id=f"{platform}_{signals_agent_segment_id}",
        activation_id=activation_id,
        status="pending",
        message=f"Signal {signals_agent_segment_id} queued for activation on {platform}",
        context_id=context_id
    )