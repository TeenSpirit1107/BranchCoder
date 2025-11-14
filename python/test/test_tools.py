#!/usr/bin/env python3
"""
Comprehensive test suite for all tools in the tools directory.
Tests each tool to verify accuracy and functionality.
"""

import asyncio
import sys
import tempfile
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# pytest is optional - tests can run standalone
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    # Create a dummy pytest marker for standalone execution
    class MockPytestMark:
        def __call__(self, func):
            return func
    class MockPytest:
        class mark:
            asyncio = MockPytestMark()
    pytest = MockPytest()

from tools.command_tool import CommandTool
from tools.lint_tool import LintTool
from tools.web_search_tool import WebSearchTool
from tools.fetch_url_tool import FetchUrlTool
from tools.workspace_rag_tool import WorkspaceRAGTool


class TestCommandTool:
    """Test suite for CommandTool."""
    
    @pytest.mark.asyncio
    async def test_execute_simple_command(self):
        """Test executing a simple command."""
        tool = CommandTool()
        result = await tool.execute(command="echo 'Hello, World!'")
        
        assert result["success"] is True
        assert "Hello, World!" in result["stdout"]
        assert result["returncode"] == 0
        print(f"✓ Simple command test passed: {result['stdout'].strip()}")
    
    @pytest.mark.asyncio
    async def test_execute_command_with_workspace_dir(self):
        """Test executing command with workspace directory set."""
        tool = CommandTool()
        
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            tool.set_workspace_dir(tmpdir)
            
            # Create a test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")
            
            # List files in workspace
            result = await tool.execute(command="ls -la")
            
            assert result["success"] is True
            assert "test.txt" in result["stdout"]
            print(f"✓ Workspace directory test passed")
    
    @pytest.mark.asyncio
    async def test_execute_invalid_command(self):
        """Test executing an invalid command."""
        tool = CommandTool()
        result = await tool.execute(command="nonexistent_command_xyz123")
        
        assert result["success"] is False
        assert result["returncode"] != 0
        print(f"✓ Invalid command test passed (expected failure)")
    
    @pytest.mark.asyncio
    async def test_execute_command_timeout(self):
        """Test command timeout handling."""
        tool = CommandTool()
        result = await tool.execute(command="sleep 2", timeout=1)
        
        assert result["success"] is False
        error_msg = result.get("error", "").lower()
        assert "timeout" in error_msg or "timed out" in error_msg
        print(f"✓ Timeout test passed")


class TestLintTool:
    """Test suite for LintTool."""
    
    @pytest.mark.asyncio
    async def test_lint_valid_code(self):
        """Test linting valid Python code."""
        tool = LintTool()
        code = """
def hello_world():
    print("Hello, World!")
    return True
"""
        result = await tool.execute(code=code, check_syntax=True, check_style=False)
        
        assert result["success"] is True
        assert result["error_count"] == 0
        print(f"✓ Valid code lint test passed")
    
    @pytest.mark.asyncio
    async def test_lint_syntax_error(self):
        """Test linting code with syntax error."""
        tool = LintTool()
        code = """
def hello_world(
    print("Hello, World!")
    return True
"""
        result = await tool.execute(code=code, check_syntax=True, check_style=False)
        
        assert result["success"] is True
        assert result["error_count"] > 0
        assert any(issue["type"] == "syntax_error" for issue in result["issues"])
        print(f"✓ Syntax error detection test passed")
    
    @pytest.mark.asyncio
    async def test_lint_from_file(self):
        """Test linting from a file path."""
        tool = LintTool()
        
        # Create a temporary Python file
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
            
            assert result["success"] is True
            assert result["file"] == temp_path
            print(f"✓ File-based lint test passed")
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_lint_missing_parameters(self):
        """Test linting with missing parameters."""
        tool = LintTool()
        result = await tool.execute()
        
        assert result["success"] is False
        assert "error" in result
        print(f"✓ Missing parameters test passed")


