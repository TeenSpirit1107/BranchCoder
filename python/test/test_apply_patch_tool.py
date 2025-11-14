#!/usr/bin/env python3
"""
Test suite for ApplyPatchTool
Tests patch application functionality including unified diff parsing and file patching.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.apply_patch_tool import ApplyPatchTool


async def test_apply_patch_tool():
    """Run comprehensive tests for ApplyPatchTool."""
    print("=" * 80)
    print("ApplyPatchTool Test Suite")
    print("=" * 80)
    
    tool = ApplyPatchTool()
    passed = 0
    failed = 0
    
    # Test 1: Basic patch application
    print("\n[Test 1] Basic patch application...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.txt"
            original_content = """Line 1
Line 2
Line 3
Line 4
Line 5"""
            test_file.write_text(original_content)
            
            # Create a patch
            patch_content = """--- test.txt
+++ test.txt
@@ -1,5 +1,5 @@
 Line 1
-Line 2
+Line 2 Modified
 Line 3
 Line 4
 Line 5"""
            
            tool.set_workspace_dir(tmpdir)
            result = await tool.execute(patch_content=patch_content, target_file="test.txt")
            
            assert result["success"] is True, "Patch should succeed"
            assert result["patches_applied"] == 1, "Should apply 1 patch"
            
            # Verify file was modified
            new_content = test_file.read_text()
            assert "Line 2 Modified" in new_content, "File should contain modified line"
            assert "Line 2" not in new_content or new_content.count("Line 2") == 1, "Original line should be replaced"
            
            print(f"  ✓ Patch applied successfully")
            print(f"  ✓ File modified correctly")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        failed += 1
    
    # Test 2: Patch with multiple hunks
    print("\n[Test 2] Patch with multiple changes...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            original_content = """def hello():
    print("Hello")
    return True

def world():
    print("World")
    return False"""
            test_file.write_text(original_content)
            
            patch_content = """--- test.py
+++ test.py
@@ -1,3 +1,3 @@
 def hello():
-    print("Hello")
+    print("Hello, World!")
     return True
@@ -4,3 +4,3 @@
 def world():
-    print("World")
+    print("World!")
     return False"""
            
            tool.set_workspace_dir(tmpdir)
            result = await tool.execute(patch_content=patch_content, target_file="test.py")
            
            assert result["success"] is True, "Patch should succeed"
            
            new_content = test_file.read_text()
            assert "Hello, World!" in new_content, "First change should be applied"
            assert "World!" in new_content, "Second change should be applied"
            
            print(f"  ✓ Multiple changes applied")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        failed += 1
    
    # Test 3: Dry run
    print("\n[Test 3] Dry run (validation only)...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            original_content = "Original content"
            test_file.write_text(original_content)
            
            patch_content = """--- test.txt
+++ test.txt
@@ -1,1 +1,1 @@
-Original content
+Modified content"""
            
            tool.set_workspace_dir(tmpdir)
            result = await tool.execute(patch_content=patch_content, target_file="test.txt", dry_run=True)
            
            assert result["success"] is True, "Dry run should succeed"
            assert result.get("dry_run") is True, "Should indicate dry run"
            
            # Verify file was NOT modified
            current_content = test_file.read_text()
            assert current_content == original_content, "File should not be modified in dry run"
            
            print(f"  ✓ Dry run validated patch without modifying file")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        failed += 1
    
    # Test 4: Patch with context lines
    print("\n[Test 4] Patch with context lines...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            original_content = """Header line
Context before
Line to change
Context after
Footer line"""
            test_file.write_text(original_content)
            
            patch_content = """--- test.txt
+++ test.txt
@@ -1,5 +1,5 @@
 Header line
 Context before
-Line to change
+Line changed
 Context after
 Footer line"""
            
            tool.set_workspace_dir(tmpdir)
            result = await tool.execute(patch_content=patch_content, target_file="test.txt")
            
            assert result["success"] is True, "Patch should succeed"
            
            new_content = test_file.read_text()
            assert "Line changed" in new_content, "Line should be changed"
            assert "Line to change" not in new_content, "Original line should be removed"
            
            print(f"  ✓ Context-aware patch applied")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        failed += 1
    
    # Test 5: Invalid patch format
    print("\n[Test 5] Invalid patch format handling...")
    try:
        result = await tool.execute(patch_content="This is not a patch")
        assert result["success"] is False, "Invalid patch should fail"
        assert "error" in result, "Should return error message"
        print(f"  ✓ Invalid patch correctly rejected")
        print(f"  ✓ Error: {result.get('error', 'N/A')[:50]}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 6: File not found
    print("\n[Test 6] File not found handling...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            patch_content = """--- nonexistent.txt
+++ nonexistent.txt
@@ -1,1 +1,1 @@
-Old
+New"""
            
            tool.set_workspace_dir(tmpdir)
            result = await tool.execute(patch_content=patch_content)
            
            assert result["success"] is False, "Should fail when file doesn't exist"
            assert "error" in result.get("results", [{}])[0], "Should have error in result"
            
            print(f"  ✓ File not found correctly handled")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        failed += 1
    
    # Test 7: Patch from file path
    print("\n[Test 7] Patch from file path...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Original")
            
            patch_file = Path(tmpdir) / "patch.diff"
            patch_content = """--- test.txt
+++ test.txt
@@ -1,1 +1,1 @@
-Original
+Modified"""
            patch_file.write_text(patch_content)
            
            tool.set_workspace_dir(tmpdir)
            result = await tool.execute(patch_content=str(patch_file))
            
            assert result["success"] is True, "Patch from file should succeed"
            
            new_content = test_file.read_text()
            assert "Modified" in new_content, "File should be modified"
            
            print(f"  ✓ Patch from file path applied")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        failed += 1
    
    # Test 8: Tool definition
    print("\n[Test 8] Tool definition...")
    try:
        definition = tool.get_tool_definition()
        assert definition["type"] == "function", "Should be function type"
        assert definition["function"]["name"] == "apply_patch", "Name should match"
        assert "parameters" in definition["function"], "Should have parameters"
        print(f"  ✓ Tool name: {definition['function']['name']}")
        print(f"  ✓ Has parameters")
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
    asyncio.run(test_apply_patch_tool())

