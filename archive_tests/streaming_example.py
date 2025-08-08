"""Example of how to add streaming support to the v2 server."""

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import google.generativeai as genai
import json
import asyncio

# Example of streaming endpoint
async def handle_a2a_task_streaming(request: dict):
    """Handle A2A task with streaming response."""
    
    async def generate_stream():
        # Start with task metadata
        yield f"data: {json.dumps({'type': 'task_start', 'id': task_id})}\n\n"
        
        # Stream the AI response as it's generated
        prompt = "Generate response for: " + query
        
        # Gemini supports streaming!
        for chunk in model.generate_content_stream(prompt):
            yield f"data: {json.dumps({'type': 'text', 'content': chunk.text})}\n\n"
            await asyncio.sleep(0.01)  # Small delay for smooth streaming
        
        # Send the data part at the end
        yield f"data: {json.dumps({'type': 'data', 'content': search_results})}\n\n"
        
        # Signal completion
        yield f"data: {json.dumps({'type': 'task_complete'})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# To enable in agent card:
def get_agent_card_with_streaming():
    return {
        "name": "Signals Agent v2",
        "description": "AI-powered audience discovery",
        "version": "2.1.0",
        "capabilities": {
            "streaming": True,  # ← Enable this!
            "pushNotifications": False,
            "stateTransitionHistory": True,  # ← And this for transparency
            "extensions": []
        }
    }


# Example of state transitions:
async def handle_with_state_history(request: dict):
    """Show state transitions."""
    
    # 1. Start in 'working' state
    await update_task_state(task_id, "working", "Analyzing your query...")
    
    # 2. Update as we progress
    await update_task_state(task_id, "working", "Searching for audiences...")
    
    # 3. Complete with results
    await update_task_state(task_id, "completed", final_response)
    
    # Client can request history:
    # GET /task/{task_id}/history
    # Returns: [
    #   {"state": "pending", "timestamp": "...", "message": "Task created"},
    #   {"state": "working", "timestamp": "...", "message": "Analyzing your query..."},
    #   {"state": "working", "timestamp": "...", "message": "Searching for audiences..."},
    #   {"state": "completed", "timestamp": "...", "message": "Found 3 signals..."}
    # ]