"""Database search service that implements RAG/FTS/hybrid search for signal_segments table."""

import sqlite3
import os
from typing import List, Dict, Any, Optional
from embeddings import EmbeddingsManager


class DatabaseSearchService:
    """Handles different search modes for the signal_segments database."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_path = os.environ.get('DATABASE_PATH', 'signals_agent.db')
        
        # Initialize embeddings manager if Gemini is available
        self.embeddings_manager = None
        if config.get('gemini_api_key'):
            try:
                self.embeddings_manager = EmbeddingsManager(config, self.db_path)
            except Exception as e:
                print(f"[DatabaseSearchService] Could not initialize embeddings: {e}")
    
    def ensure_fts_table(self):
        """Ensure FTS5 table exists for signal_segments."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create FTS5 virtual table for signal_segments
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS signal_segments_fts 
            USING fts5(
                id UNINDEXED,
                name, 
                description,
                data_provider,
                signal_type,
                content='signal_segments',
                content_rowid='rowid'
            )
        """)
        
        # Create trigger to keep FTS in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS signal_segments_fts_insert 
            AFTER INSERT ON signal_segments BEGIN
                INSERT INTO signal_segments_fts(rowid, id, name, description, data_provider, signal_type)
                VALUES (NEW.rowid, NEW.id, NEW.name, NEW.description, NEW.data_provider, NEW.signal_type);
            END
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS signal_segments_fts_update 
            AFTER UPDATE ON signal_segments BEGIN
                UPDATE signal_segments_fts 
                SET name=NEW.name, description=NEW.description, data_provider=NEW.data_provider, signal_type=NEW.signal_type
                WHERE rowid=NEW.rowid;
            END
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS signal_segments_fts_delete 
            AFTER DELETE ON signal_segments BEGIN
                DELETE FROM signal_segments_fts WHERE rowid=OLD.rowid;
            END
        """)
        
        # Populate FTS table if empty
        cursor.execute("SELECT COUNT(*) FROM signal_segments_fts")
        fts_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM signal_segments")
        segments_count = cursor.fetchone()[0]
        
        if fts_count < segments_count:
            print(f"[DatabaseSearchService] Populating FTS table ({segments_count} segments)")
            cursor.execute("""
                INSERT INTO signal_segments_fts(rowid, id, name, description, data_provider, signal_type)
                SELECT rowid, id, name, description, data_provider, signal_type FROM signal_segments
            """)
        
        conn.commit()
        conn.close()
    
    def search_fts(self, query: str, filters: Optional[Dict[str, Any]] = None, 
                   principal_access_level: str = 'public', limit: int = 20) -> List[Dict[str, Any]]:
        """Search using FTS5 full-text search."""
        self.ensure_fts_table()
        
        # Sanitize query for FTS5
        import re
        sanitized_query = re.sub(r'[^\w\s\-]', ' ', query)
        words = sanitized_query.lower().split()
        
        if not words:
            return []
        
        # Limit words to prevent complexity issues
        if len(words) > 20:
            words = words[:20]
        
        # Build FTS5 query
        fts_terms = [f'"{word}"' for word in words if word.strip()]
        if not fts_terms:
            return []
        
        fts_query = ' OR '.join(fts_terms)
        
        # Build catalog access filter
        if principal_access_level == 'public':
            catalog_filter = "s.catalog_access = 'public'"
        elif principal_access_level == 'personalized':
            catalog_filter = "s.catalog_access IN ('public', 'personalized')"
        else:  # private
            catalog_filter = "s.catalog_access IN ('public', 'personalized', 'private')"
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Base query with FTS5
        base_query = f"""
            SELECT s.*, rank * -1 as relevance_score
            FROM signal_segments s
            JOIN signal_segments_fts fts ON s.rowid = fts.rowid
            WHERE signal_segments_fts MATCH ? AND {catalog_filter}
        """
        params = [fts_query]
        
        # Add additional filters
        if filters:
            if filters.get('catalog_types'):
                placeholders = ','.join('?' * len(filters['catalog_types']))
                base_query += f" AND s.signal_type IN ({placeholders})"
                params.extend(filters['catalog_types'])
            
            if filters.get('data_providers'):
                placeholders = ','.join('?' * len(filters['data_providers']))
                base_query += f" AND s.data_provider IN ({placeholders})"
                params.extend(filters['data_providers'])
            
            if filters.get('max_cpm'):
                base_query += " AND s.base_cpm <= ?"
                params.append(filters['max_cpm'])
            
            if filters.get('min_coverage_percentage'):
                base_query += " AND s.coverage_percentage >= ?"
                params.append(filters['min_coverage_percentage'])
        
        base_query += " ORDER BY rank LIMIT ?"
        params.append(limit)
        
        try:
            cursor.execute(base_query, params)
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except Exception as e:
            print(f"[DatabaseSearchService] FTS search failed: {e}")
            conn.close()
            return []
    
    def search_rag(self, query: str, filters: Optional[Dict[str, Any]] = None,
                   principal_access_level: str = 'public', limit: int = 20, 
                   use_expansion: bool = True) -> List[Dict[str, Any]]:
        """Search using RAG vector similarity."""
        if not self.embeddings_manager:
            print("[DatabaseSearchService] RAG search requested but embeddings not available, falling back to FTS")
            return self.search_fts(query, filters, principal_access_level, limit)
        
        # TODO: Implement vector embeddings for signal_segments table
        # The EmbeddingsManager currently only supports LiveRamp segments
        # For now, fall back to FTS search which provides good semantic matching
        print("[DatabaseSearchService] RAG search for signal_segments not yet implemented (would need embeddings generation), using FTS")
        return self.search_fts(query, filters, principal_access_level, limit)
    
    def search_hybrid(self, query: str, filters: Optional[Dict[str, Any]] = None,
                      principal_access_level: str = 'public', limit: int = 20,
                      use_expansion: bool = True) -> List[Dict[str, Any]]:
        """Search using hybrid FTS + RAG approach."""
        if not self.embeddings_manager:
            print("[DatabaseSearchService] Hybrid search requested but embeddings not available, using FTS only")
            return self.search_fts(query, filters, principal_access_level, limit)
        
        # TODO: Implement hybrid search combining FTS + vector similarity for signal_segments
        # This would require generating embeddings for signal_segments and combining with FTS scores
        # For now, FTS search provides good results and avoids expression tree depth issues
        print("[DatabaseSearchService] Hybrid search for signal_segments not yet implemented (would combine FTS + embeddings), using FTS")
        return self.search_fts(query, filters, principal_access_level, limit)
    
    def search_basic(self, query: str, filters: Optional[Dict[str, Any]] = None,
                     principal_access_level: str = 'public', limit: int = 20) -> List[Dict[str, Any]]:
        """Basic search without any text matching - just filters."""
        # Build catalog access filter
        if principal_access_level == 'public':
            catalog_filter = "catalog_access = 'public'"
        elif principal_access_level == 'personalized':
            catalog_filter = "catalog_access IN ('public', 'personalized')"
        else:  # private
            catalog_filter = "catalog_access IN ('public', 'personalized', 'private')"
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        base_query = f"SELECT * FROM signal_segments WHERE {catalog_filter}"
        params = []
        
        # Add additional filters
        if filters:
            if filters.get('catalog_types'):
                placeholders = ','.join('?' * len(filters['catalog_types']))
                base_query += f" AND signal_type IN ({placeholders})"
                params.extend(filters['catalog_types'])
            
            if filters.get('data_providers'):
                placeholders = ','.join('?' * len(filters['data_providers']))
                base_query += f" AND data_provider IN ({placeholders})"
                params.extend(filters['data_providers'])
            
            if filters.get('max_cpm'):
                base_query += " AND base_cpm <= ?"
                params.append(filters['max_cpm'])
            
            if filters.get('min_coverage_percentage'):
                base_query += " AND coverage_percentage >= ?"
                params.append(filters['min_coverage_percentage'])
        
        base_query += " ORDER BY coverage_percentage DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(base_query, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def search(self, query: str, search_mode: str = 'hybrid', 
               filters: Optional[Dict[str, Any]] = None,
               principal_access_level: str = 'public', limit: int = 20,
               use_expansion: bool = True) -> List[Dict[str, Any]]:
        """Main search method that routes to appropriate search strategy."""
        
        if search_mode == 'rag':
            return self.search_rag(query, filters, principal_access_level, limit, use_expansion)
        elif search_mode == 'fts':
            return self.search_fts(query, filters, principal_access_level, limit)
        elif search_mode == 'hybrid':
            return self.search_hybrid(query, filters, principal_access_level, limit, use_expansion)
        else:
            print(f"[DatabaseSearchService] Unknown search mode '{search_mode}', using FTS")
            return self.search_fts(query, filters, principal_access_level, limit)