#!/usr/bin/env python3
"""
Offline sync script for LiveRamp Data Marketplace catalog.
Run this as a scheduled job (daily/weekly) to keep the catalog up to date.

Usage:
    python sync_liveramp_catalog.py [--full]
    
Options:
    --full    Force a full resync (ignore cache age)
"""

import sys
import os
import json
import sqlite3
import requests
import time
import argparse
from datetime import datetime
from typing import List, Dict, Any
from config_loader import load_config


class LiveRampCatalogSync:
    """Handles offline synchronization of LiveRamp catalog."""
    
    def __init__(self):
        self.config = load_config()
        self.lr_config = self.config['platforms']['liveramp']
        # Use environment variable for database path if available (for Fly.io)
        self.db_path = os.environ.get('DATABASE_PATH', self.config['database']['path'])
        self.auth_token = None
        self.token_expires_at = None
        
    def authenticate(self):
        """Authenticate with LiveRamp."""
        print("Authenticating with LiveRamp...")
        
        token_uri = self.lr_config.get('token_uri', 'https://serviceaccounts.liveramp.com/authn/v1/oauth2/token')
        
        data = {
            'grant_type': 'password',
            'client_id': self.lr_config['client_id'],
            'username': self.lr_config['account_id'],
            'password': self.lr_config['secret_key']
        }
        
        response = requests.post(token_uri, data=data)
        
        if response.status_code != 200:
            raise Exception(f"Authentication failed: {response.status_code} {response.text}")
        
        token_data = response.json()
        self.auth_token = token_data.get('access_token')
        expires_in = token_data.get('expires_in', 3600)
        self.token_expires_at = datetime.now().timestamp() + expires_in
        
        print("✓ Authentication successful")
    
    def is_token_valid(self):
        """Check if token is still valid."""
        if not self.auth_token or not self.token_expires_at:
            return False
        return datetime.now().timestamp() < (self.token_expires_at - 300)
    
    def fetch_all_segments(self, max_segments: int = None) -> List[Dict]:
        """Fetch all segments from LiveRamp with pagination."""
        if not self.is_token_valid():
            self.authenticate()
        
        base_url = self.lr_config.get('base_url', 'https://api.liveramp.com')
        segments_url = f"{base_url}/data-marketplace/buyer-api/v3/segments"
        
        headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Accept': 'application/json',
            'LR-Org-Id': self.lr_config.get('owner_org', '')
        }
        
        all_segments = []
        after_cursor = None
        page = 0
        limit = 100  # Max per request
        
        print(f"Fetching segments from LiveRamp Data Marketplace...")
        
        while True:
            # Re-authenticate if token expired during sync
            if not self.is_token_valid():
                self.authenticate()
                headers['Authorization'] = f'Bearer {self.auth_token}'
            
            params = {'limit': limit}
            if after_cursor:
                params['after'] = after_cursor
            
            try:
                response = requests.get(segments_url, headers=headers, params=params, timeout=30)
                
                if response.status_code == 429:  # Rate limited
                    wait_time = int(response.headers.get('Retry-After', 60))
                    print(f"Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                
                if response.status_code != 200:
                    print(f"Error fetching page {page + 1}: {response.status_code}")
                    if page > 0:  # Continue if we already have some data
                        break
                    raise Exception(f"Failed to fetch segments: {response.status_code} {response.text}")
                
                data = response.json()
                segments = data.get('v3_Segments', [])
                
                if not segments:
                    print(f"No more segments at page {page + 1}")
                    break
                
                all_segments.extend(segments)
                
                # Get next cursor
                pagination = data.get('_pagination', {})
                after_cursor = pagination.get('after')
                
                print(f"  Page {page + 1}: Retrieved {len(segments)} segments (total: {len(all_segments)})")
                
                # Check if we've reached the limit
                if max_segments and len(all_segments) >= max_segments:
                    print(f"Reached limit of {max_segments} segments")
                    all_segments = all_segments[:max_segments]
                    break
                
                # If no cursor, we've reached the end
                if not after_cursor:
                    print("Reached end of catalog")
                    break
                
                page += 1
                
                # Rate limiting - be nice to the API
                time.sleep(0.5)
                
            except requests.exceptions.Timeout:
                print(f"Timeout on page {page + 1}, retrying...")
                time.sleep(5)
                continue
                
            except Exception as e:
                print(f"Error on page {page + 1}: {e}")
                if page > 0:  # Continue if we already have some data
                    break
                raise
        
        return all_segments
    
    def store_segments(self, segments: List[Dict]):
        """Store segments in the database."""
        print(f"Storing {len(segments)} segments in database...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Begin transaction for atomic operations
            cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
            
            # Clear old LiveRamp segments within transaction
            cursor.execute("DELETE FROM liveramp_segments")
            cursor.execute("DELETE FROM liveramp_segments_fts")
        
        # Prepare batch insert data
        segment_data = []
        
        for segment in segments:
            segment_id = str(segment.get('id'))
            name = segment.get('name', '')
            description = segment.get('description', '')
            provider = segment.get('providerName', '')
            segment_type = segment.get('segmentType', '')
            
            # Extract reach
            reach_count = None
            reach_info = segment.get('reach', {})
            if isinstance(reach_info, dict):
                input_records = reach_info.get('inputRecords', {})
                if isinstance(input_records, dict):
                    reach_count = input_records.get('count')
            
            # Extract pricing
            has_pricing = False
            cpm_price = None
            subscriptions = segment.get('subscriptions', [])
            for sub in subscriptions:
                if isinstance(sub, dict):
                    price_info = sub.get('price', {})
                    if isinstance(price_info, dict):
                        cpm_price = price_info.get('cpm')
                        if cpm_price:
                            has_pricing = True
                            break
            
            # Extract categories
            categories = []
            for cat in segment.get('categories', []):
                if isinstance(cat, dict):
                    categories.append(cat.get('name', ''))
                else:
                    categories.append(str(cat))
            categories_str = ', '.join(categories)
            
            segment_data.append((
                segment_id, name, description, provider, segment_type,
                reach_count, has_pricing, cpm_price, categories_str,
                json.dumps(segment)
            ))
        
            # Batch insert
            cursor.executemany('''
                INSERT INTO liveramp_segments (
                    segment_id, name, description, provider_name, segment_type,
                    reach_count, has_pricing, cpm_price, categories, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', segment_data)
            
            # Commit transaction
            conn.commit()
            print(f"✓ Stored {len(segments)} segments successfully")
        except Exception as e:
            # Rollback on error
            conn.rollback()
            print(f"Error storing segments: {e}")
            raise
        finally:
            conn.close()
    
    def update_sync_status(self, status: str, total_segments: int = 0, error: str = None):
        """Update sync status in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status == 'started':
            cursor.execute('''
                INSERT INTO liveramp_sync_status (sync_started, status)
                VALUES (?, ?)
            ''', (datetime.now().isoformat(), 'in_progress'))
        else:
            # Update the most recent sync record
            cursor.execute('''
                UPDATE liveramp_sync_status 
                SET sync_completed = ?, total_segments = ?, status = ?, error_message = ?
                WHERE id = (SELECT MAX(id) FROM liveramp_sync_status)
            ''', (datetime.now().isoformat(), total_segments, status, error))
        
        conn.commit()
        conn.close()
    
    def needs_sync(self, max_age_hours: int = 24) -> bool:
        """Check if catalog needs to be synced."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check last successful sync
        cursor.execute('''
            SELECT sync_completed FROM liveramp_sync_status 
            WHERE status = 'success'
            ORDER BY id DESC LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or not row[0]:
            return True
        
        last_sync = datetime.fromisoformat(row[0])
        age_hours = (datetime.now() - last_sync).total_seconds() / 3600
        
        return age_hours > max_age_hours
    
    def get_statistics(self):
        """Get statistics about the synced catalog."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total segments
        cursor.execute('SELECT COUNT(*) FROM liveramp_segments')
        stats['total_segments'] = cursor.fetchone()[0]
        
        # Segments with pricing
        cursor.execute('SELECT COUNT(*) FROM liveramp_segments WHERE has_pricing = 1')
        stats['segments_with_pricing'] = cursor.fetchone()[0]
        
        # Segments with reach
        cursor.execute('SELECT COUNT(*) FROM liveramp_segments WHERE reach_count IS NOT NULL')
        stats['segments_with_reach'] = cursor.fetchone()[0]
        
        # Top providers
        cursor.execute('''
            SELECT provider_name, COUNT(*) as count 
            FROM liveramp_segments 
            GROUP BY provider_name 
            ORDER BY count DESC 
            LIMIT 10
        ''')
        stats['top_providers'] = cursor.fetchall()
        
        # Last sync
        cursor.execute('''
            SELECT sync_completed, total_segments, status 
            FROM liveramp_sync_status 
            ORDER BY id DESC LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            stats['last_sync'] = row[0]
            stats['last_sync_segments'] = row[1]
            stats['last_sync_status'] = row[2]
        
        conn.close()
        return stats
    
    def run_sync(self, force: bool = False, max_segments: int = None):
        """Run the sync process."""
        print("\n" + "="*60)
        print("LiveRamp Catalog Sync")
        print("="*60)
        
        # Check if sync is needed
        if not force and not self.needs_sync():
            print("Catalog is up to date (synced within last 24 hours)")
            stats = self.get_statistics()
            print(f"Current catalog: {stats['total_segments']} segments")
            print(f"Last sync: {stats.get('last_sync', 'Never')}")
            return
        
        try:
            # Mark sync as started
            self.update_sync_status('started')
            
            # Fetch segments
            start_time = time.time()
            segments = self.fetch_all_segments(max_segments)
            fetch_time = time.time() - start_time
            
            if not segments:
                raise Exception("No segments retrieved")
            
            # Store segments
            store_start = time.time()
            self.store_segments(segments)
            store_time = time.time() - store_start
            
            # Update status
            self.update_sync_status('success', len(segments))
            
            # Print summary
            total_time = time.time() - start_time
            print("\n" + "="*60)
            print("Sync Complete!")
            print(f"  Total segments: {len(segments)}")
            print(f"  Fetch time: {fetch_time:.1f} seconds")
            print(f"  Store time: {store_time:.1f} seconds")
            print(f"  Total time: {total_time:.1f} seconds")
            
            # Show statistics
            stats = self.get_statistics()
            print(f"\nCatalog Statistics:")
            print(f"  Segments with pricing: {stats['segments_with_pricing']}")
            print(f"  Segments with reach: {stats['segments_with_reach']}")
            print(f"\nTop Providers:")
            for provider, count in stats['top_providers'][:5]:
                print(f"  {provider}: {count} segments")
            
        except Exception as e:
            print(f"\n[ERROR] Sync failed: {e}")
            self.update_sync_status('failed', 0, str(e))
            raise


def main():
    parser = argparse.ArgumentParser(description='Sync LiveRamp Data Marketplace catalog')
    parser.add_argument('--full', action='store_true', help='Force full resync')
    parser.add_argument('--limit', type=int, help='Limit number of segments (for testing)')
    args = parser.parse_args()
    
    syncer = LiveRampCatalogSync()
    
    try:
        syncer.run_sync(force=args.full, max_segments=args.limit)
    except KeyboardInterrupt:
        print("\nSync interrupted by user")
        syncer.update_sync_status('cancelled')
        sys.exit(1)
    except Exception as e:
        print(f"\nSync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()