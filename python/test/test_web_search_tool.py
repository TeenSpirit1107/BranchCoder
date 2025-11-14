#!/usr/bin/env python3
"""
Test suite for WebSearchTool
Tests web search functionality using DDGS.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.web_search_tool import WebSearchTool


async def test_web_search_tool():
    """Run comprehensive tests for WebSearchTool."""
    print("=" * 80)
    print("WebSearchTool Test Suite")
    print("=" * 80)
    
    tool = WebSearchTool()
    passed = 0
    failed = 0
    
    # Test 1: Basic web search
    print("\n[Test 1] Basic web search...")
    try:
        result = await tool.execute(query="Python programming", max_results=5)
        assert result["status"] == "success", "Search should succeed"
        assert "results" in result, "Should have results"
        assert len(result["results"]) > 0, "Search should return at least one result"
        assert "title" in result["results"][0], "Result should have title"
        assert "url" in result["results"][0], "Result should have URL"
        assert "snippet" in result["results"][0], "Result should have snippet"
        print(f"  ✓ Search successful")
        print(f"  ✓ Results: {len(result['results'])}")
        print(f"  ✓ First result: {result['results'][0].get('title', 'N/A')[:50]}...")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 2: Empty query
    print("\n[Test 2] Empty query handling...")
    try:
        result = await tool.execute(query="")
        assert result["status"] == "error", "Should return error"
        assert "error" in result, "Should have error message"
        print(f"  ✓ Empty query correctly handled")
        print(f"  ✓ Error: {result.get('error', 'N/A')}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 3: Different search types
    print("\n[Test 3] Different search types...")
    try:
        # General search
        result1 = await tool.execute(query="Python", search_type="general", max_results=3)
        assert result1["status"] == "success", "General search should succeed"
        
        # API documentation search
        result2 = await tool.execute(query="requests", search_type="api_documentation", max_results=3)
        assert result2["status"] == "success", "API doc search should succeed"
        
        # Python packages search
        result3 = await tool.execute(query="numpy", search_type="python_packages", max_results=3)
        assert result3["status"] == "success", "Python packages search should succeed"
        
        # GitHub search
        result4 = await tool.execute(query="python", search_type="github", max_results=3)
        assert result4["status"] == "success", "GitHub search should succeed"
        
        print(f"  ✓ General search: {len(result1['results'])} results")
        print(f"  ✓ API documentation search: {len(result2['results'])} results")
        print(f"  ✓ Python packages search: {len(result3['results'])} results")
        print(f"  ✓ GitHub search: {len(result4['results'])} results")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 4: Max results limit
    print("\n[Test 4] Max results limit enforcement...")
    try:
        result = await tool.execute(query="Python", max_results=100)  # Should be limited to 50
        assert result["status"] == "success", "Should succeed"
        assert len(result["results"]) <= 50, "Should be limited to 50"
        print(f"  ✓ Max results limited correctly: {len(result['results'])}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 5: Result structure
    print("\n[Test 5] Result structure validation...")
    try:
        result = await tool.execute(query="test", max_results=2)
        assert result["status"] == "success", "Should succeed"
        assert "query" in result, "Should have query"
        assert "search_type" in result, "Should have search_type"
        assert "total_results" in result, "Should have total_results"
        
        # Results may be empty, but structure should be valid
        if len(result["results"]) > 0:
            first_result = result["results"][0]
            assert "title" in first_result, "Result should have title"
            assert "url" in first_result, "Result should have URL"
            assert "snippet" in first_result, "Result should have snippet"
            assert "rank" in first_result, "Result should have rank"
        
        print(f"  ✓ Result structure valid")
        print(f"  ✓ Query: {result['query']}")
        print(f"  ✓ Search type: {result['search_type']}")
        print(f"  ✓ Results count: {len(result['results'])}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 6: Tool definition
    print("\n[Test 6] Tool definition...")
    try:
        definition = tool.get_tool_definition()
        assert definition["type"] == "function", "Should be function type"
        assert definition["function"]["name"] == "web_search", "Name should match"
        assert "parameters" in definition["function"], "Should have parameters"
        print(f"  ✓ Tool name: {definition['function']['name']}")
        print(f"  ✓ Has parameters")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 7: Minimum max_results
    print("\n[Test 7] Minimum max_results handling...")
    try:
        result = await tool.execute(query="test", max_results=0)  # Should be adjusted to 1
        assert result["status"] == "success", "Should succeed"
        assert len(result["results"]) > 0, "Should return at least one result"
        print(f"  ✓ Minimum max_results handled: {len(result['results'])} results")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return passed, failed


if __name__ == "__main__":
    asyncio.run(test_web_search_tool())

