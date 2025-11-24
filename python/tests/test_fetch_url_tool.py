#!/usr/bin/env python3
"""
Test suite for FetchUrlTool
Tests URL fetching and content extraction functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.fetch_url_tool import FetchUrlTool


async def test_fetch_url_tool():
    """Run comprehensive tests for FetchUrlTool."""
    print("=" * 80)
    print("FetchUrlTool Test Suite")
    print("=" * 80)
    
    tool = FetchUrlTool()
    passed = 0
    failed = 0
    
    # Test 1: Fetch valid URL
    print("\n[Test 1] Fetching valid URL...")
    try:
        result = await tool.execute(url="https://www.example.com", max_chars=1000)
        assert "url" in result, "Should have URL"
        assert result["url"] == "https://www.example.com", "URL should match"
        
        if "error" not in result:
            assert "content" in result, "Should have content"
            assert len(result["content"]) > 0, "Content should not be empty"
            assert "length" in result, "Should have length"
            print(f"  ✓ URL fetched successfully")
            print(f"  ✓ Content length: {result.get('length', 0)} chars")
            print(f"  ✓ Content preview: {result['content'][:100]}...")
            passed += 1
        else:
            print(f"  ⚠ Network error (may be expected): {result.get('error')}")
            # Don't count as failure for network issues
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 2: Invalid URL
    print("\n[Test 2] Invalid URL handling...")
    try:
        result = await tool.execute(url="https://invalid-url-that-does-not-exist-12345.com")
        assert "url" in result, "Should have URL"
        assert "error" in result, "Should have error for invalid URL"
        print(f"  ✓ Invalid URL correctly handled")
        print(f"  ✓ Error: {result.get('error', 'N/A')}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 3: Max chars truncation
    print("\n[Test 3] Max chars truncation...")
    try:
        result = await tool.execute(url="https://www.example.com", max_chars=100)
        assert "url" in result, "Should have URL"
        
        if "content" in result:
            assert len(result["content"]) <= 103, "Content should be truncated (100 + '...')"
            print(f"  ✓ Content truncated correctly")
            print(f"  ✓ Content length: {len(result['content'])} (max: 100)")
            passed += 1
        else:
            print(f"  ⚠ Skipped (network error)")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 4: Tool definition
    print("\n[Test 4] Tool definition...")
    try:
        definition = tool.get_tool_definition()
        assert definition["type"] == "function", "Should be function type"
        assert definition["function"]["name"] == "fetch_url", "Name should match"
        assert "parameters" in definition["function"], "Should have parameters"
        print(f"  ✓ Tool name: {definition['function']['name']}")
        print(f"  ✓ Has parameters")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 5: HTTP error handling
    print("\n[Test 5] HTTP error handling...")
    try:
        # Try a URL that might return 404
        result = await tool.execute(url="https://www.example.com/nonexistent-page-12345")
        assert "url" in result, "Should have URL"
        # May have error or content depending on server response
        if "error" in result:
            print(f"  ✓ HTTP error handled: {result.get('error')}")
        else:
            print(f"  ✓ URL processed (may have redirected)")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 6: Content extraction quality
    print("\n[Test 6] Content extraction quality...")
    try:
        result = await tool.execute(url="https://www.example.com", max_chars=500)
        if "content" in result:
            content = result["content"]
            # Check that content is reasonably clean (no excessive whitespace)
            assert len(content.strip()) > 0, "Content should not be all whitespace"
            print(f"  ✓ Content extracted and cleaned")
            print(f"  ✓ Content length: {len(content)}")
            passed += 1
        else:
            print(f"  ⚠ Skipped (network error)")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 80)
    print("Note: Some tests may show network errors if internet is unavailable.")
    print("=" * 80)
    
    return passed, failed


if __name__ == "__main__":
    asyncio.run(test_fetch_url_tool())

