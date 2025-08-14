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
from embeddings import EmbeddingsManager


class LiveRampCatalogSync:
    """Handles offline synchronization of LiveRamp catalog."""
    
    def __init__(self):
        self.config = load_config()
        self.lr_config = self.config['platforms']['liveramp']
        # Use environment variable for database path if available (for Fly.io)
        self.db_path = os.environ.get('DATABASE_PATH', self.config['database']['path'])
        self.auth_token = None
        self.token_expires_at = None
        # Initialize embeddings manager if Gemini is configured
        self.embeddings_manager = None
        if self.config.get('gemini_api_key'):
            try:
                self.embeddings_manager = EmbeddingsManager(self.config, self.db_path)
                print("✓ Embeddings manager initialized")
            except Exception as e:
                print(f"Warning: Could not initialize embeddings manager: {e}")
                print("  Embeddings will not be generated during sync")
        
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
    
    def fetch_all_segments(self, max_segments: int = None, incremental: bool = False, write_callback=None) -> List[Dict]:
        """Fetch all segments from LiveRamp with pagination.
        
        Args:
            max_segments: Maximum number of segments to fetch
            incremental: If True, only fetch segments updated since last sync
            write_callback: Optional callback to write segments as we fetch them
        """
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
        # LiveRamp API maximum is 100 per page
        limit = 100  # Maximum allowed by LiveRamp API
        
        # Check for last sync time if incremental
        last_sync_time = None
        if incremental:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sync_completed FROM liveramp_sync_status 
                WHERE status = 'success'
                ORDER BY id DESC LIMIT 1
            ''')
            row = cursor.fetchone()
            if row and row[0]:
                last_sync_time = row[0]
                print(f"Incremental sync: fetching segments updated since {last_sync_time}")
            conn.close()
        
        print(f"Fetching segments from LiveRamp Data Marketplace (page size: {limit})...")
        
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
                
                # Filter by update time if incremental
                if incremental and last_sync_time:
                    filtered_segments = []
                    for seg in segments:
                        # Check if segment has an update timestamp
                        updated_at = seg.get('updatedAt') or seg.get('updated_at') or seg.get('lastModified')
                        if updated_at and updated_at > last_sync_time:
                            filtered_segments.append(seg)
                    segments = filtered_segments
                    if not segments:
                        print(f"  Page {page + 1}: No new segments (skipping)")
                        page += 1
                        continue
                
                # Write segments incrementally if callback provided
                if write_callback:
                    write_callback(segments)
                    print(f"  Page {page + 1}: Wrote {len(segments)} segments (total processed: {len(all_segments) + len(segments)})")
                else:
                    all_segments.extend(segments)
                    print(f"  Page {page + 1}: Retrieved {len(segments)} segments (total: {len(all_segments)})")
                
                # Track all segments even if written incrementally
                if write_callback:
                    all_segments.extend(segments)  # Still track for count
                
                # Get next cursor
                pagination = data.get('_pagination', {})
                after_cursor = pagination.get('after')
                
                # Check if we've reached the limit
                if max_segments and len(all_segments) >= max_segments:
                    print(f"Reached limit of {max_segments} segments")
                    if not write_callback:
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
    
    def store_segments(self, segments: List[Dict], append: bool = False):
        """Store segments in the database.
        
        Args:
            segments: List of segments to store
            append: If True, append to existing data instead of replacing
        """
        if not segments:
            return
        
        print(f"Storing {len(segments)} segments in database (append={append})...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Begin transaction for atomic operations
            cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
            
            # Only clear if not appending
            if not append:
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
                
                # Extract pricing (Enhanced to check multiple locations)
                has_pricing = False
                cpm_price = None
                
                # Method 1: Check subscriptions (most common)
                subscriptions = segment.get('subscriptions', [])
                if subscriptions and isinstance(subscriptions, list):
                    for sub in subscriptions:
                        if isinstance(sub, dict):
                            # Check price object
                            price_obj = sub.get('price', {})
                            if isinstance(price_obj, dict):
                                # Try different price fields
                                for price_field in ['cpm', 'CPM', 'value', 'Value', 'amount', 'cost']:
                                    price_val = price_obj.get(price_field)
                                    if price_val is not None:
                                        try:
                                            cpm_price = float(price_val)
                                            has_pricing = True
                                            break
                                        except (ValueError, TypeError):
                                            pass
                            
                            # Check subscription root for direct pricing
                            if not has_pricing:
                                for field in ['cpm', 'CPM', 'price', 'cost', 'fee']:
                                    if field in sub and sub[field] is not None:
                                        try:
                                            cpm_price = float(sub[field])
                                            has_pricing = True
                                            break
                                        except (ValueError, TypeError):
                                            pass
                        
                        if has_pricing:
                            break
                
                # Method 2: Check root level pricing fields
                if not has_pricing:
                    for field in ['price', 'pricing', 'cpm', 'CPM', 'cost', 'fee']:
                        if field in segment:
                            val = segment[field]
                            if isinstance(val, (int, float)):
                                try:
                                    cpm_price = float(val)
                                    has_pricing = True
                                    break
                                except (ValueError, TypeError):
                                    pass
                            elif isinstance(val, dict):
                                for subfield in ['cpm', 'CPM', 'value', 'amount']:
                                    if subfield in val and val[subfield] is not None:
                                        try:
                                            cpm_price = float(val[subfield])
                                            has_pricing = True
                                            break
                                        except (ValueError, TypeError):
                                            pass
                                if has_pricing:
                                    break
                
                # Method 3: Check 'pricing' field (LiveRamp specific structure)
                if not has_pricing:
                    pricing_obj = segment.get('pricing', {})
                    if pricing_obj:
                        # Try digitalAdTargeting first (most common for programmatic)
                        if 'digitalAdTargeting' in pricing_obj:
                            dat = pricing_obj['digitalAdTargeting']
                            if 'value' in dat and 'amount' in dat['value']:
                                amount = dat['value']['amount']
                                unit = dat['value'].get('unit', 'CENTS')
                                if unit == 'CENTS':
                                    cpm_price = amount / 100.0  # Convert cents to dollars
                                else:
                                    cpm_price = float(amount)
                                has_pricing = True
                        
                        # Fallback to tvTargeting
                        if not has_pricing and 'tvTargeting' in pricing_obj:
                            tv = pricing_obj['tvTargeting']
                            if 'value' in tv and 'amount' in tv['value']:
                                amount = tv['value']['amount']
                                unit = tv['value'].get('unit', 'CENTS')
                                if unit == 'CENTS':
                                    cpm_price = amount / 100.0
                                else:
                                    cpm_price = float(amount)
                                has_pricing = True
                        
                        # Fallback to contentMarketing
                        if not has_pricing and 'contentMarketing' in pricing_obj:
                            cm = pricing_obj['contentMarketing']
                            if 'value' in cm and 'amount' in cm['value']:
                                amount = cm['value']['amount']
                                unit = cm['value'].get('unit', 'CENTS')
                                if unit == 'CENTS':
                                    cpm_price = amount / 100.0
                                else:
                                    cpm_price = float(amount)
                                has_pricing = True
                
                # Method 4: Check if marked as free
                if not has_pricing:
                    if segment.get('isFree') or segment.get('is_free') or segment.get('free'):
                        cpm_price = 0.0
                        has_pricing = True
                
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
            
            # Batch insert with conflict resolution for incremental updates
            cursor.executemany('''
                INSERT OR REPLACE INTO liveramp_segments (
                    segment_id, name, description, provider_name, segment_type,
                    reach_count, has_pricing, cpm_price, categories, raw_data, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', segment_data)
            
            # Commit transaction
            conn.commit()
            print(f"✓ Stored {len(segments)} segments successfully")
            
            # Generate embeddings for the stored segments if embeddings manager is available
            if self.embeddings_manager:
                try:
                    print(f"  Generating embeddings for {len(segments)} segments...")
                    # Create a simplified list for embedding generation
                    segments_for_embedding = []
                    for seg in segments:
                        segments_for_embedding.append({
                            'segment_id': seg.get('segmentId'),
                            'name': seg.get('name', ''),
                            'description': seg.get('description', ''),
                            'providerName': seg.get('provider', {}).get('name', '') if isinstance(seg.get('provider'), dict) else '',
                            'segmentType': seg.get('segmentType', ''),
                            'categories': seg.get('categories', [])
                        })
                    
                    # Generate and store embeddings in smaller batches
                    batch_size = 10  # Small batches to avoid rate limits
                    for i in range(0, len(segments_for_embedding), batch_size):
                        batch = segments_for_embedding[i:i+batch_size]
                        self.embeddings_manager.generate_and_store_embeddings(batch)
                        if i + batch_size < len(segments_for_embedding):
                            time.sleep(0.5)  # Brief pause between batches
                    print(f"  ✓ Generated embeddings for {len(segments)} segments")
                except Exception as e:
                    print(f"  ⚠ Warning: Could not generate embeddings: {e}")
                    # Don't fail the sync if embeddings fail
        except Exception as e:
            # Rollback on error
            conn.rollback()
            print(f"Error storing segments: {e}")
            raise
        finally:
            conn.close()
    
    def update_sync_status(self, status: str, total_segments: int = 0, error: str = None, progress: int = None):
        """Update sync status in database.
        
        Args:
            status: Status string ('started', 'in_progress', 'success', 'failed')
            total_segments: Total segments processed
            error: Error message if failed
            progress: Current progress count for in-progress updates
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status == 'started':
            cursor.execute('''
                INSERT INTO liveramp_sync_status (sync_started, status, total_segments)
                VALUES (?, ?, ?)
            ''', (datetime.now().isoformat(), 'in_progress', 0))
        elif status == 'in_progress' and progress is not None:
            # Update progress during sync
            cursor.execute('''
                UPDATE liveramp_sync_status 
                SET total_segments = ?, last_updated = ?
                WHERE id = (SELECT MAX(id) FROM liveramp_sync_status)
            ''', (progress, datetime.now().isoformat()))
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
    
    def generate_embeddings(self, segments: List[Dict], batch_size: int = 50):
        """Generate embeddings for synced segments.
        
        Args:
            segments: List of segment dictionaries
            batch_size: Number of segments to process in each batch
        """
        if not self.embeddings_manager:
            print("Embeddings manager not available, skipping embedding generation")
            return
        
        print(f"\nGenerating embeddings for {len(segments)} segments...")
        start_time = time.time()
        
        try:
            self.embeddings_manager.generate_and_store_embeddings(segments, batch_size)
            duration = time.time() - start_time
            
            # Check status
            status = self.embeddings_manager.check_embeddings_status()
            print(f"✓ Embeddings generated in {duration:.1f} seconds")
            print(f"  Coverage: {status['segments_with_embeddings']}/{status['total_segments']} segments ({status['embeddings_coverage']:.1f}%)")
            
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            print("  Sync completed but embeddings may be incomplete")
    
    def run_sync(self, force: bool = False, max_segments: int = None, generate_embeddings: bool = True, incremental: bool = False):
        """Run the sync process.
        
        Args:
            force: Force sync even if not needed
            max_segments: Maximum segments to sync
            generate_embeddings: Whether to generate embeddings
            incremental: Only sync segments updated since last successful sync
        """
        print("\n" + "="*60)
        print(f"LiveRamp Catalog Sync {'(Incremental)' if incremental else '(Full)'}")
        print("="*60)
        
        # Check if sync is needed
        if not force and not incremental and not self.needs_sync():
            print("Catalog is up to date (synced within last 24 hours)")
            stats = self.get_statistics()
            print(f"Current catalog: {stats['total_segments']} segments")
            print(f"Last sync: {stats.get('last_sync', 'Never')}")
            return
        
        try:
            # Mark sync as started
            self.update_sync_status('started')
            
            # For incremental sync, don't clear existing data
            if incremental:
                print("Running incremental sync - will append new/updated segments")
            else:
                print("Running full sync - will replace all segments")
            
            # Track segments written
            total_written = 0
            segments_batch = []
            
            def write_batch(batch):
                """Write a batch of segments incrementally."""
                nonlocal total_written, segments_batch
                if batch:
                    # Store with append flag for incremental writes
                    self.store_segments(batch, append=(total_written > 0 or incremental))
                    total_written += len(batch)
                    segments_batch.extend(batch)
                    
                    # Update progress in database
                    self.update_sync_status('in_progress', progress=total_written)
                    
                    # Generate embeddings for this batch if requested
                    if generate_embeddings and self.embeddings_manager and len(segments_batch) >= 100:
                        try:
                            self.embeddings_manager.generate_and_store_embeddings(segments_batch, batch_size=50)
                            segments_batch = []  # Clear after processing
                        except Exception as e:
                            print(f"Warning: Error generating embeddings for batch: {e}")
            
            # Fetch segments with incremental write callback
            start_time = time.time()
            segments = self.fetch_all_segments(
                max_segments=max_segments,
                incremental=incremental,
                write_callback=write_batch
            )
            fetch_time = time.time() - start_time
            
            # Process any remaining segments for embeddings
            if generate_embeddings and self.embeddings_manager and segments_batch:
                try:
                    self.embeddings_manager.generate_and_store_embeddings(segments_batch, batch_size=50)
                except Exception as e:
                    print(f"Warning: Error generating embeddings for final batch: {e}")
            
            if not segments and not incremental:
                raise Exception("No segments retrieved")
            
            # For non-incremental writes (backward compatibility)
            if total_written == 0 and segments:
                store_start = time.time()
                self.store_segments(segments)
                store_time = time.time() - store_start
                total_written = len(segments)
                
                # Generate embeddings if requested
                if generate_embeddings and self.embeddings_manager:
                    self.generate_embeddings(segments)
            else:
                store_time = 0  # Already measured during incremental writes
            
            # Generate embeddings if requested
            if generate_embeddings and self.embeddings_manager:
                self.generate_embeddings(segments)
            
            # Update status
            self.update_sync_status('success', total_written or len(segments))
            
            # Print summary
            total_time = time.time() - start_time
            print("\n" + "="*60)
            print("Sync Complete!")
            print(f"  Total segments: {total_written or len(segments)}")
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
    parser.add_argument('--incremental', action='store_true', help='Only sync segments updated since last sync')
    parser.add_argument('--limit', type=int, help='Limit number of segments (for testing)')
    parser.add_argument('--no-embeddings', action='store_true', help='Skip embedding generation')
    parser.add_argument('--embeddings-only', action='store_true', help='Only generate embeddings for existing segments')
    parser.add_argument('--embeddings-incremental', action='store_true', help='Generate embeddings only for segments without them')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for embedding generation')
    args = parser.parse_args()
    
    syncer = LiveRampCatalogSync()
    
    try:
        if args.embeddings_incremental:
            # Generate embeddings only for segments that don't have them
            if syncer.embeddings_manager:
                print("Running incremental embedding generation...")
                syncer.embeddings_manager.generate_incremental_embeddings(
                    batch_size=args.batch_size,
                    max_segments=args.limit or 1000
                )
                # Show updated status
                status = syncer.embeddings_manager.check_embeddings_status()
                print(f"\n✓ Incremental update complete")
                print(f"  Total segments: {status['total_segments']:,}")
                print(f"  With embeddings: {status['segments_with_embeddings']:,}")
                print(f"  Without embeddings: {status['segments_without_embeddings']:,}")
                print(f"  Coverage: {status['embeddings_coverage']:.1f}%")
            else:
                print("Embeddings manager not available. Check Gemini configuration.")
        elif args.embeddings_only:
            # Just generate embeddings for existing segments
            print("Generating embeddings for existing segments...")
            conn = sqlite3.connect(syncer.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT raw_data FROM liveramp_segments')
            segments = [json.loads(row[0]) for row in cursor.fetchall()]
            conn.close()
            
            if segments:
                syncer.generate_embeddings(segments, batch_size=args.batch_size)
            else:
                print("No segments found in database")
        else:
            syncer.run_sync(
                force=args.full,
                max_segments=args.limit,
                generate_embeddings=not args.no_embeddings,
                incremental=args.incremental
            )
    except KeyboardInterrupt:
        print("\nSync interrupted by user")
        syncer.update_sync_status('cancelled')
        sys.exit(1)
    except Exception as e:
        print(f"\nSync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()