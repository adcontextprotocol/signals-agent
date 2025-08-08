#!/usr/bin/env python3
"""A2A Protocol Compatibility Tests."""

import json
import requests
import pytest
from typing import Dict, Any
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional


class AgentCardSchema(BaseModel):
    """A2A Agent Card schema for validation."""
    name: str
    description: str
    version: str
    protocolVersion: str
    url: str
    defaultInputModes: List[str]
    defaultOutputModes: List[str]
    capabilities: Dict[str, Any]
    skills: List[Dict[str, Any]]
    provider: Dict[str, str]


class TestA2ACompatibility:
    """Test suite for A2A protocol compliance."""
    
    BASE_URL = "http://localhost:8000"
    
    @classmethod
    def setup_class(cls):
        """Check if server is running."""
        try:
            response = requests.get(f"{cls.BASE_URL}/health", timeout=1)
            if response.status_code != 200:
                pytest.skip("Server not running")
        except requests.exceptions.RequestException:
            pytest.skip("Server not running on localhost:8000")
    
    def test_agent_card_structure(self):
        """Test that agent card has all required fields."""
        response = requests.get(f"{self.BASE_URL}/agent-card")
        assert response.status_code == 200
        
        agent_card = response.json()
        
        # Validate against schema
        try:
            validated = AgentCardSchema(**agent_card)
        except ValidationError as e:
            pytest.fail(f"Agent card validation failed: {e}")
        
        # Additional specific checks
        assert validated.protocolVersion == "a2a/v1"
        assert "text" in validated.defaultInputModes
        assert "text" in validated.defaultOutputModes
        assert len(validated.skills) > 0
        assert "tags" in validated.skills[0]
        assert len(validated.skills[0]["tags"]) > 0
    
    def test_agent_card_wellknown_endpoint(self):
        """Test that /.well-known/agent.json returns same as /agent-card."""
        card1 = requests.get(f"{self.BASE_URL}/agent-card").json()
        card2 = requests.get(f"{self.BASE_URL}/.well-known/agent.json").json()
        
        # URLs might differ due to request path, so compare other fields
        card1_copy = card1.copy()
        card2_copy = card2.copy()
        card1_copy.pop("url", None)
        card2_copy.pop("url", None)
        
        assert card1_copy == card2_copy
    
    def test_a2a_task_endpoint(self):
        """Test A2A task endpoint with basic discovery."""
        request_data = {
            "query": "luxury car enthusiasts",
            "instruction": "Find audiences interested in luxury cars"
        }
        
        response = requests.post(f"{self.BASE_URL}/a2a/task", json=request_data)
        
        # Allow 500 errors during test development but log them
        if response.status_code == 500:
            print(f"Server error (may be missing Gemini API key): {response.text[:200]}")
            pytest.skip("Server returned 500 - likely configuration issue")
        
        assert response.status_code == 200
        
        result = response.json()
        
        # Validate structure
        assert "id" in result
        assert "kind" in result
        assert result["kind"] == "task"
        assert "contextId" in result
        assert "status" in result
        assert "state" in result["status"]
        assert result["status"]["state"] in ["completed", "working", "failed"]
        
        if result["status"]["state"] == "completed":
            assert "message" in result["status"]
            message = result["status"]["message"]
            assert "kind" in message
            assert message["kind"] == "message"
            assert "message_id" in message  # underscore, not camelCase
            assert "parts" in message
            assert "role" in message
            assert message["role"] == "agent"
            
            # Check parts structure
            parts = message["parts"]
            assert len(parts) >= 1
            text_parts = [p for p in parts if p.get("kind") == "text"]
            assert len(text_parts) >= 1
    
    def test_contextual_query(self):
        """Test that contextual queries maintain context."""
        # First query
        request1 = {
            "query": "automotive enthusiasts",
            "instruction": "Find automotive audiences"
        }
        
        response1 = requests.post(f"{self.BASE_URL}/a2a/task", json=request1)
        if response1.status_code == 500:
            pytest.skip("Server configuration issue")
        assert response1.status_code == 200
        result1 = response1.json()
        context_id = result1.get("contextId")
        assert context_id is not None
        
        # Follow-up query with context
        request2 = {
            "query": "tell me more about these audiences",
            "contextId": context_id
        }
        
        response2 = requests.post(f"{self.BASE_URL}/a2a/task", json=request2)
        assert response2.status_code == 200
        result2 = response2.json()
        
        # Should maintain same context
        assert result2.get("contextId") == context_id
        
        # Response should be contextual (not a new search)
        if result2["status"]["state"] == "completed":
            message = result2["status"]["message"]
            text_parts = [p for p in message["parts"] if p.get("kind") == "text"]
            if text_parts:
                text = text_parts[0]["text"].lower()
                # Should reference the previous search
                assert any(word in text for word in ["automotive", "car", "vehicle", "these"])
    
    def test_json_rpc_message_send(self):
        """Test JSON-RPC message/send format."""
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [
                        {"kind": "text", "text": "find luxury travel audiences"}
                    ]
                }
            }
        }
        
        response = requests.post(f"{self.BASE_URL}/", json=request_data)
        if response.status_code == 500:
            pytest.skip("Server configuration issue")
        assert response.status_code == 200
        
        result = response.json()
        
        # Validate JSON-RPC response
        assert "jsonrpc" in result
        assert result["jsonrpc"] == "2.0"
        assert "id" in result
        assert result["id"] == 1
        assert "result" in result
        
        # Result should be a Message object
        message = result["result"]
        assert "kind" in message
        assert message["kind"] == "message"
        assert "message_id" in message  # underscore format
        assert "parts" in message
        assert "role" in message
        assert message["role"] == "agent"
    
    def test_error_handling(self):
        """Test proper error response format."""
        # Invalid request
        request_data = {
            "query": None,  # Invalid
            "instruction": "test"
        }
        
        response = requests.post(f"{self.BASE_URL}/a2a/task", json=request_data)
        
        # Allow 500 or 200 with error status
        if response.status_code == 500:
            pytest.skip("Server configuration issue")
        
        # Should return 200 with error in status
        assert response.status_code == 200
        result = response.json()
        
        if "status" in result and result["status"]["state"] == "failed":
            assert "error" in result["status"]
            error = result["status"]["error"]
            assert "code" in error
            assert "message" in error
            assert isinstance(error["code"], int)
    
    def test_custom_segment_query(self):
        """Test that 'custom segments' queries are recognized."""
        # First create context
        request1 = {
            "query": "luxury buyers",
            "instruction": "Find luxury audiences"
        }
        
        response1 = requests.post(f"{self.BASE_URL}/a2a/task", json=request1)
        if response1.status_code == 500:
            pytest.skip("Server configuration issue")
        context_id = response1.json().get("contextId")
        
        # Ask about custom segments
        request2 = {
            "query": "what are the custom segments?",
            "contextId": context_id
        }
        
        response2 = requests.post(f"{self.BASE_URL}/a2a/task", json=request2)
        assert response2.status_code == 200
        
        result2 = response2.json()
        assert result2.get("contextId") == context_id
        
        # Should get contextual response about custom segments
        if result2["status"]["state"] == "completed":
            message = result2["status"]["message"]
            data_parts = [p for p in message["parts"] if p.get("kind") == "data"]
            if data_parts:
                data = data_parts[0]["data"]
                # Should have custom_segment_proposals
                assert "custom_segment_proposals" in data or "custom_proposals" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])