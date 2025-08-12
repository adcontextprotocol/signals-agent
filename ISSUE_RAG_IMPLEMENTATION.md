# Issue: Implement RAG (Retrieval-Augmented Generation) for Segment Search

## Problem Statement
Current search implementation uses basic text matching and FTS5, which has limitations:
- Poor performance on semantic queries ("people who buy expensive things" → luxury segments)
- Cannot understand conceptual relationships between terms
- Struggles with colloquial terms ("soccer moms", "finance bros")
- No typo tolerance beyond exact FTS5 matching
- Cannot find related segments when exact terms don't match

## Proposed Solution: RAG with Vector Embeddings

### Architecture
```
Query → Embedding → Vector Search → Top K Results → Rerank → Final Results
                         ↓
                  SQLite Vector Extension
                  (or separate vector DB)
```

### Implementation Plan

#### Phase 1: Embedding Generation
- Generate embeddings during LiveRamp sync
- Use sentence-transformers or OpenAI embeddings
- Store in SQLite with vector extension (like sqlite-vss)

```python
# During sync_liveramp_catalog.py
for segment in segments:
    embedding = model.encode(f"{segment['name']} {segment['description']}")
    store_embedding(segment_id, embedding)
```

#### Phase 2: Vector Search
- Install sqlite-vss extension
- Create vector index on embeddings
- Implement similarity search

```sql
-- Create virtual table for vector search
CREATE VIRTUAL TABLE segment_embeddings USING vss0(
    embedding(384)  -- dimension depends on model
);

-- Search by similarity
SELECT segment_id, distance
FROM segment_embeddings
WHERE vss_search(embedding, ?)
LIMIT 100;
```

#### Phase 3: Hybrid Search
- Combine vector similarity with FTS5 text search
- Weight results from both methods
- Pass to AI for final ranking

```python
def hybrid_search(query):
    # Get vector search results
    vector_results = vector_search(query, limit=100)
    
    # Get FTS5 results
    fts_results = fts_search(query, limit=100)
    
    # Combine with weights
    combined = merge_results(
        vector_results, weight=0.7,
        fts_results, weight=0.3
    )
    
    return combined[:100]
```

## Benefits
1. **Semantic Understanding**: Find "luxury" segments when searching "expensive"
2. **Typo Tolerance**: "finace" → finance segments
3. **Conceptual Matching**: "soccer moms" → family/suburban segments
4. **Better Relevance**: Understand context and relationships
5. **Scalability**: Efficient even with 200k+ segments

## Technical Requirements

### Option 1: SQLite Extensions (Recommended)
- [sqlite-vss](https://github.com/asg017/sqlite-vss) - Vector similarity search
- Sentence-transformers for embeddings
- ~10MB per 100k segments (384-dim embeddings)

### Option 2: Separate Vector DB
- ChromaDB or Weaviate
- More features but adds complexity
- Better for very large scale (1M+ segments)

### Embedding Models
```python
# Option 1: Sentence-transformers (local, free)
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')  # 384 dimensions

# Option 2: OpenAI (API, paid)
import openai
response = openai.Embedding.create(
    model="text-embedding-ada-002",  # 1536 dimensions
    input=text
)
```

## Implementation Steps

1. **Add dependencies**:
```bash
pip install sentence-transformers sqlite-vss numpy
```

2. **Modify sync script** to generate embeddings:
```python
# sync_liveramp_catalog.py
def store_segments_with_embeddings(segments):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    for segment in segments:
        text = f"{segment['name']} {segment['description']}"
        embedding = model.encode(text)
        
        # Store embedding alongside segment
        store_segment_embedding(segment['id'], embedding)
```

3. **Create vector search function**:
```python
def vector_search(query: str, limit: int = 100):
    # Generate query embedding
    query_embedding = model.encode(query)
    
    # Search in vector index
    results = db.execute("""
        SELECT segment_id, distance
        FROM segment_embeddings
        WHERE vss_search(embedding, ?)
        LIMIT ?
    """, (query_embedding, limit))
    
    return results
```

4. **Update main search** to use hybrid approach

## Performance Considerations

### Storage
- 384-dim float32 embeddings = 1.5KB per segment
- 200k segments = ~300MB additional storage
- Can use quantization to reduce by 4x

### Speed
- Embedding generation: ~100 segments/second
- Vector search: <100ms for 200k segments
- One-time sync cost: ~30 min additional

### Accuracy vs Speed Tradeoffs
- Smaller models (MiniLM): Faster, less accurate
- Larger models (BERT-large): Slower, more accurate
- Can use approximate search (HNSW) for speed

## Testing Strategy

Compare search quality metrics:
```python
TEST_CASES = [
    {
        "query": "soccer moms",
        "expected_concepts": ["family", "suburban", "parents", "children"],
        "current_score": 2.0,  # Poor
        "expected_score": 8.0   # Good
    },
    {
        "query": "people who buy expensive things",
        "expected_concepts": ["luxury", "affluent", "premium", "high-income"],
        "current_score": 0.0,  # Fails
        "expected_score": 9.0   # Excellent
    }
]
```

## Migration Path

1. **Phase 1**: Run in parallel, compare results
2. **Phase 2**: Use for fallback when FTS5 returns few results
3. **Phase 3**: Make primary search method
4. **Phase 4**: Remove FTS5 dependency

## Estimated Effort
- Initial implementation: 2-3 days
- Testing and tuning: 1-2 days
- Production deployment: 1 day
- Total: ~1 week

## References
- [RAG in SQLite](https://towardsdatascience.com/retrieval-augmented-generation-in-sqlite/)
- [sqlite-vss documentation](https://github.com/asg017/sqlite-vss)
- [Sentence Transformers](https://www.sbert.net/)
- [Vector Search Benchmarks](https://ann-benchmarks.com/)

## Decision Criteria
Implement RAG if:
- [ ] Semantic queries are important for users
- [ ] Current search quality score < 5.0
- [ ] Users complain about search relevance
- [ ] We need to support non-English queries
- [ ] Catalog grows beyond 500k segments

## Alternative: Quick Wins First
Before implementing RAG, consider:
1. Synonyms table for common terms
2. Query expansion (finance → financial, banking, investment)
3. Fuzzy matching for typos
4. Caching common queries

---

**Priority**: MEDIUM-HIGH
**Complexity**: MEDIUM
**Impact**: HIGH for search quality
**Risk**: LOW (can run in parallel with existing)