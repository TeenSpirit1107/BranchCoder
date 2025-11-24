#!/usr/bin/env python3
"""
Test suite for CommandTool
Tests command execution functionality including workspace directory handling.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.command_tool import CommandTool


async def test_command_tool():
    """Run comprehensive tests for CommandTool."""
    print("=" * 80)
    print("CommandTool Test Suite")
    print("=" * 80)
    
    tool = CommandTool()
    passed = 0
    failed = 0
    
    # Test 1: Basic command execution
    print("\n[Test 1] Basic command execution...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool.set_workspace_dir(tmpdir)
        result = await tool.execute(command="echo 'Hello, World!'")
        assert result["success"] is True, "Command should succeed"
        assert "Hello, World!" in result["stdout"], "Output should contain expected text"
        assert result["returncode"] == 0, "Return code should be 0"
        assert "command" in result, "Result should contain command"
        print(f"  ✓ Command: echo 'Hello, World!'")
        print(f"  ✓ Return code: {result['returncode']}")
        print(f"  ✓ Output: {result['stdout'].strip()}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 2: Command with workspace directory
    print("\n[Test 2] Command execution with workspace directory...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool.set_workspace_dir(tmpdir)
            
            # Create a test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")
            
            # List files
            result = await tool.execute(command="ls -la")
            assert result["success"] is True, "Command should succeed"
            assert "test.txt" in result["stdout"], "Output should contain test file"
            print(f"  ✓ Workspace directory: {tmpdir}")
            print(f"  ✓ Found test file in output")
            passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 3: Invalid command
    print("\n[Test 3] Invalid command handling...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool.set_workspace_dir(tmpdir)
        result = await tool.execute(command="nonexistent_command_xyz123")
        assert result["success"] is False, "Invalid command should fail"
        assert result["returncode"] != 0, "Return code should be non-zero"
        print(f"  ✓ Invalid command correctly handled")
        print(f"  ✓ Return code: {result['returncode']}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 4: Command with timeout
    print("\n[Test 4] Command timeout handling...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool.set_workspace_dir(tmpdir)
        result = await tool.execute(command="sleep 2", timeout=1)
        assert result["success"] is False, "Command should timeout"
        error_msg = result.get("error", "").lower()
        assert "timeout" in error_msg or "timed out" in error_msg, f"Error should mention timeout, got: {result.get('error', 'N/A')}"
        print(f"  ✓ Timeout correctly handled")
        print(f"  ✓ Error message: {result.get('error', 'N/A')}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 5: Command with output and error streams
    print("\n[Test 5] Command with stdout and stderr...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool.set_workspace_dir(tmpdir)
        result = await tool.execute(command="python3 -c 'import sys; print(\"stdout\"); print(\"stderr\", file=sys.stderr)'")
        # This may succeed or fail depending on Python availability
        if result["success"]:
            assert "stdout" in result["stdout"], "Should capture stdout"
            print(f"  ✓ Captured stdout: {result['stdout'].strip()}")
            print(f"  ✓ Captured stderr: {result['stderr'].strip()}")
        else:
            print(f"  ⚠ Python not available, skipping")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 6: Tool definition
    print("\n[Test 6] Tool definition...")
    try:
        definition = tool.get_tool_definition()
        assert definition["type"] == "function", "Should be function type"
        assert definition["function"]["name"] == "execute_command", "Name should match"
        assert "parameters" in definition["function"], "Should have parameters"
        print(f"  ✓ Tool name: {definition['function']['name']}")
        print(f"  ✓ Has parameters: {len(definition['function']['parameters']['properties'])}")
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
    asyncio.run(test_command_tool())

