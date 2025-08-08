"""Unit tests for the Audience Activation Protocol implementation."""

import unittest
import json
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from main import mcp
from database import init_db
from schemas import *


class TestAudienceActivationProtocol(unittest.TestCase):
    """Test suite for the audience activation protocol."""
    
    def setUp(self):
        """Set up test database before each test."""
        # Use in-memory database for testing
        self.test_db = ":memory:"
        with patch('main.get_db_connection') as mock_conn:
            mock_conn.return_value = sqlite3.connect(self.test_db)
            init_db()
    
    def get_test_db_connection(self):
        """Get connection to test database."""
        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        return conn
    
    @patch('main.get_db_connection')
    def test_get_audiences_multi_platform_specific(self, mock_conn):
        """Test multi-platform audience discovery with specific platforms."""
        mock_conn.return_value = self.get_test_db_connection()
        
        request_data = {
            "audience_spec": "sports enthusiasts",
            "deliver_to": {
                "platforms": [
                    {"platform": "the-trade-desk", "account": "omnicom-ttd-main"},
                    {"platform": "index-exchange"}
                ],
                "countries": ["US"]
            },
            "filters": {
                "catalog_types": ["marketplace"],
                "max_cpm": 5.0
            },
            "max_results": 3
        }
        
        response = mcp.call_tool("get_audiences", **request_data)
        
        # Validate response structure
        self.assertIn("audiences", response)
        self.assertIsInstance(response["audiences"], list)
        
        if response["audiences"]:
            audience = response["audiences"][0]
            # Check required fields
            self.assertIn("audience_agent_segment_id", audience)
            self.assertIn("name", audience)
            self.assertIn("description", audience)
            self.assertIn("audience_type", audience)
            self.assertIn("data_provider", audience)
            self.assertIn("coverage_percentage", audience)
            self.assertIn("pricing", audience)
            
            # Should have deployments array
            self.assertIn("deployments", audience)
            self.assertIsInstance(audience["deployments"], list)
    
    @patch('main.get_db_connection')
    def test_get_audiences_multi_platform(self, mock_conn):
        """Test multi-platform audience discovery."""
        mock_conn.return_value = self.get_test_db_connection()
        
        request_data = {
            "audience_spec": "automotive",
            "deliver_to": {
                "platforms": [
                    {"platform": "index-exchange"},
                    {"platform": "openx"}
                ],
                "countries": ["US"]
            },
            "max_results": 5
        }
        
        response = mcp.call_tool("get_audiences", **request_data)
        
        # Validate response structure
        self.assertIn("audiences", response)
        
        if response["audiences"]:
            audience = response["audiences"][0]
            # Should have deployments array
            self.assertIn("deployments", audience)
            self.assertIsInstance(audience["deployments"], list)
            
            if audience["deployments"]:
                deployment = audience["deployments"][0]
                self.assertIn("platform", deployment)
                self.assertIn("is_live", deployment)
                self.assertIn("scope", deployment)
    
    @patch('main.get_db_connection')
    def test_activate_audience_success(self, mock_conn):
        """Test successful audience activation."""
        mock_conn.return_value = self.get_test_db_connection()
        
        request_data = {
            "audience_agent_segment_id": "peer39_luxury_auto",
            "platform": "google-dv360",
            "account": "test-account"
        }
        
        response = mcp.call_tool("activate_audience", **request_data)
        
        # Validate response structure
        self.assertIn("decisioning_platform_segment_id", response)
        self.assertIn("estimated_activation_duration_minutes", response)
        
        # Check that the segment ID follows expected format
        expected_id = "google-dv360_peer39_luxury_auto_test-account"
        self.assertEqual(response["decisioning_platform_segment_id"], expected_id)
        
        # Check duration is reasonable
        duration = response["estimated_activation_duration_minutes"]
        self.assertGreater(duration, 0)
        self.assertLess(duration, 1440)  # Less than 24 hours
    
    @patch('main.get_db_connection')
    def test_activate_audience_not_found(self, mock_conn):
        """Test activation of non-existent audience."""
        mock_conn.return_value = self.get_test_db_connection()
        
        request_data = {
            "audience_agent_segment_id": "nonexistent_segment",
            "platform": "the-trade-desk"
        }
        
        with self.assertRaises(ValueError) as context:
            mcp.call_tool("activate_audience", **request_data)
        
        self.assertIn("not found", str(context.exception))
    
    @patch('main.get_db_connection')
    def test_check_audience_status(self, mock_conn):
        """Test audience status checking."""
        mock_conn.return_value = self.get_test_db_connection()
        
        request_data = {
            "audience_agent_segment_id": "sports_enthusiasts_public",
            "decisioning_platform": "the-trade-desk"
        }
        
        response = mcp.call_tool("check_audience_status", **request_data)
        
        # Validate response structure
        self.assertIn("status", response)
        self.assertIn(response["status"], ["deployed", "activating", "failed", "not_found"])
        
        if response["status"] == "deployed":
            self.assertIn("deployed_at", response)
    
    
    def test_audience_response_model_validation(self):
        """Test that AudienceResponse model validates correctly."""
        # Valid audience response
        valid_data = {
            "audience_agent_segment_id": "test_segment",
            "name": "Test Audience", 
            "description": "Test description",
            "audience_type": "marketplace",
            "data_provider": "TestProvider",
            "coverage_percentage": 25.5,
            "deployments": [
                {
                    "platform": "the-trade-desk",
                    "account": None,
                    "is_live": True,
                    "scope": "platform-wide",
                    "decisioning_platform_segment_id": "ttd_test_segment"
                }
            ],
            "pricing": {
                "cpm": 3.50,
                "currency": "USD"
            }
        }
        
        # Should not raise validation error
        audience = AudienceResponse(**valid_data)
        self.assertEqual(audience.audience_agent_segment_id, "test_segment")
        self.assertEqual(audience.coverage_percentage, 25.5)
    
    def test_get_audiences_request_validation(self):
        """Test that GetAudiencesRequest validates deliver_to formats."""
        # Multi-platform format with specific platforms
        multi_platform_data = {
            "audience_spec": "test spec",
            "deliver_to": {
                "platforms": [{"platform": "index-exchange"}],
                "countries": ["US"]
            }
        }
        
        request = GetAudiencesRequest(**multi_platform_data)
        self.assertIsInstance(request.deliver_to, DeliverySpecification)
        
        # All platforms format
        all_platforms_data = {
            "audience_spec": "test spec",
            "deliver_to": {
                "platforms": "all",
                "countries": ["US"]
            }
        }
        
        request = GetAudiencesRequest(**all_platforms_data)
        self.assertIsInstance(request.deliver_to, DeliverySpecification)
    
    def test_pricing_model_validation(self):
        """Test PricingModel validation."""
        # CPM only
        cpm_pricing = PricingModel(cpm=3.50)
        self.assertEqual(cpm_pricing.cpm, 3.50)
        self.assertIsNone(cpm_pricing.revenue_share_percentage)
        
        # Revenue share only
        revenue_share_pricing = PricingModel(revenue_share_percentage=15.0)
        self.assertEqual(revenue_share_pricing.revenue_share_percentage, 15.0)
        self.assertIsNone(revenue_share_pricing.cpm)
        
        # Both models
        both_pricing = PricingModel(cpm=2.50, revenue_share_percentage=12.0)
        self.assertEqual(both_pricing.cpm, 2.50)
        self.assertEqual(both_pricing.revenue_share_percentage, 12.0)
    


class TestDatabaseIntegration(unittest.TestCase):
    """Test database integration and sample data."""
    
    def test_database_initialization(self):
        """Test that database initializes with sample data."""
        # Create temporary database
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Initialize with sample data
        from database import create_tables, insert_sample_data
        create_tables(cursor)
        insert_sample_data(cursor)
        conn.commit()
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = ["audience_segments", "platform_deployments", "usage_reports"]
        for table in expected_tables:
            self.assertIn(table, tables)
        
        # Verify sample data was inserted
        cursor.execute("SELECT COUNT(*) FROM audience_segments")
        segment_count = cursor.fetchone()[0]
        self.assertGreater(segment_count, 0)
        
        cursor.execute("SELECT COUNT(*) FROM platform_deployments") 
        deployment_count = cursor.fetchone()[0]
        self.assertGreater(deployment_count, 0)
        
        conn.close()


if __name__ == "__main__":
    unittest.main()