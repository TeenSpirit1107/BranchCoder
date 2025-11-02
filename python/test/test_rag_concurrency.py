#!/usr/bin/env python3
"""
Test suite for RAG concurrency support.
Tests that multiple concurrent retrieval requests can safely access the RAG service.
Assumes index already exists (will auto-load from disk if available).
"""
import asyncio
import sys
from pathlib import Path

# pytest is optional - tests can run standalone
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    # Create a dummy pytest marker for standalone execution
    class MockPytestMark:
        def __call__(self, func):
            # Decorator that returns the function unchanged
            return func
    
    class MockPytest:
        class mark:
            asyncio = MockPytestMark()
    pytest = MockPytest()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.indexing import IndexingService


class TestRAGConcurrency:
    """Test suite for RAG concurrency features - only tests retrieval (assumes index already exists)."""
    
    @pytest.mark.asyncio
    async def test_concurrent_retrieval_two_queries(self):
        """Test that two concurrent retrieval requests work correctly."""
        # Initialize indexing service (will auto-load existing index from disk)
        indexing_service = IndexingService(
            enable_rerank=False,  # Disable rerank for faster testing
            rerank_top_n=5,
            initial_candidates=20,
        )
        
        # Create two concurrent retrieval tasks
        queries = ["data processing", "user management"]
        
        # Execute two queries concurrently
        tasks = [indexing_service.retrieve(query, top_k=5) for query in queries]
        results = await asyncio.gather(*tasks)
        
        # Verify both requests completed successfully
        assert len(results) == 2
        for i, result in enumerate(results):
            assert isinstance(result, dict)
            assert "file" in result
            assert "function" in result
            assert "class" in result
            assert isinstance(result["file"], list)
            assert isinstance(result["function"], list)
            assert isinstance(result["class"], list)
            print(f"Query '{queries[i]}' returned {len(result['file'])} files, "
                  f"{len(result['function'])} functions, {len(result['class'])} classes")
    
    @pytest.mark.asyncio
    async def test_concurrent_retrieval_same_query(self):
        """Test that two identical queries can be processed concurrently."""
        indexing_service = IndexingService(
            enable_rerank=False,
            rerank_top_n=5,
            initial_candidates=20,
        )
        
        # Create two identical queries
        query = "data processing"
        
        # Execute two identical queries concurrently
        tasks = [indexing_service.retrieve(query, top_k=5) for _ in range(2)]
        results = await asyncio.gather(*tasks)
        
        # Both should succeed
        assert len(results) == 2
        for result in results:
            assert isinstance(result, dict)
            assert all(key in result for key in ["file", "function", "class"])


# Standalone test function for direct execution
async def run_standalone_tests():
    """Run tests without pytest (for quick validation)."""
    print("=" * 60)
    print("Running RAG Concurrency Tests (Standalone)")
    print("Note: Tests assume index already exists (auto-loaded from disk)")
    print("=" * 60)
    
    try:
        # Initialize indexing service (will auto-load existing index from disk)
        indexing_service = IndexingService(
            enable_rerank=False,
            rerank_top_n=5,
            initial_candidates=20,
        )
        
        # Test 1: Two concurrent retrieval queries
        print("\n[Test 1] Two Concurrent Retrieval Queries...")
        try:
            queries = ["data processing", "user management"]
            tasks = [indexing_service.retrieve(query, top_k=5) for query in queries]
            results = await asyncio.gather(*tasks)
            assert len(results) == 2
            print(f"✓ Successfully processed 2 concurrent queries")
            for i, result in enumerate(results):
                print(f"  Query '{queries[i]}': {len(result.get('file', []))} files, "
                      f"{len(result.get('function', []))} functions, "
                      f"{len(result.get('class', []))} classes")
        except Exception as e:
            print(f"✗ Test 1 failed: {e}")
            raise
        
        # Test 2: Two identical queries concurrently
        print("\n[Test 2] Two Identical Queries Concurrently...")
        try:
            query = "data processing"
            tasks = [indexing_service.retrieve(query, top_k=5) for _ in range(2)]
            results = await asyncio.gather(*tasks)
            assert len(results) == 2
            print(f"✓ Successfully handled 2 identical concurrent requests")
        except Exception as e:
            print(f"✗ Test 2 failed: {e}")
            raise
        
        print("\n" + "=" * 60)
        print("All standalone tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"Tests failed with error: {e}")
        print("Note: Make sure index already exists (run indexing first if needed)")
        print("Note: Make sure OpenAI API keys are configured for embeddings.")
        print("=" * 60)
        raise


if __name__ == "__main__":
    # Run standalone tests
    asyncio.run(run_standalone_tests())

