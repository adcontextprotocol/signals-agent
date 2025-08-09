"""Configuration loader with environment variable support."""

import os
import json
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.json with environment variable overrides.
    
    Environment variables:
    - GEMINI_API_KEY: Overrides gemini_api_key
    - IX_USERNAME: Overrides platforms.index-exchange.username
    - IX_PASSWORD: Overrides platforms.index-exchange.password
    - IX_ACCOUNT_MAPPING: JSON string for principal account mappings
    - LIVERAMP_CLIENT_ID: Overrides platforms.liveramp.client_id
    - LIVERAMP_ACCOUNT_ID: Overrides platforms.liveramp.account_id
    - LIVERAMP_SECRET_KEY: Overrides platforms.liveramp.secret_key
    - LIVERAMP_UID: Overrides platforms.liveramp.uid
    - LIVERAMP_OWNER_ORG: Overrides platforms.liveramp.owner_org
    - LIVERAMP_TOKEN_URI: Overrides platforms.liveramp.token_uri
    - LIVERAMP_ACCOUNT_MAPPING: JSON string for principal account mappings
    """
    # Load base config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        # If no config.json, start with sample
        with open('config.json.sample', 'r') as f:
            config = json.load(f)
    
    # Override with environment variables
    if gemini_key := os.environ.get('GEMINI_API_KEY'):
        config['gemini_api_key'] = gemini_key
    
    # Platform-specific overrides
    if 'platforms' in config:
        # Index Exchange overrides
        if 'index-exchange' in config['platforms']:
            if ix_username := os.environ.get('IX_USERNAME'):
                config['platforms']['index-exchange']['username'] = ix_username
            
            if ix_password := os.environ.get('IX_PASSWORD'):
                config['platforms']['index-exchange']['password'] = ix_password
            
            # Account mappings (JSON string)
            if ix_mappings := os.environ.get('IX_ACCOUNT_MAPPING'):
                try:
                    mappings = json.loads(ix_mappings)
                    config['platforms']['index-exchange']['principal_accounts'] = mappings
                except json.JSONDecodeError:
                    print(f"Warning: Invalid IX_ACCOUNT_MAPPING JSON: {ix_mappings}")
            
            # Default account for Index Exchange
            if ix_default_account := os.environ.get('IX_DEFAULT_ACCOUNT'):
                if 'principal_accounts' not in config['platforms']['index-exchange']:
                    config['platforms']['index-exchange']['principal_accounts'] = {}
                # Set default account for common principals
                config['platforms']['index-exchange']['principal_accounts']['default'] = ix_default_account
                config['platforms']['index-exchange']['principal_accounts']['acme_corp'] = ix_default_account
                config['platforms']['index-exchange']['principal_accounts']['luxury_brands_inc'] = ix_default_account
                config['platforms']['index-exchange']['principal_accounts']['auto_manufacturer'] = ix_default_account
        
        # LiveRamp overrides
        if 'liveramp' in config['platforms']:
            if lr_client_id := os.environ.get('LIVERAMP_CLIENT_ID'):
                config['platforms']['liveramp']['client_id'] = lr_client_id
                # Enable LiveRamp if credentials are provided
                config['platforms']['liveramp']['enabled'] = True
            
            if lr_account_id := os.environ.get('LIVERAMP_ACCOUNT_ID'):
                config['platforms']['liveramp']['account_id'] = lr_account_id
            
            if lr_secret_key := os.environ.get('LIVERAMP_SECRET_KEY'):
                config['platforms']['liveramp']['secret_key'] = lr_secret_key
                # Also set as client_secret for compatibility
                config['platforms']['liveramp']['client_secret'] = lr_secret_key
            
            if lr_uid := os.environ.get('LIVERAMP_UID'):
                config['platforms']['liveramp']['uid'] = lr_uid
            
            if lr_owner_org := os.environ.get('LIVERAMP_OWNER_ORG'):
                config['platforms']['liveramp']['owner_org'] = lr_owner_org
            
            if lr_token_uri := os.environ.get('LIVERAMP_TOKEN_URI'):
                config['platforms']['liveramp']['token_uri'] = lr_token_uri
            
            # Account mappings (JSON string)
            if lr_mappings := os.environ.get('LIVERAMP_ACCOUNT_MAPPING'):
                try:
                    mappings = json.loads(lr_mappings)
                    config['platforms']['liveramp']['principal_accounts'] = mappings
                except json.JSONDecodeError:
                    print(f"Warning: Invalid LIVERAMP_ACCOUNT_MAPPING JSON: {lr_mappings}")
            
            # Default account for LiveRamp
            if lr_account_id := os.environ.get('LIVERAMP_ACCOUNT_ID'):
                if 'principal_accounts' not in config['platforms']['liveramp']:
                    config['platforms']['liveramp']['principal_accounts'] = {}
                # Set default account for common principals
                config['platforms']['liveramp']['principal_accounts']['default'] = lr_account_id
                config['platforms']['liveramp']['principal_accounts']['acme_corp'] = lr_account_id
                config['platforms']['liveramp']['principal_accounts']['luxury_brands_inc'] = lr_account_id
    
    # Database path override (useful for Docker volumes)
    if db_path := os.environ.get('DATABASE_PATH'):
        config['database']['path'] = db_path
    
    return config

def get_secret(key: str, default: str = None) -> str:
    """Get a secret from environment or config."""
    return os.environ.get(key, default)