class TestWebSearchTool:
    """Test suite for WebSearchTool."""
    
    @pytest.mark.asyncio
    async def test_web_search_basic(self):
        """Test basic web search."""
        tool = WebSearchTool()
        result = await tool.execute(query="Python programming", max_results=5)
        
        assert result["status"] == "success"
        assert "results" in result
        assert len(result["results"]) > 0, "Search should return at least one result"
        assert "title" in result["results"][0]
        assert "url" in result["results"][0]
        print(f"✓ Basic web search test passed: {len(result['results'])} results")
    
    @pytest.mark.asyncio
    async def test_web_search_empty_query(self):
        """Test web search with empty query."""
        tool = WebSearchTool()
        result = await tool.execute(query="")
        
        assert result["status"] == "error"
        assert "error" in result
        print(f"✓ Empty query test passed")
    
    @pytest.mark.asyncio
    async def test_web_search_different_types(self):
        """Test different search types."""
        tool = WebSearchTool()
        
        # Test general search
        result1 = await tool.execute(query="Python", search_type="general", max_results=3)
        assert result1["status"] == "success"
        
        # Test API documentation search
        result2 = await tool.execute(query="requests", search_type="api_documentation", max_results=3)
        assert result2["status"] == "success"
        
        # Test Python packages search
        result3 = await tool.execute(query="numpy", search_type="python_packages", max_results=3)
        assert result3["status"] == "success"
        
        print(f"✓ Different search types test passed")
    
    @pytest.mark.asyncio
    async def test_web_search_max_results_limit(self):
        """Test max_results limit enforcement."""
        tool = WebSearchTool()
        result = await tool.execute(query="Python", max_results=100)  # Should be limited to 50
        
        assert result["status"] == "success"
        assert len(result["results"]) <= 50
        print(f"✓ Max results limit test passed")


class TestFetchUrlTool:
    """Test suite for FetchUrlTool."""
    
    @pytest.mark.asyncio
    async def test_fetch_url_valid(self):
        """Test fetching a valid URL."""
        tool = FetchUrlTool()
        # Use a simple, reliable URL
        result = await tool.execute(url="https://www.example.com", max_chars=1000)
        
        assert "url" in result
        assert result["url"] == "https://www.example.com"
        
        if "error" not in result:
            assert "content" in result
            assert len(result["content"]) > 0
            print(f"✓ Valid URL fetch test passed: {len(result.get('content', ''))} chars")
        else:
            print(f"⚠ URL fetch returned error (may be network issue): {result.get('error')}")
    
    @pytest.mark.asyncio
    async def test_fetch_url_invalid(self):
        """Test fetching an invalid URL."""
        tool = FetchUrlTool()
        result = await tool.execute(url="https://invalid-url-that-does-not-exist-12345.com")
        
        assert "url" in result
        assert "error" in result
        print(f"✓ Invalid URL test passed")
    
    @pytest.mark.asyncio
    async def test_fetch_url_max_chars(self):
        """Test max_chars truncation."""
        tool = FetchUrlTool()
        result = await tool.execute(url="https://www.example.com", max_chars=100)
        
        assert "url" in result
        if "content" in result:
            assert len(result["content"]) <= 103  # 100 + "..."
            print(f"✓ Max chars truncation test passed")
        else:
            print(f"⚠ Max chars test skipped (network error)")


class TestWorkspaceRAGTool:
    """Test suite for WorkspaceRAGTool."""
    
    @pytest.mark.asyncio
    async def test_workspace_rag_without_workspace(self):
        """Test RAG tool without workspace directory set."""
        tool = WorkspaceRAGTool()
        result = await tool.execute(query="test query")
        
        assert result["success"] is False
        assert "error" in result
        print(f"✓ No workspace directory test passed")
    
    @pytest.mark.asyncio
    async def test_workspace_rag_tool_definition(self):
        """Test tool definition is correct."""
        tool = WorkspaceRAGTool()
        definition = tool.get_tool_definition()
        
        assert definition["type"] == "function"
        assert definition["function"]["name"] == "workspace_rag_retrieve"
        assert "parameters" in definition["function"]
        print(f"✓ Tool definition test passed")
    
    @pytest.mark.asyncio
    async def test_workspace_rag_with_workspace(self):
        """Test RAG tool with workspace directory (may fail if index doesn't exist)."""
        tool = WorkspaceRAGTool()
        
        # Use current workspace if available
        workspace_dir = str(Path(__file__).parent.parent.parent)
        tool.set_workspace_dir(workspace_dir)
        
        result = await tool.execute(query="test query")
        
        # This may succeed or fail depending on whether index exists
        if result["success"]:
            assert "results" in result
            assert "count" in result
            print(f"✓ Workspace RAG test passed: {result['count']} results")
        else:
            print(f"⚠ Workspace RAG test: {result.get('error')} (index may not exist)")


