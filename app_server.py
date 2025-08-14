#!/usr/bin/env python3
"""
Main application server with integrated search UI.
Runs FastAPI with both MCP endpoints and search UI.
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import time
import os
import sqlite3
from config_loader import load_config
from adapters.manager import AdapterManager

# Create FastAPI app
app = FastAPI(title="Audience Agent", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize configuration and adapters
config = load_config()
adapter_manager = AdapterManager(config)

def get_db_connection():
    """Get database connection with row factory."""
    db_path = os.environ.get('DATABASE_PATH', 'signals_agent.db')
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

@app.get("/")
async def home():
    """Home page with links to different interfaces."""
    return HTMLResponse(content="""
    <html>
    <head>
        <title>Audience Agent</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #333; }
            .link-card { 
                border: 1px solid #ddd; 
                padding: 20px; 
                margin: 10px 0; 
                border-radius: 8px;
                text-decoration: none;
                display: block;
                color: inherit;
            }
            .link-card:hover { background: #f5f5f5; }
            .link-card h2 { margin-top: 0; color: #0066cc; }
            .link-card p { color: #666; }
        </style>
    </head>
    <body>
        <h1>🎯 Audience Agent</h1>
        <p>AI-powered audience discovery and activation platform</p>
        
        <a href="/search" class="link-card">
            <h2>🔍 Search UI</h2>
            <p>Interactive search interface for discovering LiveRamp segments using RAG, FTS, and hybrid search</p>
        </a>
        
        <a href="/api/stats" class="link-card">
            <h2>📊 System Stats</h2>
            <p>View database statistics and system health</p>
        </a>
        
        <div class="link-card">
            <h2>🔌 MCP Interface</h2>
            <p>Connect via MCP protocol on port 8000 for programmatic access</p>
        </div>
    </body>
    </html>
    """)

@app.get("/search")
async def serve_search_ui():
    """Serve the search UI HTML page."""
    try:
        with open("search_ui.html", "r") as f:
            content = f.read()
            # Update API endpoints to use relative paths
            content = content.replace('http://localhost:8002', '')
            return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Search UI not found. Please ensure search_ui.html exists.</h1>", 
            status_code=404
        )

@app.get("/api/search")
async def search_api(
    q: str = Query(..., description="Search query"),
    mode: str = Query("hybrid", description="Search mode: rag, fts, or hybrid"),
    limit: int = Query(20, description="Number of results"),
    rag_weight: float = Query(0.7, description="Weight for RAG in hybrid mode"),
    expand_query: bool = Query(True, description="Use AI to expand query with related terms")
):
    """Search LiveRamp segments using different modes with optional query expansion."""
    
    # Get LiveRamp adapter
    adapter = adapter_manager.adapters.get('liveramp')
    
    if not adapter:
        raise HTTPException(status_code=500, detail="LiveRamp adapter not initialized")
    
    start_time = time.time()
    
    try:
        if mode == "rag":
            # Pure RAG search
            if not hasattr(adapter, 'embeddings_manager') or not adapter.embeddings_manager:
                raise HTTPException(status_code=400, detail="Embeddings not available")
            results = adapter.search_segments_rag(q, limit=limit, use_expansion=expand_query)
            
        elif mode == "fts":
            # Pure FTS search (no expansion for FTS)
            results = adapter.search_segments(q, limit=limit)
            
        elif mode == "hybrid":
            # Hybrid search (expansion only affects RAG part)
            results = adapter.search_segments_hybrid(q, limit=limit, rag_weight=rag_weight, use_expansion=expand_query)
            
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
        
        # Calculate search time
        search_time = time.time() - start_time
        
        # Format results
        formatted_results = []
        for r in results:
            formatted_results.append({
                "id": r.get("segment_id"),
                "name": r.get("name"),
                "description": r.get("description"),
                "provider": r.get("provider"),
                "categories": r.get("categories", []),
                "coverage": r.get("coverage_percentage"),
                "cpm": r.get("cpm"),
                "rag_score": r.get("rag_score", 0),
                "fts_score": r.get("fts_score", 0),
                "combined_score": r.get("combined_score", 0),
                "similarity_score": r.get("similarity_score", 0),
                "relevance_score": r.get("relevance_score", 0)
            })
        
        return {
            "query": q,
            "mode": mode,
            "limit": limit,
            "rag_weight": rag_weight if mode == "hybrid" else None,
            "search_time": round(search_time * 1000, 2),  # in ms
            "result_count": len(formatted_results),
            "results": formatted_results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    """Get statistics about the database and embeddings."""
    
    stats = {
        "database": {},
        "embeddings": {},
        "adapter": {}
    }
    
    # Database stats
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Count LiveRamp segments
    cursor.execute("SELECT COUNT(*) as count FROM liveramp_segments")
    lr_count = cursor.fetchone()
    stats["database"]["liveramp_segments"] = lr_count['count'] if lr_count else 0
    
    # Count segments with embeddings
    try:
        cursor.execute("SELECT COUNT(*) as count FROM liveramp_embeddings")
        emb_count = cursor.fetchone()
        stats["embeddings"]["total"] = emb_count['count'] if emb_count else 0
    except sqlite3.OperationalError:
        stats["embeddings"]["total"] = 0
    
    # Get sync status
    try:
        cursor.execute("SELECT * FROM liveramp_sync_status ORDER BY started_at DESC LIMIT 1")
        sync_status = cursor.fetchone()
        if sync_status:
            stats["database"]["last_sync"] = dict(sync_status)
    except sqlite3.OperationalError:
        pass
    
    # Get LiveRamp adapter status
    adapter = adapter_manager.adapters.get('liveramp')
    
    if adapter:
        stats["adapter"]["initialized"] = True
        stats["adapter"]["has_embeddings"] = hasattr(adapter, 'embeddings_manager') and adapter.embeddings_manager is not None
    else:
        stats["adapter"]["initialized"] = False
        stats["adapter"]["has_embeddings"] = False
    
    conn.close()
    
    return stats

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get('PORT', 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)