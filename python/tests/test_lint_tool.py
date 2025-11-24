#!/usr/bin/env python3
"""
Test suite for LintTool
Tests code syntax checking and linting functionality.
"""

import asyncio
import sys
import tempfile
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.lint_tool import LintTool


async def test_lint_tool():
    """Run comprehensive tests for LintTool."""
    print("=" * 80)
    print("LintTool Test Suite")
    print("=" * 80)
    
    tool = LintTool()
    passed = 0
    failed = 0
    
    # Test 1: Valid Python code
    print("\n[Test 1] Linting valid Python code...")
    try:
        code = """
def hello_world():
    print("Hello, World!")
    return True

class TestClass:
    def __init__(self):
        self.value = 42
"""
        result = await tool.execute(code=code, check_syntax=True, check_style=False)
        assert result["success"] is True, "Should succeed"
        assert result["error_count"] == 0, "Should have no errors"
        assert result["total_issues"] == 0, "Should have no issues"
        print(f"  ✓ Valid code passed linting")
        print(f"  ✓ Errors: {result['error_count']}, Warnings: {result['warning_count']}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 2: Syntax error detection
    print("\n[Test 2] Detecting syntax errors...")
    try:
        code = """
def hello_world(
    print("Hello, World!")
    return True
"""
        result = await tool.execute(code=code, check_syntax=True, check_style=False)
        assert result["success"] is True, "Should succeed (tool reports errors)"
        assert result["error_count"] > 0, "Should detect syntax error"
        assert any(issue["type"] == "syntax_error" for issue in result["issues"]), "Should have syntax error"
        print(f"  ✓ Syntax error detected")
        print(f"  ✓ Error count: {result['error_count']}")
        print(f"  ✓ Error message: {result['issues'][0].get('message', 'N/A')}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 3: File-based linting
    print("\n[Test 3] File-based linting...")
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
def test_function():
    x = 1
    y = 2
    return x + y
""")
            temp_path = f.name
        
        try:
            result = await tool.execute(file_path=temp_path, check_syntax=True, check_style=False)
            assert result["success"] is True, "Should succeed"
            assert result["file"] == temp_path, "File path should match"
            assert result["error_count"] == 0, "Should have no errors"
            print(f"  ✓ File-based linting successful")
            print(f"  ✓ File: {result['file']}")
            passed += 1
        finally:
            os.unlink(temp_path)
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 4: Missing parameters
    print("\n[Test 4] Missing parameters handling...")
    try:
        result = await tool.execute()
        assert result["success"] is False, "Should fail without parameters"
        assert "error" in result, "Should have error message"
        print(f"  ✓ Missing parameters correctly handled")
        print(f"  ✓ Error: {result.get('error', 'N/A')}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 5: Invalid file path
    print("\n[Test 5] Invalid file path handling...")
    try:
        result = await tool.execute(file_path="/nonexistent/path/file.py")
        assert result["success"] is False, "Should fail for invalid path"
        assert "error" in result, "Should have error message"
        print(f"  ✓ Invalid file path correctly handled")
        print(f"  ✓ Error: {result.get('error', 'N/A')}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 6: Code with style issues (if linter available)
    print("\n[Test 6] Style checking (if linter available)...")
    try:
        code = """
import os
x=1+2
def test():
    pass
"""
        result = await tool.execute(code=code, check_syntax=True, check_style=True)
        assert result["success"] is True, "Should succeed"
        # Style checking may or may not find issues depending on linter availability
        print(f"  ✓ Style checking completed")
        print(f"  ✓ Total issues: {result['total_issues']}")
        print(f"  ✓ Errors: {result['error_count']}, Warnings: {result['warning_count']}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 7: Tool definition
    print("\n[Test 7] Tool definition...")
    try:
        definition = tool.get_tool_definition()
        assert definition["type"] == "function", "Should be function type"
        assert definition["function"]["name"] == "lint_code", "Name should match"
        assert "parameters" in definition["function"], "Should have parameters"
        print(f"  ✓ Tool name: {definition['function']['name']}")
        print(f"  ✓ Has parameters")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 8: Complex code with multiple issues
    print("\n[Test 8] Complex code with multiple potential issues...")
    try:
        code = """
def function1():
    x=1
    y=2
    return x+y

def function2():
    unused_var = 10
    return 42
"""
        result = await tool.execute(code=code, check_syntax=True, check_style=True)
        assert result["success"] is True, "Should succeed"
        print(f"  ✓ Complex code linted")
        print(f"  ✓ Total issues: {result['total_issues']}")
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
    asyncio.run(test_lint_tool())

