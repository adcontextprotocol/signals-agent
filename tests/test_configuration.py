#!/usr/bin/env python3
"""Configuration and Environment Tests."""

import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_loader import load_config


class TestConfiguration:
    """Test suite for configuration loading and environment variables."""
    
    def test_env_var_priority(self):
        """Test that environment variables override config.json."""
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "gemini_api_key": "key_from_config",
                "test_value": "config_value"
            }
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            # Test with environment variable
            with patch.dict(os.environ, {
                "GEMINI_API_KEY": "key_from_env",
                "CONFIG_PATH": config_path
            }):
                config = load_config()
                assert config.get("gemini_api_key") == "key_from_env"
                assert config.get("test_value") == "config_value"
        finally:
            os.unlink(config_path)
    
    def test_config_file_fallback(self):
        """Test that config.json is used when env vars not set."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "gemini_api_key": "test_key_123",
                "platforms": {
                    "test-platform": {
                        "enabled": True
                    }
                }
            }
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            with patch.dict(os.environ, {"CONFIG_PATH": config_path}, clear=True):
                config = load_config()
                assert config.get("gemini_api_key") == "test_key_123"
                assert config.get("platforms", {}).get("test-platform", {}).get("enabled") is True
        finally:
            os.unlink(config_path)
    
    def test_missing_config_file(self):
        """Test behavior when config file doesn't exist."""
        with patch.dict(os.environ, {"CONFIG_PATH": "/nonexistent/config.json"}, clear=True):
            config = load_config()
            # Should return empty dict or defaults
            assert isinstance(config, dict)
    
    def test_platform_configuration(self):
        """Test platform-specific configuration loading."""
        config_data = {
            "platforms": {
                "index-exchange": {
                    "enabled": True,
                    "base_url": "https://api.example.com",
                    "username": "test_user",
                    "password": "test_pass",
                    "cache_duration_seconds": 30,
                    "principal_accounts": {
                        "principal1": "account1"
                    }
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            with patch.dict(os.environ, {"CONFIG_PATH": config_path}):
                config = load_config()
                ix_config = config.get("platforms", {}).get("index-exchange", {})
                
                assert ix_config.get("enabled") is True
                assert ix_config.get("base_url") == "https://api.example.com"
                assert ix_config.get("username") == "test_user"
                assert ix_config.get("cache_duration_seconds") == 30
                assert ix_config.get("principal_accounts", {}).get("principal1") == "account1"
        finally:
            os.unlink(config_path)
    
    def test_database_configuration(self):
        """Test database path configuration."""
        config_data = {
            "database_path": "/custom/path/signals.db"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            with patch.dict(os.environ, {"CONFIG_PATH": config_path}):
                config = load_config()
                assert config.get("database_path") == "/custom/path/signals.db"
        finally:
            os.unlink(config_path)
    
    def test_sensitive_data_masking(self):
        """Test that sensitive data is properly handled."""
        config_data = {
            "gemini_api_key": "secret_key_12345",
            "platforms": {
                "test": {
                    "password": "secret_password",
                    "api_key": "secret_api_key"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            with patch.dict(os.environ, {"CONFIG_PATH": config_path}):
                config = load_config()
                
                # Verify sensitive data is loaded (not masked in config itself)
                assert config.get("gemini_api_key") == "secret_key_12345"
                assert config.get("platforms", {}).get("test", {}).get("password") == "secret_password"
                
                # In a real implementation, logging should mask these values
                # This is a placeholder for that test
        finally:
            os.unlink(config_path)
    
    def test_config_validation(self):
        """Test that invalid config is handled gracefully."""
        invalid_configs = [
            "not a json object",  # Invalid JSON
            {"platforms": "should be dict"},  # Wrong type
            {"platforms": {"test": ["should be dict"]}},  # Wrong nested type
        ]
        
        for invalid_config in invalid_configs:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                if isinstance(invalid_config, str):
                    f.write(invalid_config)
                else:
                    json.dump(invalid_config, f)
                config_path = f.name
            
            try:
                with patch.dict(os.environ, {"CONFIG_PATH": config_path}):
                    config = load_config()
                    # Should handle gracefully and return dict
                    assert isinstance(config, dict)
            finally:
                os.unlink(config_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])