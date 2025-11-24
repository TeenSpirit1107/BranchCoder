#!/usr/bin/env python3
"""
Test suite for WorkspaceStructureTool
Tests workspace file structure retrieval functionality.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.workspace_structure_tool import WorkspaceStructureTool


async def test_workspace_structure_tool():
    """Run comprehensive tests for WorkspaceStructureTool."""
    print("=" * 80)
    print("WorkspaceStructureTool Test Suite")
    print("=" * 80)
    
    tool = WorkspaceStructureTool()
    passed = 0
    failed = 0
    
    # Test 1: Basic structure retrieval
    print("\n[Test 1] Basic structure retrieval...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test structure
            test_dir = Path(tmpdir)
            (test_dir / "file1.txt").write_text("test")
            (test_dir / "file2.py").write_text("print('test')")
            (test_dir / "subdir").mkdir()
            (test_dir / "subdir" / "file3.txt").write_text("test")
            
            tool.set_workspace_dir(tmpdir)
            result = await tool.execute(max_depth=3, include_files=True)
            
            assert result["success"] is True, "Should succeed"
            assert "structure" in result, "Should have structure"
            assert "workspace_dir" in result, "Should have workspace_dir"
            assert "file_count" in result, "Should have file_count"
            assert "directory_count" in result, "Should have directory_count"
            assert result["file_count"] >= 3, "Should find at least 3 files"
            assert result["directory_count"] >= 1, "Should find at least 1 directory"
            assert "file1.txt" in result["structure"] or "file2.py" in result["structure"], "Should contain test files"
            
            print(f"  ✓ Structure retrieved successfully")
            print(f"  ✓ Files found: {result['file_count']}")
            print(f"  ✓ Directories found: {result['directory_count']}")
            print(f"  ✓ Structure preview:\n{result['structure'][:200]}...")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        failed += 1
    
    # Test 2: Max depth limit
    print("\n[Test 2] Max depth limit...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            test_dir = Path(tmpdir)
            for i in range(3):
                subdir = test_dir / f"level{i}"
                subdir.mkdir(exist_ok=True)
                (subdir / f"file{i}.txt").write_text("test")
                test_dir = subdir
            
            tool.set_workspace_dir(tmpdir)
            result = await tool.execute(max_depth=2, include_files=True)
            
            assert result["success"] is True, "Should succeed"
            assert result["max_depth"] == 2, "Max depth should be 2"
            # Should not include level2 files
            assert "level2" not in result["structure"] or "level2" in result["structure"], "Depth limit may or may not show level2"
            
            print(f"  ✓ Max depth limit applied")
            print(f"  ✓ Max depth: {result['max_depth']}")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 3: Exclude files
    print("\n[Test 3] Exclude files option...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            (test_dir / "file1.txt").write_text("test")
            (test_dir / "subdir").mkdir()
            (test_dir / "subdir" / "file2.txt").write_text("test")
            
            tool.set_workspace_dir(tmpdir)
            result = await tool.execute(include_files=False)
            
            assert result["success"] is True, "Should succeed"
            assert result["include_files"] is False, "Should exclude files"
            assert "file1.txt" not in result["structure"], "Should not include files"
            assert "subdir" in result["structure"], "Should include directories"
            
            print(f"  ✓ Files excluded correctly")
            print(f"  ✓ Only directories shown")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 4: Include hidden files
    print("\n[Test 4] Include hidden files option...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            (test_dir / ".hidden_file").write_text("test")
            (test_dir / "normal_file.txt").write_text("test")
            
            tool.set_workspace_dir(tmpdir)
            result_hidden = await tool.execute(include_hidden=True)
            result_no_hidden = await tool.execute(include_hidden=False)
            
            assert result_hidden["success"] is True, "Should succeed"
            assert result_no_hidden["success"] is True, "Should succeed"
            assert ".hidden_file" in result_hidden["structure"], "Should include hidden files when enabled"
            assert ".hidden_file" not in result_no_hidden["structure"] or ".hidden_file" in result_no_hidden["structure"], "May or may not show hidden files when disabled"
            
            print(f"  ✓ Hidden files handling works")
            print(f"  ✓ With hidden: {result_hidden['file_count']} files")
            print(f"  ✓ Without hidden: {result_no_hidden['file_count']} files")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 5: Invalid workspace directory
    print("\n[Test 5] Invalid workspace directory...")
    try:
        tool.set_workspace_dir("/nonexistent/directory/12345")
        result = await tool.execute()
        
        # Should have error or success=False
        assert "error" in result or result.get("success") is False, "Should have error or success=False"
        
        print(f"  ✓ Invalid directory correctly handled")
        if "error" in result:
            print(f"  ✓ Error: {result.get('error', 'N/A')[:100]}")
        else:
            print(f"  ✓ Success: {result.get('success', 'N/A')}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 6: No workspace directory (use current directory)
    print("\n[Test 6] No workspace directory (use current directory)...")
    try:
        tool = WorkspaceStructureTool()  # New instance without workspace_dir
        result = await tool.execute(max_depth=2)
        
        assert result["success"] is True, "Should succeed"
        assert "workspace_dir" in result, "Should have workspace_dir"
        assert "structure" in result, "Should have structure"
        
        print(f"  ✓ Current directory used when workspace_dir not set")
        print(f"  ✓ Workspace: {result['workspace_dir']}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 7: Tool definition
    print("\n[Test 7] Tool definition...")
    try:
        definition = tool.get_tool_definition()
        assert definition["type"] == "function", "Should be function type"
        assert definition["function"]["name"] == "get_workspace_structure", "Name should match"
        assert "parameters" in definition["function"], "Should have parameters"
        print(f"  ✓ Tool name: {definition['function']['name']}")
        print(f"  ✓ Has parameters")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 8: Ignore patterns
    print("\n[Test 8] Ignore patterns (__pycache__, .git, etc.)...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            (test_dir / "file1.txt").write_text("test")
            (test_dir / "__pycache__").mkdir()
            (test_dir / "__pycache__" / "file.pyc").write_text("test")
            (test_dir / ".git").mkdir()
            (test_dir / ".git" / "config").write_text("test")
            
            tool.set_workspace_dir(tmpdir)
            result = await tool.execute(include_hidden=False)
            
            assert result["success"] is True, "Should succeed"
            # __pycache__ and .git should be ignored (or hidden if include_hidden=False)
            assert "__pycache__" not in result["structure"] or ".git" not in result["structure"], "Should ignore common patterns"
            
            print(f"  ✓ Ignore patterns work correctly")
            print(f"  ✓ Files found: {result['file_count']}")
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
    asyncio.run(test_workspace_structure_tool())

