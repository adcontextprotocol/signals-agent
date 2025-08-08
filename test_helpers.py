#!/usr/bin/env python3
"""Test helpers and mocks for the Signals Agent."""

import json
from typing import Dict, Any, Optional
from unittest.mock import MagicMock


class MockGeminiResponse:
    """Mock Gemini response for testing."""
    
    def __init__(self, text: str):
        self.text = text


class MockGeminiModel:
    """Mock Gemini model for testing."""
    
    def __init__(self, model_name: str = 'gemini-2.0-flash-exp'):
        """Initialize mock model (accepts model name for compatibility)."""
        self.model_name = model_name
    
    def generate_content(self, prompt: str) -> MockGeminiResponse:
        """Generate mock content based on prompt patterns."""
        
        # Analyze query intent
        if "Analyze this audience discovery query" in prompt:
            if "luxury" in prompt.lower():
                return MockGeminiResponse(json.dumps({
                    "search_query": "luxury car enthusiasts",
                    "intent": "discovery",
                    "is_follow_up": False
                }))
            elif "tell me" in prompt.lower() or "what is" in prompt.lower():
                return MockGeminiResponse(json.dumps({
                    "search_query": "previous context",
                    "intent": "details",
                    "is_follow_up": True
                }))
            elif "custom segment" in prompt.lower():
                return MockGeminiResponse(json.dumps({
                    "search_query": "custom segments",
                    "intent": "details",
                    "is_follow_up": True
                }))
            else:
                return MockGeminiResponse(json.dumps({
                    "search_query": "general audience",
                    "intent": "discovery",
                    "is_follow_up": False
                }))
        
        # Generate response message
        elif "Generate a helpful response" in prompt:
            if "luxury" in prompt.lower():
                return MockGeminiResponse(
                    "Found 5 luxury car enthusiast segments with high coverage. "
                    "Top segments include 'Premium Vehicle Owners' (2.5M reach) and "
                    "'Luxury Brand Affinity' (1.8M reach). Available on 3 platforms."
                )
            elif "custom" in prompt.lower():
                return MockGeminiResponse(
                    "Based on your search, I recommend 3 custom segments: "
                    "1) 'High-Value Car Buyers' - Combines luxury interest with purchase intent. "
                    "2) 'Premium Lifestyle Enthusiasts' - Broader luxury audience. "
                    "3) 'Automotive Innovators' - Early adopters of premium vehicles."
                )
            else:
                return MockGeminiResponse(
                    "Found relevant audience segments matching your criteria. "
                    "These audiences are available across multiple platforms."
                )
        
        # Rank signals
        elif "Rank these signals" in prompt:
            # Return the input signals in order (mock ranking)
            return MockGeminiResponse("1,2,3,4,5")
        
        # Generate custom proposals
        elif "create custom audience segments" in prompt:
            if "luxury" in prompt.lower():
                proposals = [
                    {
                        "name": "Luxury Auto Enthusiasts",
                        "description": "High-income individuals interested in premium vehicles",
                        "rationale": "Combines luxury lifestyle with automotive interest",
                        "estimated_size": 2500000
                    },
                    {
                        "name": "Premium Brand Loyalists",
                        "description": "Consumers with strong affinity for luxury brands",
                        "rationale": "Targets brand-conscious luxury consumers",
                        "estimated_size": 1800000
                    }
                ]
            else:
                proposals = [
                    {
                        "name": "General Interest Audience",
                        "description": "Broad audience matching search criteria",
                        "rationale": "Wide reach for general targeting",
                        "estimated_size": 5000000
                    }
                ]
            return MockGeminiResponse(json.dumps(proposals))
        
        # Default response
        return MockGeminiResponse(json.dumps({
            "result": "mock response",
            "status": "success"
        }))


def mock_genai_configure(api_key: str):
    """Mock genai.configure function."""
    pass


def create_mock_genai_module():
    """Create a mock google.generativeai module."""
    mock_module = MagicMock()
    mock_module.configure = mock_genai_configure
    mock_module.GenerativeModel = MockGeminiModel
    return mock_module


def get_test_config():
    """Get test configuration without requiring real API keys."""
    return {
        "gemini_api_key": "test-key-for-testing",
        "test_mode": True,
        "platforms": {
            "index-exchange": {
                "enabled": False,  # Disable for testing
                "test_mode": True
            }
        }
    }