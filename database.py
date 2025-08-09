"""Database initialization and sample data for the Signals Agent."""

import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any


def init_db():
    """Initialize the database with tables and sample data."""
    db_path = os.environ.get('DATABASE_PATH', 'signals_agent.db')
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    
    # Enable WAL mode for better concurrent access
    cursor.execute("PRAGMA journal_mode=WAL")
    
    # Create tables
    create_tables(cursor)
    
    # Insert sample data
    insert_sample_data(cursor)
    
    conn.commit()
    conn.close()
    print("Database initialized with sample data")


def create_tables(cursor: sqlite3.Cursor):
    """Create all database tables."""
    
    # Signal segments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signal_segments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            data_provider TEXT NOT NULL,
            coverage_percentage REAL NOT NULL,
            signal_type TEXT NOT NULL CHECK (signal_type IN ('private', 'marketplace', 'audience', 'bidding', 'contextual', 'geographical', 'temporal', 'environmental')),
            catalog_access TEXT NOT NULL CHECK (catalog_access IN ('public', 'personalized', 'private')),
            base_cpm REAL NOT NULL,
            revenue_share_percentage REAL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # Principals table (for access control)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS principals (
            principal_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            access_level TEXT NOT NULL CHECK (access_level IN ('public', 'personalized', 'private')),
            description TEXT,
            created_at TEXT NOT NULL
        )
    """)
    
    # Principal segment access table (for personalized catalogs)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS principal_segment_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            principal_id TEXT NOT NULL,
            signals_agent_segment_id TEXT NOT NULL,
            access_type TEXT NOT NULL CHECK (access_type IN ('granted', 'custom_pricing')),
            custom_cpm REAL,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (principal_id) REFERENCES principals (principal_id),
            FOREIGN KEY (signals_agent_segment_id) REFERENCES signal_segments (id),
            UNIQUE(principal_id, signals_agent_segment_id)
        )
    """)
    
    # Platform deployments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS platform_deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signals_agent_segment_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            account TEXT,
            decisioning_platform_segment_id TEXT,
            scope TEXT NOT NULL CHECK (scope IN ('platform-wide', 'account-specific')),
            is_live BOOLEAN NOT NULL DEFAULT 0,
            deployed_at TEXT,
            estimated_activation_duration_minutes INTEGER NOT NULL DEFAULT 60,
            FOREIGN KEY (signals_agent_segment_id) REFERENCES signal_segments (id),
            UNIQUE(signals_agent_segment_id, platform, account)
        )
    """)
    
    # Unified contexts table for all context types (A2A-ready)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contexts (
            context_id TEXT PRIMARY KEY,
            context_type TEXT NOT NULL CHECK (context_type IN ('discovery', 'activation', 'optimization', 'reporting')),
            parent_context_id TEXT,
            principal_id TEXT,
            metadata TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'expired')),
            created_at TEXT NOT NULL,
            completed_at TEXT,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (parent_context_id) REFERENCES contexts (context_id)
        )
    """)
    
    # Create index for efficient lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_contexts_type_principal 
        ON contexts (context_type, principal_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_contexts_parent 
        ON contexts (parent_context_id)
    """)
    
    # LiveRamp marketplace segments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS liveramp_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            segment_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            provider_name TEXT,
            segment_type TEXT,
            reach_count INTEGER,
            has_pricing BOOLEAN,
            cpm_price REAL,
            categories TEXT,
            raw_data TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create FTS5 virtual table for full-text search
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS liveramp_segments_fts 
        USING fts5(
            segment_id UNINDEXED,
            name,
            description,
            provider_name,
            categories,
            content=liveramp_segments,
            content_rowid=id
        ) 
    """)
    
    # Create trigger to keep FTS in sync
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS liveramp_segments_ai 
        AFTER INSERT ON liveramp_segments BEGIN
            INSERT INTO liveramp_segments_fts(
                rowid, segment_id, name, description, provider_name, categories
            ) VALUES (
                new.id, new.segment_id, new.name, new.description, 
                new.provider_name, new.categories
            );
        END;
    """)
    
    # LiveRamp sync status table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS liveramp_sync_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_started TIMESTAMP,
            sync_completed TIMESTAMP,
            total_segments INTEGER,
            status TEXT,
            error_message TEXT
        )
    """)
    


