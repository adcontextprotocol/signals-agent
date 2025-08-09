"""Unified server that mounts both A2A and MCP protocol facades.

This is a clean implementation that separates:
- Business logic (business_logic.py)
- A2A protocol handling (a2a_facade.py)
- MCP protocol handling (mcp_facade.py)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Import the protocol routers
from a2a_facade import router as a2a_router
from mcp_facade import router as mcp_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create main application
app = FastAPI(
    title="Signals Agent Unified Server",
    version="2.0.0",
    description="Unified server supporting both A2A and MCP protocols"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Add health check endpoint (before mounting other routes)
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "protocols": ["a2a", "mcp"]}

# Add root GET endpoint
@app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "name": "Signals Agent Unified Server",
        "version": "2.0.0",
        "protocols": {
            "a2a": {
                "agent_card": "/agent-card",
                "task": "/a2a/task",
                "stream": "/a2a/task/stream"
            },
            "mcp": {
                "endpoint": "/mcp"
            }
        }
    }

# Include the protocol routers
# This properly registers all routes with their metadata
app.include_router(a2a_router)
app.include_router(mcp_router)

if __name__ == "__main__":
    import uvicorn
    host = "0.0.0.0"
    port = 8000
    
    logger.info(f"Starting Unified Server on {host}:{port}")
    logger.info(f"- A2A Agent Card: http://{host}:{port}/agent-card")
    logger.info(f"- A2A Tasks: http://{host}:{port}/a2a/task")
    logger.info(f"- MCP Endpoint: http://{host}:{port}/mcp")
    
    uvicorn.run(app, host=host, port=port)