#!/usr/bin/env python3
"""
Test suite for SearchReplaceTool
Tests code replacement functionality using content matching.
"""

import asyncio
import sys
import tempfile
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.search_replace_tool import SearchReplaceTool


async def test_search_replace_tool():
    """Run comprehensive tests for SearchReplaceTool."""
    print("=" * 80)
    print("SearchReplaceTool Test Suite")
    print("=" * 80)
    
    tool = SearchReplaceTool()
    passed = 0
    failed = 0
    
    # Test 1: Basic replacement
    print("\n[Test 1] Basic replacement...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.py"
            original_content = """def hello():
    print("Hello")
    return True

def world():
    print("World")
"""
            test_file.write_text(original_content)
            
            # Replace code block
            result = await tool.execute(
                file_path=str(test_file),
                old_string='    print("Hello")',
                new_string='    print("Hello, World!")'
            )
            
            assert result["success"], f"Replacement failed: {result.get('error')}"
            assert result["replacements"] == 1, f"Expected 1 replacement, got {result['replacements']}"
            
            # Verify file content
            new_content = test_file.read_text()
            assert 'print("Hello, World!")' in new_content
            assert 'print("Hello")' not in new_content
            
            print("✅ PASSED")
            passed += 1
    except Exception as e:
        print(f"❌ FAILED: {e}")
        failed += 1
    
    # Test 2: Replacement with context
    print("\n[Test 2] Replacement with context...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            original_content = """def func1():
    x = 1
    return x

def func2():
    x = 1
    return x
"""
            test_file.write_text(original_content)
            
            # Replace with more context to ensure unique match
            result = await tool.execute(
                file_path=str(test_file),
                old_string="""def func1():
    x = 1
    return x""",
                new_string="""def func1():
    x = 2
    return x"""
            )
            
            assert result["success"], f"Replacement failed: {result.get('error')}"
            
            # Verify only func1 was changed
            new_content = test_file.read_text()
            assert 'def func1():\n    x = 2' in new_content
            assert 'def func2():\n    x = 1' in new_content
            
            print("✅ PASSED")
            passed += 1
    except Exception as e:
        print(f"❌ FAILED: {e}")
        failed += 1
    
    # Test 3: Multiple matches (should fail with count=1)
    print("\n[Test 3] Multiple matches (should fail)...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            original_content = """x = 1
y = 1
z = 1
"""
            test_file.write_text(original_content)
            
            # Try to replace "x = 1" which appears multiple times
            result = await tool.execute(
                file_path=str(test_file),
                old_string="x = 1",
                new_string="x = 2",
                count=1
            )
            
            # Should fail because multiple matches found
            assert not result["success"], "Should fail when multiple matches found"
            assert "多个匹配" in result.get("error", "") or "multiple" in result.get("error", "").lower()
            
            print("✅ PASSED")
            passed += 1
    except Exception as e:
        print(f"❌ FAILED: {e}")
        failed += 1
    
    # Test 4: No match found
    print("\n[Test 4] No match found...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            original_content = """def hello():
    print("Hello")
"""
            test_file.write_text(original_content)
            
            # Try to replace non-existent code
            result = await tool.execute(
                file_path=str(test_file),
                old_string="print('Goodbye')",
                new_string="print('Hello')"
            )
            
            assert not result["success"], "Should fail when no match found"
            assert "未找到" in result.get("error", "") or "not found" in result.get("error", "").lower()
            
            print("✅ PASSED")
            passed += 1
    except Exception as e:
        print(f"❌ FAILED: {e}")
        failed += 1
    
    # Test 5: File doesn't exist
    print("\n[Test 5] File doesn't exist...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await tool.execute(
                file_path=str(Path(tmpdir) / "nonexistent.py"),
                old_string="test",
                new_string="test2"
            )
            
            assert not result["success"], "Should fail when file doesn't exist"
            assert "不存在" in result.get("error", "") or "not exist" in result.get("error", "").lower()
            
            print("✅ PASSED")
            passed += 1
    except Exception as e:
        print(f"❌ FAILED: {e}")
        failed += 1
    
    # Test 6: Multi-line replacement
    print("\n[Test 6] Multi-line replacement...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            original_content = """def calculate():
    result = 0
    for i in range(10):
        result += i
    return result
"""
            test_file.write_text(original_content)
            
            # Replace multi-line block
            result = await tool.execute(
                file_path=str(test_file),
                old_string="""    result = 0
    for i in range(10):
        result += i""",
                new_string="""    result = sum(range(10))"""
            )
            
            assert result["success"], f"Replacement failed: {result.get('error')}"
            
            new_content = test_file.read_text()
            assert "result = sum(range(10))" in new_content
            assert "for i in range(10):" not in new_content
            
            print("✅ PASSED")
            passed += 1
    except Exception as e:
        print(f"❌ FAILED: {e}")
        failed += 1
    
    # Test 7: Whitespace preservation
    print("\n[Test 7] Whitespace preservation...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            original_content = """def test():
    if True:
        return 1
"""
            test_file.write_text(original_content)
            
            # Replace with exact whitespace match
            result = await tool.execute(
                file_path=str(test_file),
                old_string="    if True:\n        return 1",
                new_string="    if True:\n        return 2"
            )
            
            assert result["success"], f"Replacement failed: {result.get('error')}"
            
            new_content = test_file.read_text()
            assert "return 2" in new_content
            assert "return 1" not in new_content
            
            print("✅ PASSED")
            passed += 1
    except Exception as e:
        print(f"❌ FAILED: {e}")
        failed += 1
    
    # Test 8: Tool definition
    print("\n[Test 8] Tool definition...")
    try:
        definition = tool.get_tool_definition()
        assert definition["type"] == "function"
        assert definition["function"]["name"] == "search_replace"
        assert "file_path" in definition["function"]["parameters"]["properties"]
        assert "old_string" in definition["function"]["parameters"]["properties"]
        assert "new_string" in definition["function"]["parameters"]["properties"]
        
        print("✅ PASSED")
        passed += 1
    except Exception as e:
        print(f"❌ FAILED: {e}")
        failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print(f"Test Summary: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return passed, failed


if __name__ == "__main__":
    passed, failed = asyncio.run(test_search_replace_tool())
    sys.exit(0 if failed == 0 else 1)