# Standalone test functions for direct execution
async def run_all_tests():
    """Run all tests without pytest (for quick validation)."""
    print("=" * 80)
    print("Running Tool Tests (Standalone)")
    print("=" * 80)
    
    test_results = {
        "passed": [],
        "failed": []
    }
    
    # Test CommandTool
    print("\n" + "=" * 80)
    print("Testing CommandTool")
    print("=" * 80)
    try:
        tool = CommandTool()
        
        # Test 1: Simple command
        print("\n[Test 1] Simple command execution...")
        result = await tool.execute(command="echo 'Hello, World!'")
        assert result["success"] is True
        assert "Hello, World!" in result["stdout"]
        test_results["passed"].append("CommandTool: Simple command")
        print("✓ Passed")
        
        # Test 2: Workspace directory
        print("\n[Test 2] Command with workspace directory...")
        with tempfile.TemporaryDirectory() as tmpdir:
            tool.set_workspace_dir(tmpdir)
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")
            result = await tool.execute(command="ls -la")
            assert result["success"] is True
            assert "test.txt" in result["stdout"]
            test_results["passed"].append("CommandTool: Workspace directory")
            print("✓ Passed")
        
        # Test 3: Invalid command
        print("\n[Test 3] Invalid command handling...")
        result = await tool.execute(command="nonexistent_command_xyz123")
        assert result["success"] is False
        test_results["passed"].append("CommandTool: Invalid command")
        print("✓ Passed")
        
    except Exception as e:
        test_results["failed"].append(f"CommandTool: {str(e)}")
        print(f"✗ Failed: {e}")
    
    # Test LintTool
    print("\n" + "=" * 80)
    print("Testing LintTool")
    print("=" * 80)
    try:
        tool = LintTool()
        
        # Test 1: Valid code
        print("\n[Test 1] Linting valid code...")
        code = """
def hello_world():
    print("Hello, World!")
    return True
"""
        result = await tool.execute(code=code, check_syntax=True, check_style=False)
        assert result["success"] is True
        assert result["error_count"] == 0
        test_results["passed"].append("LintTool: Valid code")
        print("✓ Passed")
        
        # Test 2: Syntax error
        print("\n[Test 2] Detecting syntax errors...")
        code = """
def hello_world(
    print("Hello, World!")
    return True
"""
        result = await tool.execute(code=code, check_syntax=True, check_style=False)
        assert result["success"] is True
        assert result["error_count"] > 0
        test_results["passed"].append("LintTool: Syntax error detection")
        print("✓ Passed")
        
        # Test 3: File-based linting
        print("\n[Test 3] File-based linting...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def test(): return 1")
            temp_path = f.name
        try:
            result = await tool.execute(file_path=temp_path, check_syntax=True, check_style=False)
            assert result["success"] is True
            test_results["passed"].append("LintTool: File-based linting")
            print("✓ Passed")
        finally:
            os.unlink(temp_path)
        
        # Test 4: Missing parameters
        print("\n[Test 4] Missing parameters handling...")
        result = await tool.execute()
        assert result["success"] is False
        test_results["passed"].append("LintTool: Missing parameters")
        print("✓ Passed")
        
    except Exception as e:
        test_results["failed"].append(f"LintTool: {str(e)}")
        print(f"✗ Failed: {e}")
    
    # Test WebSearchTool
    print("\n" + "=" * 80)
    print("Testing WebSearchTool")
    print("=" * 80)
    try:
        tool = WebSearchTool()
        
        # Test 1: Basic search
        print("\n[Test 1] Basic web search...")
        result = await tool.execute(query="Python programming", max_results=3)
        assert result["status"] == "success"
        assert "results" in result
        assert len(result["results"]) > 0, "Search should return at least one result"
        assert "title" in result["results"][0], "Result should have title"
        assert "url" in result["results"][0], "Result should have URL"
        test_results["passed"].append("WebSearchTool: Basic search")
        print(f"✓ Passed ({len(result['results'])} results)")
        
        # Test 2: Empty query
        print("\n[Test 2] Empty query handling...")
        result = await tool.execute(query="")
        assert result["status"] == "error"
        test_results["passed"].append("WebSearchTool: Empty query")
        print("✓ Passed")
        
        # Test 3: Different search types
        print("\n[Test 3] Different search types...")
        result1 = await tool.execute(query="Python", search_type="general", max_results=2)
        result2 = await tool.execute(query="requests", search_type="api_documentation", max_results=2)
        assert result1["status"] == "success"
        assert result2["status"] == "success"
        test_results["passed"].append("WebSearchTool: Search types")
        print("✓ Passed")
        
    except Exception as e:
        test_results["failed"].append(f"WebSearchTool: {str(e)}")
        print(f"✗ Failed: {e}")
    
    # Test FetchUrlTool
    print("\n" + "=" * 80)
    print("Testing FetchUrlTool")
    print("=" * 80)
    try:
        tool = FetchUrlTool()
        
        # Test 1: Valid URL
        print("\n[Test 1] Fetching valid URL...")
        result = await tool.execute(url="https://www.example.com", max_chars=500)
        assert "url" in result
        if "error" not in result:
            assert "content" in result
            test_results["passed"].append("FetchUrlTool: Valid URL")
            print(f"✓ Passed ({len(result.get('content', ''))} chars)")
        else:
            test_results["failed"].append(f"FetchUrlTool: Network error - {result.get('error')}")
            print(f"⚠ Network error (may be expected): {result.get('error')}")
        
        # Test 2: Invalid URL
        print("\n[Test 2] Invalid URL handling...")
        result = await tool.execute(url="https://invalid-url-that-does-not-exist-12345.com")
        assert "error" in result
        test_results["passed"].append("FetchUrlTool: Invalid URL")
        print("✓ Passed")
        
        # Test 3: Max chars truncation
        print("\n[Test 3] Max chars truncation...")
        result = await tool.execute(url="https://www.example.com", max_chars=50)
        if "content" in result:
            assert len(result["content"]) <= 53  # 50 + "..."
            test_results["passed"].append("FetchUrlTool: Max chars")
            print("✓ Passed")
        else:
            print("⚠ Skipped (network error)")
        
    except Exception as e:
        test_results["failed"].append(f"FetchUrlTool: {str(e)}")
        print(f"✗ Failed: {e}")
    
    # Test WorkspaceRAGTool
    print("\n" + "=" * 80)
    print("Testing WorkspaceRAGTool")
    print("=" * 80)
    try:
        tool = WorkspaceRAGTool()
        
        # Test 1: Without workspace
        print("\n[Test 1] Without workspace directory...")
        result = await tool.execute(query="test query")
        assert result["success"] is False
        test_results["passed"].append("WorkspaceRAGTool: No workspace")
        print("✓ Passed")
        
        # Test 2: Tool definition
        print("\n[Test 2] Tool definition...")
        definition = tool.get_tool_definition()
        assert definition["type"] == "function"
        assert definition["function"]["name"] == "workspace_rag_retrieve"
        test_results["passed"].append("WorkspaceRAGTool: Tool definition")
        print("✓ Passed")
        
        # Test 3: With workspace (may fail if index doesn't exist)
        print("\n[Test 3] With workspace directory...")
        workspace_dir = str(Path(__file__).parent.parent.parent)
        tool.set_workspace_dir(workspace_dir)
        result = await tool.execute(query="test query")
        if result["success"]:
            test_results["passed"].append("WorkspaceRAGTool: With workspace")
            print(f"✓ Passed ({result.get('count', 0)} results)")
        else:
            print(f"⚠ Workspace RAG: {result.get('error')} (index may not exist)")
        
    except Exception as e:
        test_results["failed"].append(f"WorkspaceRAGTool: {str(e)}")
        print(f"✗ Failed: {e}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Passed: {len(test_results['passed'])}")
    print(f"Failed: {len(test_results['failed'])}")
    
    if test_results["passed"]:
        print("\n✓ Passed tests:")
        for test in test_results["passed"]:
            print(f"  - {test}")
    
    if test_results["failed"]:
        print("\n✗ Failed tests:")
        for test in test_results["failed"]:
            print(f"  - {test}")
    
    print("\n" + "=" * 80)
    if len(test_results["failed"]) == 0:
        print("All tests passed!")
    else:
        print(f"{len(test_results['failed'])} test(s) failed")
    print("=" * 80)
    
    return test_results


if __name__ == "__main__":
    # Run standalone tests
    asyncio.run(run_all_tests())

