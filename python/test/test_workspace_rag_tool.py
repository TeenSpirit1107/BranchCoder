#!/usr/bin/env python3
"""
Test suite for WorkspaceRAGTool
Tests RAG-based code retrieval from workspace.
Note: Some tests may fail if RAG index doesn't exist.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.workspace_rag_tool import WorkspaceRAGTool


async def test_workspace_rag_tool():
    """Run comprehensive tests for WorkspaceRAGTool."""
    print("=" * 80)
    print("WorkspaceRAGTool Test Suite")
    print("=" * 80)
    print("Note: Some tests require RAG index to exist in workspace")
    print("=" * 80)
    
    tool = WorkspaceRAGTool()
    passed = 0
    failed = 0
    
    # Test 1: Without workspace directory
    print("\n[Test 1] Without workspace directory...")
    try:
        result = await tool.execute(query="test query")
        assert result["success"] is False, "Should fail without workspace"
        assert "error" in result, "Should have error message"
        assert "workspace directory not set" in result.get("error", "").lower(), "Error should mention workspace"
        print(f"  ✓ Correctly handles missing workspace")
        print(f"  ✓ Error: {result.get('error', 'N/A')}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 2: Tool definition
    print("\n[Test 2] Tool definition...")
    try:
        definition = tool.get_tool_definition()
        assert definition["type"] == "function", "Should be function type"
        assert definition["function"]["name"] == "workspace_rag_retrieve", "Name should match"
        assert "parameters" in definition["function"], "Should have parameters"
        assert "query" in definition["function"]["parameters"]["properties"], "Should have query parameter"
        print(f"  ✓ Tool name: {definition['function']['name']}")
        print(f"  ✓ Has parameters")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 3: Set workspace directory
    print("\n[Test 3] Setting workspace directory...")
    try:
        workspace_dir = str(Path(__file__).parent.parent.parent)
        tool.set_workspace_dir(workspace_dir)
        print(f"  ✓ Workspace directory set: {workspace_dir}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 4: RAG retrieval (may fail if index doesn't exist)
    print("\n[Test 4] RAG retrieval (requires index)...")
    try:
        workspace_dir = str(Path(__file__).parent.parent.parent)
        tool.set_workspace_dir(workspace_dir)
        result = await tool.execute(query="test query")
        
        if result["success"]:
            assert "results" in result, "Should have results"
            assert "count" in result, "Should have count"
            assert "by_type" in result, "Should have by_type"
            assert isinstance(result["results"], list), "Results should be a list"
            print(f"  ✓ RAG retrieval successful")
            print(f"  ✓ Results count: {result.get('count', 0)}")
            print(f"  ✓ By type: {result.get('by_type', {})}")
            
            if len(result["results"]) > 0:
                first_result = result["results"][0]
                assert "type" in first_result, "Result should have type"
                assert "content" in first_result, "Result should have content"
                assert "file_path" in first_result, "Result should have file_path"
                assert "score" in first_result, "Result should have score"
                print(f"  ✓ First result type: {first_result.get('type')}")
                print(f"  ✓ First result file: {first_result.get('file_path', 'N/A')}")
        else:
            print(f"  ⚠ RAG retrieval failed (index may not exist)")
            print(f"  ⚠ Error: {result.get('error', 'N/A')}")
        
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 5: Multiple queries
    print("\n[Test 5] Multiple queries...")
    try:
        workspace_dir = str(Path(__file__).parent.parent.parent)
        tool.set_workspace_dir(workspace_dir)
        
        queries = ["function", "class", "import"]
        results = []
        for query in queries:
            result = await tool.execute(query=query)
            results.append(result)
        
        success_count = sum(1 for r in results if r.get("success"))
        print(f"  ✓ Executed {len(queries)} queries")
        print(f"  ✓ Successful: {success_count}/{len(queries)}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 6: Result structure validation
    print("\n[Test 6] Result structure validation...")
    try:
        workspace_dir = str(Path(__file__).parent.parent.parent)
        tool.set_workspace_dir(workspace_dir)
        result = await tool.execute(query="test")
        
        assert "query" in result, "Should have query"
        assert "success" in result, "Should have success flag"
        
        if result["success"]:
            assert "results" in result, "Should have results"
            assert "count" in result, "Should have count"
            assert "by_type" in result, "Should have by_type"
            assert "file" in result["by_type"], "Should have file count"
            assert "function" in result["by_type"], "Should have function count"
            assert "class" in result["by_type"], "Should have class count"
            print(f"  ✓ Result structure valid")
        else:
            print(f"  ⚠ Result structure valid (but retrieval failed)")
        
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 7: Empty query handling
    print("\n[Test 7] Empty query handling...")
    try:
        workspace_dir = str(Path(__file__).parent.parent.parent)
        tool.set_workspace_dir(workspace_dir)
        result = await tool.execute(query="")
        
        # Empty query may succeed or fail depending on implementation
        assert "query" in result, "Should have query field"
        print(f"  ✓ Empty query handled")
        print(f"  ✓ Success: {result.get('success', False)}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 80)
    print("Note: Some tests may show warnings if RAG index doesn't exist.")
    print("This is expected if the workspace hasn't been indexed yet.")
    print("=" * 80)
    
    return passed, failed


if __name__ == "__main__":
    asyncio.run(test_workspace_rag_tool())

