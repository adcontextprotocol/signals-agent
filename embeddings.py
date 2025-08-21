"""Vector embeddings management for RAG implementation using Gemini and sqlite-vec."""

import sqlite3
import json
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import google.generativeai as genai
from datetime import datetime, timedelta
import sqlite_vec
import hashlib
import time
from functools import lru_cache


class EmbeddingsManager:
    """Manages vector embeddings for LiveRamp segments using Gemini and sqlite-vec."""
    
    def __init__(self, config: Dict[str, Any], db_path: str):
        """Initialize the embeddings manager.
        
        Args:
            config: Configuration dictionary containing Gemini API key
            db_path: Path to the SQLite database
        """
        self.config = config
        self.db_path = db_path
        
        # Initialize Gemini
        api_key = config.get('gemini_api_key')
        if not api_key:
            raise ValueError("Gemini API key is required for embeddings")
        
        genai.configure(api_key=api_key)
        # Use the embedding model directly, not GenerativeModel
        self.embedding_dimension = 768  # text-embedding-004 produces 768-dim vectors
        
        # Initialize generative model for query expansion
        self.generative_model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Cache for search results
        self._search_cache = {}
        self._cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes
        self._cache_size = 100  # Max number of cached queries
        
        # Initialize database with vector support
        self._init_vector_db()
    
    def _init_vector_db(self):
        """Initialize the vector database schema."""
        conn = sqlite3.connect(self.db_path)
        
        # Load sqlite-vec extension
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        
        cursor = conn.cursor()
        
        # Create embeddings table
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS liveramp_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                segment_id TEXT UNIQUE NOT NULL,
                embedding_text TEXT NOT NULL,
                embedding_hash TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (segment_id) REFERENCES liveramp_segments(segment_id)
            )
        ''')
        
        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_liveramp_embeddings_segment_id 
            ON liveramp_embeddings(segment_id)
        ''')
        
        # Create virtual table for vector similarity search
        cursor.execute(f'''
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_liveramp_embeddings
            USING vec0(
                segment_id TEXT PRIMARY KEY,
                embedding float[{self.embedding_dimension}]
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for a text using Gemini.
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            Numpy array containing the embedding vector
        """
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="RETRIEVAL_DOCUMENT"
        )
        return np.array(result['embedding'], dtype=np.float32)
    
    def expand_query(self, query: str) -> List[str]:
        """Expand a query into related terms using AI.
        
        Args:
            query: Original search query
            
        Returns:
            List of related search terms including the original
        """
        try:
            prompt = f"""Given the search query "{query}" for finding audience segments in a data marketplace, 
            generate 5 related search terms that would help find relevant audience segments.
            
            Focus on:
            - Industry terms and categories
            - Demographics and behaviors
            - Purchase intent signals
            - Professional attributes
            - Interest categories
            
            Return ONLY a comma-separated list of terms, no explanations or numbering.
            Example: luxury cars, premium vehicles, high-end automotive, luxury brand enthusiasts, affluent car buyers
            """
            
            response = self.generative_model.generate_content(prompt)
            expanded_terms = [term.strip() for term in response.text.split(',')]
            
            # Add the original query if not already in the list
            if query.lower() not in [term.lower() for term in expanded_terms]:
                expanded_terms.insert(0, query)
            
            # Limit to 6 terms total
            return expanded_terms[:6]
            
        except Exception as e:
            print(f"Query expansion failed: {e}")
            # Fall back to just the original query
            return [query]
    
    @lru_cache(maxsize=128)
    def generate_query_embedding(self, query: str) -> np.ndarray:
        """Generate embedding for a search query using Gemini with caching.
        
        Args:
            query: Search query text
            
        Returns:
            Numpy array containing the embedding vector
        """
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=query,
            task_type="RETRIEVAL_QUERY"
        )
        return np.array(result['embedding'], dtype=np.float32)
    
    def create_segment_text(self, segment: Dict[str, Any]) -> str:
        """Create text representation of a segment for embedding.
        
        Args:
            segment: Segment data dictionary
            
        Returns:
            Text representation for embedding
        """
        # Extract key information
        name = segment.get('name', '')
        description = segment.get('description', '')
        provider = segment.get('providerName', '')
        segment_type = segment.get('segmentType', '')
        
        # Extract categories
        categories = []
        for cat in segment.get('categories', []):
            if isinstance(cat, dict):
                categories.append(cat.get('name', ''))
            else:
                categories.append(str(cat))
        categories_str = ', '.join(categories)
        
        # Combine into a rich text representation
        text_parts = []
        if name:
            text_parts.append(f"Name: {name}")
        if description:
            text_parts.append(f"Description: {description}")
        if provider:
            text_parts.append(f"Provider: {provider}")
        if segment_type:
            text_parts.append(f"Type: {segment_type}")
        if categories_str:
            text_parts.append(f"Categories: {categories_str}")
        
        return ' | '.join(text_parts)
    
    def store_embedding(self, segment_id: str, text: str, embedding: np.ndarray):
        """Store an embedding in the database.
        
        Args:
            segment_id: ID of the segment
            text: Text that was embedded
            embedding: Embedding vector
        """
        conn = sqlite3.connect(self.db_path)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        
        cursor = conn.cursor()
        
        # Create hash of text for deduplication
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        
        # Convert embedding to bytes for storage
        embedding_bytes = embedding.tobytes()
        
        try:
            # Begin transaction for atomic operation
            cursor.execute("BEGIN TRANSACTION")
            
            # First, delete any existing records for this segment_id
            cursor.execute('DELETE FROM liveramp_embeddings WHERE segment_id = ?', (segment_id,))
            cursor.execute('DELETE FROM vec_liveramp_embeddings WHERE segment_id = ?', (segment_id,))
            
            # Now insert the new records
            cursor.execute('''
                INSERT INTO liveramp_embeddings 
                (segment_id, embedding_text, embedding_hash, embedding)
                VALUES (?, ?, ?, ?)
            ''', (segment_id, text, text_hash, embedding_bytes))
            
            # Store in vector table for similarity search
            cursor.execute('''
                INSERT INTO vec_liveramp_embeddings 
                (segment_id, embedding)
                VALUES (?, ?)
            ''', (segment_id, embedding_bytes))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to store embedding for segment {segment_id}: {str(e)}")
        finally:
            conn.close()
    
    def generate_and_store_embeddings(self, segments: List[Dict[str, Any]], batch_size: int = 100):
        """Generate and store embeddings for multiple segments.
        
        Args:
            segments: List of segment dictionaries
            batch_size: Number of segments to process in each batch
        """
        print(f"Generating embeddings for {len(segments)} segments...")
        
        for i in range(0, len(segments), batch_size):
            batch = segments[i:i + batch_size]
            print(f"Processing batch {i // batch_size + 1} ({i + 1}-{min(i + batch_size, len(segments))} of {len(segments)})")
            
            for segment in batch:
                try:
                    # Try different possible ID fields
                    segment_id = segment.get('segment_id') or segment.get('id') or segment.get('segmentId')
                    if not segment_id:
                        print(f"Warning: No segment ID found in segment: {segment}")
                        continue
                    segment_id = str(segment_id)
                    
                    # Create text representation
                    text = self.create_segment_text(segment)
                    
                    # Generate embedding
                    embedding = self.generate_embedding(text)
                    
                    # Store embedding
                    self.store_embedding(segment_id, text, embedding)
                    
                except Exception as e:
                    print(f"Error processing segment {segment.get('id')}: {e}")
                    continue
    
    def _get_cache_key(self, query: str, limit: int) -> str:
        """Generate a cache key for a query."""
        return hashlib.md5(f"{query}_{limit}".encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Check if a cache entry is still valid."""
        if not cache_entry:
            return False
        timestamp = cache_entry.get('timestamp')
        if not timestamp:
            return False
        return datetime.now() - timestamp < self._cache_ttl
    
    def _clean_cache(self):
        """Remove expired entries from cache."""
        if len(self._search_cache) > self._cache_size:
            # Remove oldest entries
            sorted_items = sorted(self._search_cache.items(), 
                                key=lambda x: x[1].get('timestamp', datetime.min))
            # Keep only the most recent entries
            self._search_cache = dict(sorted_items[-self._cache_size:])
    
    def search_similar_segments_enhanced(self, query: str, limit: int = 10, use_expansion: bool = True) -> List[Tuple[str, float]]:
        """Enhanced search using query expansion and multiple embeddings.
        
        Args:
            query: Search query
            limit: Maximum number of results
            use_expansion: Whether to use query expansion
            
        Returns:
            List of (segment_id, distance) tuples
        """
        if not use_expansion:
            return self.search_similar_segments(query, limit)
        
        # Expand the query
        expanded_queries = self.expand_query(query)
        print(f"Expanded query '{query}' to: {expanded_queries}")
        
        # Collect results from all expanded queries
        all_results = {}
        for expanded_query in expanded_queries:
            results = self.search_similar_segments(expanded_query, limit * 2)
            for segment_id, distance in results:
                if segment_id not in all_results or distance < all_results[segment_id]:
                    all_results[segment_id] = distance
        
        # Sort by distance and return top results
        sorted_results = sorted(all_results.items(), key=lambda x: x[1])
        return sorted_results[:limit]
    
    def search_similar_segments(self, query: str, limit: int = 10) -> List[Tuple[str, float]]:
        """Search for segments similar to the query using vector similarity with caching.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of (segment_id, distance) tuples
        """
        # Check cache first
        cache_key = self._get_cache_key(query, limit)
        cache_entry = self._search_cache.get(cache_key)
        
        if cache_entry and self._is_cache_valid(cache_entry):
            return cache_entry['results']
        
        # Generate query embedding
        query_embedding = self.generate_query_embedding(query)
        
        conn = sqlite3.connect(self.db_path)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        
        cursor = conn.cursor()
        
        # Perform vector similarity search
        # sqlite-vec uses L2 distance by default, lower is better
        cursor.execute('''
            SELECT segment_id, distance
            FROM vec_liveramp_embeddings
            WHERE embedding MATCH ?
                AND k = ?
            ORDER BY distance
        ''', (query_embedding.tobytes(), limit))
        
        results = cursor.fetchall()
        conn.close()
        
        # Cache the results
        self._search_cache[cache_key] = {
            'results': results,
            'timestamp': datetime.now()
        }
        
        # Clean cache if needed
        self._clean_cache()
        
        return results
    
    def get_segments_with_embeddings(self, query: str, limit: int = 10, use_expansion: bool = True) -> List[Dict[str, Any]]:
        """Get full segment data for segments similar to the query.
        
        Args:
            query: Search query
            limit: Maximum number of results
            use_expansion: Whether to use query expansion
            
        Returns:
            List of segment dictionaries with similarity scores
        """
        # Get similar segment IDs using enhanced search
        similar_segments = self.search_similar_segments_enhanced(query, limit, use_expansion)
        
        if not similar_segments:
            return []
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        results = []
        
        # Get min and max distances for normalization
        if similar_segments:
            distances = [d for _, d in similar_segments]
            min_distance = min(distances)
            max_distance = max(distances)
            distance_range = max_distance - min_distance
            
            # If all distances are the same, use a small range to avoid division by zero
            if distance_range < 0.001:
                distance_range = 1.0
        
        for i, (segment_id, distance) in enumerate(similar_segments):
            cursor.execute('''
                SELECT * FROM liveramp_segments 
                WHERE segment_id = ?
            ''', (segment_id,))
            
            row = cursor.fetchone()
            if row:
                segment_data = json.loads(row['raw_data'])
                
                # Calculate similarity score using multiple methods for better distribution
                # 1. Min-max normalization (inverted so lower distance = higher score)
                normalized_score = 1.0 - ((distance - min_distance) / distance_range) if distance_range > 0 else 1.0
                
                # 2. Rank-based score (top result gets 1.0, decreases linearly)
                rank_score = 1.0 - (i / len(similar_segments))
                
                # 3. Exponential decay with better scaling
                # Use smaller divisor for more spread in scores
                exp_score = np.exp(-distance / 50)  # Changed from 100 to 50 for more variation
                
                # Combine the scores with weights
                # Prioritize normalized score but include rank for tie-breaking
                similarity_score = (0.7 * normalized_score + 0.2 * exp_score + 0.1 * rank_score)
                
                # Calculate coverage percentage
                coverage = None
                if row['reach_count']:
                    coverage = (row['reach_count'] / 250_000_000) * 100
                    coverage = round(min(coverage, 50.0), 1)
                
                results.append({
                    'id': row['segment_id'],  # Use 'id' as primary field for compatibility
                    'name': row['name'],
                    'description': row['description'],
                    'data_provider': f"LiveRamp ({row['provider_name']})",  # Changed to data_provider with LiveRamp prefix
                    'coverage_percentage': coverage,
                    'base_cpm': row['cpm_price'],  # Changed from 'cpm' to 'base_cpm'
                    'revenue_share_percentage': 0.0,  # Add missing field
                    'has_pricing': row['has_pricing'],
                    'categories': row['categories'].split(', ') if row['categories'] else [],
                    'similarity_score': float(similarity_score),
                    'vector_distance': float(distance),
                    'raw_data': segment_data
                })
        
        conn.close()
        
        # Sort by similarity score (higher is better)
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return results
    
    def get_segments_without_embeddings(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get segments that don't have embeddings yet.
        
        Args:
            limit: Maximum number of segments to return
            
        Returns:
            List of segment dictionaries without embeddings
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.raw_data
            FROM liveramp_segments s
            LEFT JOIN liveramp_embeddings e ON s.segment_id = e.segment_id
            WHERE e.segment_id IS NULL
            LIMIT ?
        ''', (limit,))
        
        segments = []
        for row in cursor.fetchall():
            segments.append(json.loads(row['raw_data']))
        
        conn.close()
        return segments
    
    def generate_incremental_embeddings(self, batch_size: int = 100, max_segments: int = 1000):
        """Generate embeddings only for segments that don't have them.
        
        Args:
            batch_size: Number of segments to process in each batch
            max_segments: Maximum number of segments to process
        """
        # Get segments without embeddings
        segments = self.get_segments_without_embeddings(max_segments)
        
        if not segments:
            print("All segments already have embeddings")
            return
        
        print(f"Found {len(segments)} segments without embeddings")
        self.generate_and_store_embeddings(segments, batch_size)
    
    def check_embeddings_status(self) -> Dict[str, Any]:
        """Check the status of embeddings in the database.
        
        Returns:
            Dictionary with statistics about embeddings
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total segments
        cursor.execute('SELECT COUNT(*) FROM liveramp_segments')
        stats['total_segments'] = cursor.fetchone()[0]
        
        # Segments with embeddings
        cursor.execute('SELECT COUNT(*) FROM liveramp_embeddings')
        stats['segments_with_embeddings'] = cursor.fetchone()[0]
        
        # Segments without embeddings
        stats['segments_without_embeddings'] = stats['total_segments'] - stats['segments_with_embeddings']
        
        # Embeddings coverage
        if stats['total_segments'] > 0:
            stats['embeddings_coverage'] = (stats['segments_with_embeddings'] / stats['total_segments']) * 100
        else:
            stats['embeddings_coverage'] = 0
        
        # Last embedding created
        cursor.execute('SELECT MAX(created_at) FROM liveramp_embeddings')
        last_created = cursor.fetchone()[0]
        stats['last_embedding_created'] = last_created
        
        conn.close()
        
        return stats