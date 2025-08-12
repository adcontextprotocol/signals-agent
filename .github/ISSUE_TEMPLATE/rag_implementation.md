---
name: Implement RAG for Enhanced Segment Search
about: Improve search quality with vector embeddings and semantic search
title: '[ENHANCEMENT] Implement RAG (Retrieval-Augmented Generation) for Segment Search'
labels: enhancement, performance, search
assignees: ''
---

## Problem Statement
Current FTS5-based search has a quality score of 2.8/5.0 and struggles with:
- Semantic queries ("people who buy expensive things")
- Colloquialisms ("soccer moms", "gym rats")
- Industry terms ("cord cutters", "HENRY")
- Conceptual relationships between terms

## Proposed Solution
Implement RAG with vector embeddings to enable semantic search alongside existing FTS5.

## Implementation Overview
```
Query → Embedding → Vector Search → Top K Results → Hybrid Ranking → Final Results
                         ↓
                  SQLite VSS Extension
```

## Benefits
- **3.9/5.0 improvement potential** over current system
- Semantic understanding of queries
- Typo tolerance
- Better handling of natural language

## Technical Approach
1. Use sentence-transformers for embeddings (free, local)
2. SQLite-vss for vector storage
3. Hybrid search combining FTS5 + vector similarity
4. Generate embeddings during LiveRamp sync

## Quick Wins to Try First
Before implementing RAG, consider:
- [ ] Query expansion dictionary
- [ ] Synonym mapping
- [ ] Common query cache
- [ ] Fuzzy matching for typos

## Acceptance Criteria
- [ ] Search quality score improves to 4.0+/5.0
- [ ] Semantic queries return relevant results
- [ ] Search latency remains under 500ms
- [ ] Storage overhead under 500MB for 200k segments

## References
- [RAG in SQLite](https://towardsdatascience.com/retrieval-augmented-generation-in-sqlite/)
- [sqlite-vss](https://github.com/asg017/sqlite-vss)
- Full implementation plan: `/ISSUE_RAG_IMPLEMENTATION.md`

## Estimated Effort
- Implementation: 3-4 days
- Testing: 1-2 days
- Total: ~1 week

## Priority
Medium-High (implement if search quality becomes a user complaint)