def insert_sample_data(cursor: sqlite3.Cursor):
    """Insert sample signal segments and platform deployments."""
    
    now = datetime.now().isoformat()
    
    # Sample signal segments
    segments = [
        {
            'id': 'sports_enthusiasts_public',
            'name': 'Sports Enthusiasts - Public',
            'description': 'Broad sports audience available platform-wide',
            'data_provider': 'Polk',
            'coverage_percentage': 45.0,
            'signal_type': 'audience',
            'catalog_access': 'public',
            'base_cpm': 3.50,
            'revenue_share_percentage': 15.0,
        },
        {
            'id': 'luxury_auto_intenders',
            'name': 'Luxury Automotive Intenders',
            'description': 'High-income individuals showing luxury car purchase intent',
            'data_provider': 'Experian',
            'coverage_percentage': 12.5,
            'signal_type': 'audience',
            'catalog_access': 'personalized',
            'base_cpm': 8.75,
            'revenue_share_percentage': 20.0,
        },
        {
            'id': 'peer39_luxury_auto',
            'name': 'Luxury Automotive Context',
            'description': 'Pages with luxury automotive content and high viewability',
            'data_provider': 'Peer39',
            'coverage_percentage': 15.0,
            'signal_type': 'audience',
            'catalog_access': 'public',
            'base_cpm': 2.50,
            'revenue_share_percentage': 12.0,
        },
        {
            'id': 'running_gear_premium',
            'name': 'Premium Running Gear Buyers',
            'description': 'High-income consumers who purchase premium athletic equipment',
            'data_provider': 'Acxiom',
            'coverage_percentage': 8.3,
            'signal_type': 'audience',
            'catalog_access': 'personalized',
            'base_cpm': 6.25,
            'revenue_share_percentage': 18.0,
        },
        {
            'id': 'urban_millennials',
            'name': 'Urban Millennials',
            'description': 'Millennials living in major urban markets with disposable income',
            'data_provider': 'LiveRamp',
            'coverage_percentage': 32.0,
            'signal_type': 'audience',
            'catalog_access': 'public',
            'base_cpm': 4.00,
            'revenue_share_percentage': 15.0,
        },
        {
            'id': 'private_customer_segments',
            'name': 'Private Customer Segments',
            'description': 'Proprietary first-party audience segments',
            'data_provider': 'Internal',
            'coverage_percentage': 100.0,
            'signal_type': 'audience',
            'catalog_access': 'private',
            'base_cpm': 0.00,
            'revenue_share_percentage': None,
        },
        # New signal types examples
        {
            'id': 'weather_based_targeting',
            'name': 'Weather-Based Targeting',
            'description': 'Environmental signals for weather conditions (sunny, rainy, cold)',
            'data_provider': 'WeatherData',
            'coverage_percentage': 95.0,
            'signal_type': 'environmental',
            'catalog_access': 'public',
            'base_cpm': 1.50,
            'revenue_share_percentage': 10.0,
        },
        {
            'id': 'geo_urban_centers',
            'name': 'Major Urban Centers',
            'description': 'Geographical signals for top 50 US metropolitan areas',
            'data_provider': 'GeoTarget',
            'coverage_percentage': 68.0,
            'signal_type': 'geographical',
            'catalog_access': 'public',
            'base_cpm': 2.00,
            'revenue_share_percentage': 12.0,
        },
        {
            'id': 'prime_time_viewing',
            'name': 'Prime Time TV Viewing',
            'description': 'Temporal signals for evening hours (6PM-11PM local time)',
            'data_provider': 'TimeTarget',
            'coverage_percentage': 100.0,
            'signal_type': 'temporal',
            'catalog_access': 'public',
            'base_cpm': 3.00,
            'revenue_share_percentage': 15.0,
        },
        {
            'id': 'contextual_news_finance',
            'name': 'Financial News Context',
            'description': 'Contextual signals for financial and business news content',
            'data_provider': 'Peer39',
            'coverage_percentage': 22.0,
            'signal_type': 'contextual',
            'catalog_access': 'public',
            'base_cpm': 4.50,
            'revenue_share_percentage': 18.0,
        }
    ]
    
    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM signal_segments")
    existing_count = cursor.fetchone()[0]
    
    if existing_count > 0:
        print(f"Database already contains {existing_count} segments, skipping data insertion")
        return
    
    for segment in segments:
        cursor.execute("""
            INSERT OR REPLACE INTO signal_segments 
            (id, name, description, data_provider, coverage_percentage, 
             signal_type, catalog_access, base_cpm, revenue_share_percentage, 
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            segment['id'], segment['name'], segment['description'], 
            segment['data_provider'], segment['coverage_percentage'],
            segment['signal_type'], segment['catalog_access'],
            segment['base_cpm'], segment['revenue_share_percentage'],
            now, now
        ))
    
    # Sample platform deployments
    deployments = [
        # Sports enthusiasts - already live on multiple platforms
        {
            'signals_agent_segment_id': 'sports_enthusiasts_public',
            'platform': 'the-trade-desk',
            'account': None,
            'decisioning_platform_segment_id': 'ttd_sports_general',
            'scope': 'platform-wide',
            'is_live': True,
            'deployed_at': now,
            'estimated_activation_duration_minutes': 60
        },
        {
            'signals_agent_segment_id': 'sports_enthusiasts_public',
            'platform': 'index-exchange',
            'account': None,
            'decisioning_platform_segment_id': 'ix_sports_enthusiasts_public',
            'scope': 'platform-wide',
            'is_live': True,
            'deployed_at': now,
            'estimated_activation_duration_minutes': 60
        },
        
        # Luxury auto - mix of live and requiring activation
        {
            'signals_agent_segment_id': 'peer39_luxury_auto',
            'platform': 'index-exchange',
            'account': None,
            'decisioning_platform_segment_id': 'ix_peer39_luxury_auto_gen',
            'scope': 'platform-wide',
            'is_live': True,
            'deployed_at': now,
            'estimated_activation_duration_minutes': 60
        },
        {
            'signals_agent_segment_id': 'peer39_luxury_auto',
            'platform': 'openx',
            'account': None,
            'decisioning_platform_segment_id': 'ox_peer39_lux_auto_456',
            'scope': 'platform-wide',
            'is_live': True,
            'deployed_at': now,
            'estimated_activation_duration_minutes': 60
        },
        {
            'signals_agent_segment_id': 'peer39_luxury_auto',
            'platform': 'pubmatic',
            'account': 'brand-456-pm',
            'decisioning_platform_segment_id': None,
            'scope': 'account-specific',
            'is_live': False,
            'deployed_at': None,
            'estimated_activation_duration_minutes': 60
        },
        {
            'signals_agent_segment_id': 'peer39_luxury_auto',
            'platform': 'index-exchange',
            'account': 'agency-123-ix',
            'decisioning_platform_segment_id': 'ix_agency123_peer39_lux_auto',
            'scope': 'account-specific',
            'is_live': True,
            'deployed_at': now,
            'estimated_activation_duration_minutes': 60
        },
        
        # Urban millennials - live on TTD
        {
            'signals_agent_segment_id': 'urban_millennials',
            'platform': 'the-trade-desk',
            'account': None,
            'decisioning_platform_segment_id': 'ttd_urban_millennials_gen',
            'scope': 'platform-wide',
            'is_live': True,
            'deployed_at': now,
            'estimated_activation_duration_minutes': 60
        },
        
        # Premium running gear - personalized, requiring activation
        {
            'signals_agent_segment_id': 'running_gear_premium',
            'platform': 'the-trade-desk',
            'account': 'omnicom-ttd-main',
            'decisioning_platform_segment_id': None,
            'scope': 'account-specific',
            'is_live': False,
            'deployed_at': None,
            'estimated_activation_duration_minutes': 120
        }
    ]
    
    for deployment in deployments:
        cursor.execute("""
            INSERT OR REPLACE INTO platform_deployments 
            (signals_agent_segment_id, platform, account, decisioning_platform_segment_id,
             scope, is_live, deployed_at, estimated_activation_duration_minutes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            deployment['signals_agent_segment_id'], deployment['platform'],
            deployment['account'], deployment['decisioning_platform_segment_id'],
            deployment['scope'], deployment['is_live'], deployment['deployed_at'],
            deployment['estimated_activation_duration_minutes']
        ))
    
    # Insert sample principals
    principals = [
        {
            'principal_id': 'public',
            'name': 'Public Access',
            'access_level': 'public',
            'description': 'Default public access - sees only public catalog segments'
        },
        {
            'principal_id': 'acme_corp',
            'name': 'ACME Corporation',
            'access_level': 'personalized',
            'description': 'Large advertiser with personalized catalog access and custom pricing'
        },
        {
            'principal_id': 'luxury_brands_inc',
            'name': 'Luxury Brands Inc',
            'access_level': 'personalized', 
            'description': 'Premium luxury brand advertiser with specialized segments'
        },
        {
            'principal_id': 'startup_agency',
            'name': 'Startup Digital Agency',
            'access_level': 'public',
            'description': 'Small agency with public catalog access only'
        },
        {
            'principal_id': 'auto_manufacturer',
            'name': 'Global Auto Manufacturer',
            'access_level': 'private',
            'description': 'Private client with exclusive custom segments'
        }
    ]
    
    for principal in principals:
        cursor.execute("""
            INSERT OR REPLACE INTO principals 
            (principal_id, name, access_level, description, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            principal['principal_id'], principal['name'], principal['access_level'],
            principal['description'], now
        ))
    
    # Insert principal-specific segment access
    principal_access = [
        # ACME Corp gets custom pricing on some segments
        {
            'principal_id': 'acme_corp',
            'signals_agent_segment_id': 'luxury_auto_intenders',
            'access_type': 'custom_pricing',
            'custom_cpm': 6.50,  # Discounted from 8.75
            'notes': 'Volume discount for large advertiser'
        },
        {
            'principal_id': 'acme_corp', 
            'signals_agent_segment_id': 'sports_enthusiasts_public',
            'access_type': 'custom_pricing',
            'custom_cpm': 2.75,  # Discounted from 3.50
            'notes': 'Preferred customer pricing'
        },
        
        # Luxury Brands Inc gets exclusive access to luxury segments
        {
            'principal_id': 'luxury_brands_inc',
            'signals_agent_segment_id': 'luxury_auto_intenders', 
            'access_type': 'granted',
            'custom_cpm': None,
            'notes': 'Exclusive access to luxury audience'
        },
        
        # Auto Manufacturer gets private segments (we'll add these next)
        # For now, they also get custom pricing on automotive segments
    ]
    
    for access in principal_access:
        cursor.execute("""
            INSERT OR REPLACE INTO principal_segment_access
            (principal_id, signals_agent_segment_id, access_type, custom_cpm, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            access['principal_id'], access['signals_agent_segment_id'], 
            access['access_type'], access['custom_cpm'], access['notes'], now
        ))


if __name__ == "__main__":
    init_db()