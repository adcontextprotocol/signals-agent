"""Enhanced LiveRamp Data Marketplace adapter with full catalog sync and intelligent search."""

import requests
import json
import sqlite3
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from .base import PlatformAdapter
import time
import os
import sys

# Import from parent directory
try:
    from embeddings import EmbeddingsManager
except ImportError:
    # Fallback for when module is run directly
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from embeddings import EmbeddingsManager

class LiveRampAdapter(PlatformAdapter):
    """Enhanced adapter with full catalog sync and local caching."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get('base_url', 'https://api.liveramp.com')
        self.token_uri = config.get('token_uri', 'https://serviceaccounts.liveramp.com/authn/v1/oauth2/token')
        self.client_id = config.get('client_id')
        self.secret_key = config.get('secret_key') or config.get('client_secret')
        self.account_id = config.get('account_id')
        self.auth_token = None
        self.token_expires_at = None
        # Use /data/ path for production, local path for development
        import os
        if os.path.exists('/data'):
            self.db_path = config.get('cache_db_path', '/data/signals_agent.db')
        else:
            self.db_path = config.get('cache_db_path', 'signals_agent.db')
        
        if not self.client_id or not self.secret_key:
            raise ValueError("LiveRamp adapter requires client_id and secret_key in config")
        
        self._init_cache_db()
        
        # Initialize embeddings manager if Gemini is configured
        self.embeddings_manager = None
        parent_config = config.get('parent_config', {})
        if parent_config.get('gemini_api_key'):
            try:
                self.embeddings_manager = EmbeddingsManager(parent_config, self.db_path)
                print(f"[LiveRamp] ✓ Embeddings manager initialized")
            except Exception as e:
                print(f"[LiveRamp] Could not initialize embeddings manager: {e}")
    
    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with LiveRamp using OAuth2 client credentials flow."""
        if self._is_token_valid():
            return {
                'access_token': self.auth_token,
                'expires_at': self.token_expires_at
            }
        
        auth_url = self.token_uri
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'password',
            'client_id': self.client_id,
            'username': self.account_id,
            'password': self.secret_key
        }
        
        response = requests.post(auth_url, headers=headers, data=data)
        
        if response.status_code != 200:
            raise Exception(f"LiveRamp authentication failed: {response.status_code} {response.text}")
        
        token_data = response.json()
        self.auth_token = token_data.get('access_token')
        expires_in = token_data.get('expires_in', 3600)
        self.token_expires_at = datetime.now().timestamp() + expires_in
        
        return {
            'access_token': self.auth_token,
            'expires_at': self.token_expires_at
        }
    
    def _is_token_valid(self) -> bool:
        """Check if current auth token is still valid."""
        if not self.auth_token or not self.token_expires_at:
            return False
        return datetime.now().timestamp() < (self.token_expires_at - 300)
    
    def _validate_principal_access(self, principal_id: str, account_id: str) -> bool:
        """Validate that the principal has access to the account."""
        principal_accounts = self.config.get('principal_accounts', {})
        mapped_account = principal_accounts.get(principal_id)
        return mapped_account == account_id or account_id == self.config.get('owner_org')
    
    def _init_cache_db(self):
        """Initialize local SQLite cache for segments."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create segments table with full text search
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS liveramp_segments (
                id INTEGER PRIMARY KEY,
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
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                search_text TEXT
            )
        ''')
        
        # Create FTS5 virtual table for full-text search
        cursor.execute('''
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
        ''')
        
        # Create trigger to keep FTS in sync
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS liveramp_segments_ai 
            AFTER INSERT ON liveramp_segments BEGIN
                INSERT INTO liveramp_segments_fts(
                    rowid, segment_id, name, description, provider_name, categories
                ) VALUES (
                    new.id, new.segment_id, new.name, new.description, 
                    new.provider_name, new.categories
                );
            END;
        ''')
        
        # Sync status table (matching database.py schema)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS liveramp_sync_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_started TIMESTAMP,
                sync_completed TIMESTAMP,
                total_segments INTEGER,
                status TEXT,
                error_message TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def sync_all_segments(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Sync all segments from LiveRamp to local cache."""
        start_time = time.time()
        
        # Check if we need to sync
        if not force_refresh and self._is_cache_fresh():
            return self._get_sync_status()
        
        print("Starting LiveRamp catalog sync...")
        
        # Authenticate
        self.authenticate()
        
        segments_url = f"{self.base_url}/data-marketplace/buyer-api/v3/segments"
        headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Accept': 'application/json',
            'LR-Org-Id': self.config.get('owner_org', '')
        }
        
        # Process in batches to avoid memory exhaustion
        BATCH_SIZE = 5000  # Process 5000 segments at a time for efficiency
        batch_segments = []
        total_processed = 0
        limit = 100  # LiveRamp API maximum per page
        after_cursor = None
        page = 0
        
        # Open database connection once for batch processing
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Begin transaction for entire sync
            cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
            
            # Clear old data once at the start
            cursor.execute("DELETE FROM liveramp_segments")
            cursor.execute("DELETE FROM liveramp_segments_fts")
            
            # Implement cursor-based pagination with batch processing
            while True:
                params = {'limit': limit}
                
                # Add cursor if we have one from previous request
                if after_cursor:
                    params['after'] = after_cursor
                
                try:
                    response = requests.get(segments_url, headers=headers, params=params)
                    
                    if response.status_code == 429:  # Rate limited
                        retry_after = response.headers.get('Retry-After', '5')
                        wait_time = int(retry_after) if retry_after.isdigit() else 5
                        print(f"Rate limited, waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    
                    if response.status_code != 200:
                        print(f"Error fetching page {page}: {response.status_code}")
                        break
                    
                    data = response.json()
                    
                    # Extract segments
                    segments = data.get('v3_Segments', [])
                    if not segments:
                        print(f"No more segments at page {page + 1}")
                        break
                    
                    batch_segments.extend(segments)
                    
                    # Process batch when it reaches BATCH_SIZE
                    if len(batch_segments) >= BATCH_SIZE:
                        self._store_segments_incremental(cursor, batch_segments[:BATCH_SIZE])
                        total_processed += BATCH_SIZE
                        print(f"Processed batch: {total_processed} segments total")
                        batch_segments = batch_segments[BATCH_SIZE:]  # Keep remainder
                    
                    # Check for next cursor in pagination
                    pagination = data.get('_pagination', {})
                    after_cursor = pagination.get('after')
                    
                    print(f"Fetched page {page + 1}: {len(segments)} segments (total fetched: {total_processed + len(batch_segments)})") 
                    
                    # If no cursor, we've reached the end
                    if not after_cursor:
                        print("No more pages available")
                        break
                    
                    page += 1
                    
                    # Remove testing limit for production use
                    # if total_processed >= 10000:  # Removed for full sync
                    #     break
                    
                    # Rate limiting - be nice to the API
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"Error fetching segments page {page}: {e}")
                    # Continue with what we have rather than losing everything
                    break
            
            # Process any remaining segments in the final batch
            if batch_segments:
                self._store_segments_incremental(cursor, batch_segments)
                total_processed += len(batch_segments)
                print(f"Processed final batch: {total_processed} segments total")
            
            # Commit the entire transaction
            conn.commit()
            print(f"Successfully committed {total_processed} segments to database")
            
        except Exception as e:
            conn.rollback()
            print(f"Error during sync, rolling back: {e}")
            raise
        finally:
            conn.close()
        
        # Record sync status
        duration = time.time() - start_time
        self._record_sync_status(total_processed, duration, "success")
        
        print(f"Sync complete: {total_processed} segments in {duration:.1f} seconds")
        
        return {
            'total_segments': total_processed,
            'sync_duration': duration,
            'status': 'success'
        }
    
    def _store_segments_incremental(self, cursor, segments: List[Dict]):
        """Store segments incrementally during sync without reopening connection."""
        # Prepare data for batch insert
        segment_data = []
        for segment in segments:
            segment_id = str(segment.get('id'))
            name = segment.get('name', '')
            description = segment.get('description', '')
            provider = segment.get('providerName', '')
            segment_type = segment.get('segmentType', '')
            
            # Extract reach
            reach_info = segment.get('reach', {})
            reach_count = None
            if isinstance(reach_info, dict):
                input_records = reach_info.get('inputRecords', {})
                if isinstance(input_records, dict):
                    reach_count = input_records.get('count')
            
            # Extract pricing (check multiple locations)
            has_pricing = False
            cpm_price = None
            
            # First check 'pricing' field (LiveRamp structure)
            pricing_obj = segment.get('pricing', {})
            if pricing_obj:
                # Try digitalAdTargeting first
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
                
                # Fallback to other pricing types
                if not has_pricing:
                    for price_type in ['tvTargeting', 'contentMarketing']:
                        if price_type in pricing_obj:
                            pt = pricing_obj[price_type]
                            if 'value' in pt and 'amount' in pt['value']:
                                amount = pt['value']['amount']
                                unit = pt['value'].get('unit', 'CENTS')
                                if unit == 'CENTS':
                                    cpm_price = amount / 100.0
                                else:
                                    cpm_price = float(amount)
                                has_pricing = True
                                break
            
            # Fallback to subscriptions (older structure)
            if not has_pricing:
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
            categories_list = segment.get('categories', [])
            for cat in categories_list:
                if isinstance(cat, dict):
                    cat_name = cat.get('name')
                    if cat_name:
                        categories.append(cat_name)
            categories_str = ', '.join(categories)
            
            # Create search text for better FTS
            search_text = f"{name} {description} {provider} {categories_str}"
            
            segment_data.append((
                segment_id, name, description, provider, segment_type,
                reach_count, has_pricing, cpm_price, categories_str,
                json.dumps(segment), search_text
            ))
        
        # Batch insert (no transaction management here, handled by caller)
        cursor.executemany('''
            INSERT INTO liveramp_segments (
                segment_id, name, description, provider_name, segment_type,
                reach_count, has_pricing, cpm_price, categories,
                raw_data, search_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', segment_data)
    
    def _store_segments_batch(self, segments: List[Dict]):
        """Store segments in database efficiently."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Begin transaction for atomic operations
            cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
            
            # Clear old data within transaction
            cursor.execute("DELETE FROM liveramp_segments")
            # Note: FTS table is auto-updated via triggers
            
            # Prepare data for batch insert
            segment_data = []
            for segment in segments:
                segment_id = str(segment.get('id'))
                name = segment.get('name', '')
                description = segment.get('description', '')
                provider = segment.get('providerName', '')
                segment_type = segment.get('segmentType', '')
                
                # Extract reach
                reach_info = segment.get('reach', {})
                reach_count = None
                if isinstance(reach_info, dict):
                    input_records = reach_info.get('inputRecords', {})
                    if isinstance(input_records, dict):
                        reach_count = input_records.get('count')
                
                # Extract pricing (Enhanced)
                has_pricing = False
                cpm_price = None
                subscriptions = segment.get('subscriptions', [])
                
                # Try multiple methods to find pricing
                if subscriptions:
                    for sub in subscriptions:
                        if isinstance(sub, dict):
                            # Check price object
                            price_info = sub.get('price', {})
                            if isinstance(price_info, dict):
                                # Try multiple price fields
                                for field in ['cpm', 'CPM', 'value', 'Value', 'amount', 'cost']:
                                    if field in price_info and price_info[field] is not None:
                                        try:
                                            cpm_price = float(price_info[field])
                                            has_pricing = True
                                            break
                                        except (ValueError, TypeError):
                                            pass
                            
                            # Check subscription root
                            if not has_pricing:
                                for field in ['cpm', 'CPM', 'price', 'cost']:
                                    if field in sub and sub[field] is not None:
                                        try:
                                            cpm_price = float(sub[field])
                                            has_pricing = True
                                            break
                                        except (ValueError, TypeError):
                                            pass
                        if has_pricing:
                            break
                
                # Check 'pricing' field (LiveRamp structure)
                if not has_pricing:
                    pricing_obj = segment.get('pricing', {})
                    if pricing_obj:
                        # Try digitalAdTargeting first
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
                        
                        # Fallback to other pricing types
                        if not has_pricing:
                            for price_type in ['tvTargeting', 'contentMarketing']:
                                if price_type in pricing_obj:
                                    pt = pricing_obj[price_type]
                                    if 'value' in pt and 'amount' in pt['value']:
                                        amount = pt['value']['amount']
                                        unit = pt['value'].get('unit', 'CENTS')
                                        if unit == 'CENTS':
                                            cpm_price = amount / 100.0
                                        else:
                                            cpm_price = float(amount)
                                        has_pricing = True
                                        break
                
                # Check root level if still no pricing
                if not has_pricing:
                    for field in ['price', 'cpm', 'CPM', 'cost']:
                        if field in segment:
                            val = segment[field]
                            if isinstance(val, (int, float)):
                                cpm_price = float(val)
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
                    reach_count, has_pricing, cpm_price, categories,
                    raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', segment_data)
            
            # Commit transaction
            conn.commit()
            print(f"Successfully stored {len(segments)} segments")
        except Exception as e:
            # Rollback on error
            conn.rollback()
            print(f"Error storing segments: {e}")
            raise
        finally:
            conn.close()
    
    def search_segments_hybrid(self, query: str, limit: int = 20, rag_weight: float = 0.7, use_expansion: bool = True) -> List[Dict[str, Any]]:
        """Hybrid search combining RAG and FTS scores with optional query expansion.
        
        Args:
            query: Search query
            limit: Maximum number of results
            rag_weight: Weight for RAG scores (0-1), FTS gets (1-rag_weight)
            use_expansion: Whether to use AI query expansion for RAG search
            
        Returns:
            List of segment dictionaries with combined scores
        """
        results_map = {}
        
        # Get RAG results if available
        rag_results = []
        if self.embeddings_manager:
            try:
                rag_results = self.embeddings_manager.get_segments_with_embeddings(query, limit * 2, use_expansion)
                for result in rag_results:
                    seg_id = result['segment_id']
                    results_map[seg_id] = result
                    # Normalize similarity score to 0-1 range
                    results_map[seg_id]['rag_score'] = result.get('similarity_score', 0)
            except Exception as e:
                print(f"[LiveRamp] RAG search error: {e}")
        
        # Get FTS results
        fts_results = self.search_segments(query, limit * 2)
        
        # Normalize FTS scores and combine
        max_relevance = max([abs(r.get('relevance_score', 0)) for r in fts_results], default=1)
        
        for result in fts_results:
            seg_id = result['segment_id']
            
            # Normalize FTS score to 0-1 range
            fts_score = abs(result.get('relevance_score', 0)) / max(abs(max_relevance), 1)
            
            if seg_id in results_map:
                # Combine scores
                results_map[seg_id]['fts_score'] = fts_score
                results_map[seg_id]['combined_score'] = (
                    rag_weight * results_map[seg_id]['rag_score'] +
                    (1 - rag_weight) * fts_score
                )
            else:
                # FTS-only result
                result['fts_score'] = fts_score
                result['rag_score'] = 0
                result['combined_score'] = (1 - rag_weight) * fts_score
                results_map[seg_id] = result
        
        # Sort by combined score
        results = list(results_map.values())
        results.sort(key=lambda x: x.get('combined_score', 0), reverse=True)
        
        return results[:limit]
    
    def search_segments_rag(self, query: str, limit: int = 10, use_expansion: bool = True) -> List[Dict[str, Any]]:
        """Search segments using RAG (vector similarity) search with optional query expansion.
        
        Args:
            query: Search query
            limit: Maximum number of results
            use_expansion: Whether to use AI query expansion
            
        Returns:
            List of segment dictionaries with similarity scores
        """
        if not self.embeddings_manager:
            # Fall back to FTS if embeddings are not available
            return self.search_segments(query, limit)
        
        try:
            # Use embeddings manager for vector similarity search with expansion
            results = self.embeddings_manager.get_segments_with_embeddings(query, limit, use_expansion)
            
            # Add proper score fields for UI display
            for result in results:
                # RAG score is the similarity score (already in 0-1 range)
                result['rag_score'] = result.get('similarity_score', 0)
                result['fts_score'] = 0  # No FTS score in pure RAG search
                result['combined_score'] = result['rag_score']  # In pure RAG, combined = RAG score
                result['relevance_score'] = 0  # No FTS relevance in pure RAG
                
            return results
        except Exception as e:
            print(f"[LiveRamp] RAG search failed, falling back to FTS: {e}")
            return self.search_segments(query, limit)
    
    def search_segments(self, query: str, limit: int = 200) -> List[Dict[str, Any]]:
        """Search segments using full-text search."""
        import re
        results = []
        
        # Properly sanitize query to prevent SQL injection
        # Only allow alphanumeric, spaces, and basic punctuation
        sanitized_query = re.sub(r'[^\w\s\-]', ' ', query)
        words = sanitized_query.lower().split()
        
        if not words:
            return []  # Empty query returns no results
        
        # Build FTS5 query - use OR for multi-word search
        # Each word is individually quoted for FTS5
        fts_terms = []
        for word in words:
            if word.strip():  # Skip empty strings
                # Quote each word for FTS5
                fts_terms.append(f'"{word}"')
        
        if not fts_terms:
            return []
        
        # Create OR query for FTS5
        fts_query = ' OR '.join(fts_terms)
        
        # Use context manager to ensure connection is properly closed
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Use FTS5 for intelligent search
            try:
                cursor.execute('''
                    SELECT s.*, 
                           rank * -1 as relevance_score
                    FROM liveramp_segments s
                    JOIN liveramp_segments_fts fts ON s.id = fts.rowid
                    WHERE liveramp_segments_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                ''', (fts_query, limit))
                
                for row in cursor.fetchall():
                    segment_data = json.loads(row['raw_data'])
                    
                    # Calculate coverage percentage
                    coverage = None
                    if row['reach_count']:
                        coverage = (row['reach_count'] / 250_000_000) * 100
                        coverage = round(min(coverage, 50.0), 1)
                    
                    results.append({
                        'segment_id': row['segment_id'],
                        'name': row['name'],
                        'description': row['description'],
                        'provider': row['provider_name'],
                        'coverage_percentage': coverage,
                        'cpm': row['cpm_price'],
                        'has_pricing': row['has_pricing'],
                        'categories': row['categories'].split(', ') if row['categories'] else [],
                        'relevance_score': row['relevance_score'],
                        'raw_data': segment_data,
                        # Add normalized scores for UI display
                        'fts_score': 1.0,  # FTS results have maximum FTS score
                        'rag_score': 0,  # No RAG score in pure FTS search
                        'combined_score': 1.0,  # In pure FTS, combined = FTS score
                        'similarity_score': 0  # No similarity in pure FTS
                    })
            except sqlite3.OperationalError as e:
                print(f"[LiveRamp] Search error: {e}")
                return []
        
        return results
    
    def get_segment_by_id(self, segment_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific segment by ID from cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM liveramp_segments WHERE segment_id = ?', (segment_id,))
            row = cursor.fetchone()
            
            if row:
                return json.loads(row['raw_data'])
        
        return None
    
    def get_segments_by_category(self, category: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get segments by category."""
        results = []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM liveramp_segments 
                WHERE categories LIKE ?
                LIMIT ?
            ''', (f'%{category}%', limit))
            
            for row in cursor.fetchall():
                results.append(json.loads(row['raw_data']))
        
        return results
    
    def get_segments(self, account_id: str, principal_id: Optional[str] = None, 
                     search_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Override parent method to use local cache with optional search."""
        
        # ALWAYS use local cache - no automatic sync
        # Sync should only be done by the scheduled sync job
        
        # Check if database has any segments
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if we have any segments
            cursor.execute('SELECT COUNT(*) as count FROM liveramp_segments')
            count = cursor.fetchone()['count']
            
            if count == 0:
                print(f"[LiveRamp] Warning: No segments in cache. Database needs to be synced.")
                # Return empty list instead of failing
                return []
        
        if search_query:
            # Use hybrid search for best results (combines RAG and FTS)
            segments = self.search_segments_hybrid(search_query, limit=100)
        else:
            # Limit results to prevent overwhelming the system
            # When no search query, return a reasonable sample
            MAX_SEGMENTS = 100
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('SELECT raw_data FROM liveramp_segments LIMIT ?', (MAX_SEGMENTS,))
                segments = [json.loads(row['raw_data']) for row in cursor.fetchall()]
        
        # Normalize to internal format
        return self._normalize_segments(segments, account_id)
    
    def _is_cache_fresh(self, max_age_hours: int = 24) -> bool:
        """Check if cache is fresh enough."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sync_completed FROM liveramp_sync_status 
            WHERE status = 'success'
            ORDER BY id DESC LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return False
        
        last_sync = datetime.fromisoformat(row[0])
        age = datetime.now() - last_sync
        
        return age.total_seconds() < (max_age_hours * 3600)
    
    def _record_sync_status(self, total_segments: int, duration: float, status: str):
        """Record sync status in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        sync_completed = datetime.now()
        sync_started = sync_completed - timedelta(seconds=duration)
        
        cursor.execute('''
            INSERT INTO liveramp_sync_status (sync_started, sync_completed, total_segments, status, error_message)
            VALUES (?, ?, ?, ?, ?)
        ''', (sync_started.isoformat(), sync_completed.isoformat(), total_segments, status, None))
        
        conn.commit()
        conn.close()
    
    def _get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM liveramp_sync_status 
            ORDER BY id DESC LIMIT 1
        ''')
        
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
        else:
            result = {'status': 'never_synced'}
        
        # Add segment count
        cursor.execute('SELECT COUNT(*) as count FROM liveramp_segments')
        result['current_segments'] = cursor.fetchone()['count']
        
        conn.close()
        return result
    
    def _normalize_segments(self, raw_segments: List[Dict], account_id: str) -> List[Dict[str, Any]]:
        """Normalize LiveRamp segments to our internal format."""
        normalized = []
        
        for segment in raw_segments:
            if isinstance(segment, dict) and 'raw_data' in segment:
                segment = segment['raw_data']
            
            segment_id = segment.get('id')
            segment_name = segment.get('name', f'LiveRamp Segment {segment_id}')
            description = segment.get('description', '')
            
            seller_name = segment.get('providerName', 'Unknown Provider')
            
            subscriptions = segment.get('subscriptions', [])
            cpm = None
            is_free = False
            
            for sub in subscriptions:
                if isinstance(sub, dict):
                    price_info = sub.get('price', {})
                    if isinstance(price_info, dict):
                        cpm = price_info.get('cpm') or price_info.get('value')
                        break
            
            if cpm == 0 or cpm is None:
                is_free = True
                cpm = 0.0
            
            reach_info = segment.get('reach', {})
            reach_value = None
            
            if isinstance(reach_info, dict):
                input_records = reach_info.get('inputRecords', {})
                if isinstance(input_records, dict):
                    reach_value = input_records.get('count')
            
            coverage = None
            if reach_value:
                coverage = (reach_value / 250_000_000) * 100
                coverage = round(min(coverage, 50.0), 1)
            
            segment_type = segment.get('segmentType', 'UNKNOWN')
            categories = segment.get('categories', [])
            if isinstance(categories, list):
                category_names = [cat.get('name', '') if isinstance(cat, dict) else str(cat) for cat in categories]
            else:
                category_names = []
            
            normalized_segment = {
                'id': f"liveramp_{account_id}_{segment_id}",
                'platform_segment_id': str(segment_id),
                'name': segment_name,
                'description': description or f"LiveRamp segment from {seller_name}",
                'audience_type': 'marketplace',
                'data_provider': f"LiveRamp ({seller_name})",
                'coverage_percentage': coverage,
                'base_cpm': cpm if cpm is not None else 0.0,
                'revenue_share_percentage': 0.0,
                'is_free': is_free,
                'has_coverage_data': coverage is not None,
                'has_pricing_data': cpm is not None,
                'catalog_access': 'personalized',
                'platform': 'liveramp',
                'account_id': account_id,
                'categories': category_names,
                'raw_data': segment
            }
            normalized.append(normalized_segment)
        
        return normalized
    
    def activate_segment(self, segment_id: str, account_id: str, activation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Activate a segment on LiveRamp Data Marketplace."""
        self.authenticate()
        
        activation_url = f"{self.base_url}/data-marketplace/buyer-api/v3/requested-segments"
        
        headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'LR-Org-Id': self.config.get('owner_org', '')
        }
        
        activation_data = {
            'segmentId': segment_id,
            'name': activation_config.get('name', f'Activation_{segment_id}'),
            'description': activation_config.get('description', 'Activated via Audience Agent'),
            'destinations': activation_config.get('destinations', [])
        }
        
        response = requests.post(activation_url, headers=headers, json=activation_data)
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to activate segment: {response.status_code} {response.text}")
        
        activation_response = response.json()
        
        return {
            'platform_activation_id': activation_response.get('id'),
            'status': 'activating',
            'estimated_duration_minutes': 30,
            'activation_started_at': datetime.now().isoformat(),
            'raw_response': activation_response
        }
    
    def check_segment_status(self, segment_id: str, account_id: str) -> Dict[str, Any]:
        """Check the status of a segment activation on LiveRamp."""
        self.authenticate()
        
        status_url = f"{self.base_url}/data-marketplace/buyer-api/v3/requested-segments/{segment_id}"
        
        headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Accept': 'application/json',
            'LR-Org-Id': self.config.get('owner_org', '')
        }
        
        response = requests.get(status_url, headers=headers)
        
        if response.status_code == 404:
            return {
                'status': 'not_found',
                'is_live': False,
                'error_message': 'Segment activation not found'
            }
        elif response.status_code != 200:
            raise Exception(f"Failed to check segment status: {response.status_code} {response.text}")
        
        status_data = response.json()
        
        liveramp_status = status_data.get('status', '').upper()
        
        if liveramp_status == 'ACTIVE':
            return {
                'status': 'deployed',
                'is_live': True,
                'deployed_at': status_data.get('activatedAt', datetime.now().isoformat()),
                'platform_segment_id': segment_id
            }
        elif liveramp_status in ['PENDING', 'PROCESSING']:
            return {
                'status': 'activating',
                'is_live': False,
                'platform_segment_id': segment_id
            }
        elif liveramp_status in ['FAILED', 'ERROR']:
            return {
                'status': 'failed',
                'is_live': False,
                'error_message': status_data.get('errorMessage', 'Activation failed'),
                'platform_segment_id': segment_id
            }
        else:
            return {
                'status': 'unknown',
                'is_live': False,
                'platform_segment_id': segment_id,
                'raw_status': liveramp_status
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about cached segments."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        stats = {}
        
        # Total segments
        cursor.execute('SELECT COUNT(*) as count FROM liveramp_segments')
        stats['total_segments'] = cursor.fetchone()['count']
        
        # Segments with pricing
        cursor.execute('SELECT COUNT(*) as count FROM liveramp_segments WHERE has_pricing = 1')
        stats['segments_with_pricing'] = cursor.fetchone()['count']
        
        # Segments with reach data
        cursor.execute('SELECT COUNT(*) as count FROM liveramp_segments WHERE reach_count IS NOT NULL')
        stats['segments_with_reach'] = cursor.fetchone()['count']
        
        # Top providers
        cursor.execute('''
            SELECT provider_name, COUNT(*) as count 
            FROM liveramp_segments 
            GROUP BY provider_name 
            ORDER BY count DESC 
            LIMIT 10
        ''')
        stats['top_providers'] = [dict(row) for row in cursor.fetchall()]
        
        # Sync status
        stats['sync_status'] = self._get_sync_status()
        
        conn.close()
        return stats