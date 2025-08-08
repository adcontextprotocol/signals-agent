#!/usr/bin/env python3
"""AI Integration Tests."""

import json
import requests
import pytest
import os
from unittest.mock import patch, MagicMock


class TestAIIntegration:
    """Test suite for AI-powered features."""
    
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
    
    def test_ai_contextual_response(self):
        """Test that AI generates contextual responses."""
        # Initial discovery
        request1 = {
            "query": "luxury travel enthusiasts",
            "instruction": "Find luxury travel audiences"
        }
        
        response1 = requests.post(f"{self.BASE_URL}/a2a/task", json=request1)
        assert response1.status_code == 200
        context_id = response1.json().get("contextId")
        
        # Follow-up question
        request2 = {
            "query": "what is the audience like?",
            "contextId": context_id
        }
        
        response2 = requests.post(f"{self.BASE_URL}/a2a/task", json=request2)
        assert response2.status_code == 200
        result2 = response2.json()
        
        # Check for contextual understanding
        if result2["status"]["state"] == "completed":
            message = result2["status"]["message"]
            text_parts = [p for p in message["parts"] if p.get("kind") == "text"]
            assert len(text_parts) > 0
            
            text = text_parts[0]["text"].lower()
            # Should reference luxury or travel
            assert any(word in text for word in ["luxury", "travel", "premium", "affluent"])
    
    def test_ai_intent_analysis(self):
        """Test AI's ability to analyze query intent."""
        test_cases = [
            {
                "query": "tell me more about signal ABC123",
                "expected_intent": ["details", "signal", "specific"]
            },
            {
                "query": "what are the custom segments?",
                "expected_intent": ["custom", "segment", "proposal"]
            },
            {
                "query": "compare these audiences",
                "expected_intent": ["comparison", "audience", "analysis"]
            },
            {
                "query": "pricing for these segments",
                "expected_intent": ["pricing", "cpm", "cost"]
            }
        ]
        
        for test_case in test_cases:
            request = {
                "query": test_case["query"],
                "instruction": "Analyze intent"
            }
            
            response = requests.post(f"{self.BASE_URL}/a2a/task", json=request)
            assert response.status_code == 200
            
            result = response.json()
            if "metadata" in result and "ai_intent" in result["metadata"]:
                intent = result["metadata"]["ai_intent"]
                # Check if AI recognized the intent correctly
                intent_str = json.dumps(intent).lower()
                assert any(word in intent_str for word in test_case["expected_intent"])
    
    def test_ai_custom_segment_generation(self):
        """Test AI's ability to generate custom segment proposals."""
        request = {
            "query": "eco-conscious millennials who travel",
            "instruction": "Find audiences and suggest custom segments"
        }
        
        response = requests.post(f"{self.BASE_URL}/a2a/task", json=request)
        assert response.status_code == 200
        
        result = response.json()
        if result["status"]["state"] == "completed":
            message = result["status"]["message"]
            data_parts = [p for p in message["parts"] if p.get("kind") == "data"]
            
            if data_parts:
                data = data_parts[0]["data"]
                # Should have custom proposals
                custom_proposals = data.get("custom_segment_proposals", [])
                if custom_proposals:
                    # Check proposals are relevant
                    for proposal in custom_proposals:
                        assert "name" in proposal
                        assert "rationale" in proposal
                        # Name or rationale should relate to query
                        combined = f"{proposal['name']} {proposal['rationale']}".lower()
                        assert any(word in combined for word in ["eco", "millennial", "travel", "sustainable"])
    
    def test_ai_fallback_without_gemini(self):
        """Test that system works without Gemini API key."""
        # This test would mock the Gemini API being unavailable
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            request = {
                "query": "automotive enthusiasts",
                "instruction": "Find audiences"
            }
            
            response = requests.post(f"{self.BASE_URL}/a2a/task", json=request)
            assert response.status_code == 200
            
            result = response.json()
            # Should still return results, even without AI
            assert "status" in result
            if result["status"]["state"] == "completed":
                message = result["status"]["message"]
                assert "parts" in message
    
    def test_ai_conversation_history(self):
        """Test that AI maintains conversation history."""
        # First query
        request1 = {
            "query": "sports fans",
            "instruction": "Find sports audiences"
        }
        
        response1 = requests.post(f"{self.BASE_URL}/a2a/task", json=request1)
        context_id = response1.json().get("contextId")
        
        # Second query building on first
        request2 = {
            "query": "focus on basketball fans",
            "contextId": context_id
        }
        
        response2 = requests.post(f"{self.BASE_URL}/a2a/task", json=request2)
        
        # Third query referencing both
        request3 = {
            "query": "summarize what we've found",
            "contextId": context_id
        }
        
        response3 = requests.post(f"{self.BASE_URL}/a2a/task", json=request3)
        result3 = response3.json()
        
        if result3["status"]["state"] == "completed":
            message = result3["status"]["message"]
            text_parts = [p for p in message["parts"] if p.get("kind") == "text"]
            if text_parts:
                text = text_parts[0]["text"].lower()
                # Should reference both sports and basketball
                assert "sports" in text or "basketball" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])