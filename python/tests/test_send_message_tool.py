#!/usr/bin/env python3
"""
Test suite for SendMessageTool
Tests message sending functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.send_message_tool import SendMessageTool


async def test_send_message_tool():
    """Run comprehensive tests for SendMessageTool."""
    print("=" * 80)
    print("SendMessageTool Test Suite")
    print("=" * 80)
    
    tool = SendMessageTool()
    passed = 0
    failed = 0
    
    # Test 1: Basic message sending
    print("\n[Test 1] Basic message sending...")
    try:
        message = "Hello, this is a test message!"
        result = await tool.execute(message=message)
        assert result["success"] is True, "Message sending should succeed"
        assert result["message"] == message, "Message should match input"
        assert "message_length" in result, "Should have message_length"
        assert result["message_length"] == len(message), "Message length should match"
        print(f"  ✓ Message sent successfully")
        print(f"  ✓ Message length: {result['message_length']}")
        print(f"  ✓ Message preview: {message[:50]}...")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 2: Empty message
    print("\n[Test 2] Empty message handling...")
    try:
        result = await tool.execute(message="")
        assert result["success"] is True, "Empty message should be accepted"
        assert result["message"] == "", "Message should be empty"
        assert result["message_length"] == 0, "Message length should be 0"
        print(f"  ✓ Empty message handled correctly")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 3: Long message
    print("\n[Test 3] Long message handling...")
    try:
        long_message = "A" * 10000
        result = await tool.execute(message=long_message)
        assert result["success"] is True, "Long message should be accepted"
        assert result["message"] == long_message, "Message should match input"
        assert result["message_length"] == 10000, "Message length should be correct"
        print(f"  ✓ Long message handled correctly")
        print(f"  ✓ Message length: {result['message_length']}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 4: Message with special characters
    print("\n[Test 4] Message with special characters...")
    try:
        special_message = "Hello! @#$%^&*()_+-=[]{}|;':\",./<>?`~"
        result = await tool.execute(message=special_message)
        assert result["success"] is True, "Special characters should be accepted"
        assert result["message"] == special_message, "Message should match input"
        print(f"  ✓ Special characters handled correctly")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 5: Multiline message
    print("\n[Test 5] Multiline message handling...")
    try:
        multiline_message = "Line 1\nLine 2\nLine 3"
        result = await tool.execute(message=multiline_message)
        assert result["success"] is True, "Multiline message should be accepted"
        assert result["message"] == multiline_message, "Message should match input"
        assert result["message_length"] == len(multiline_message), "Message length should be correct"
        print(f"  ✓ Multiline message handled correctly")
        print(f"  ✓ Message length: {result['message_length']}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 6: Tool definition
    print("\n[Test 6] Tool definition...")
    try:
        definition = tool.get_tool_definition()
        assert definition["type"] == "function", "Should be function type"
        assert definition["function"]["name"] == "send_message", "Name should match"
        assert "parameters" in definition["function"], "Should have parameters"
        assert "message" in definition["function"]["parameters"]["properties"], "Should have message parameter"
        print(f"  ✓ Tool name: {definition['function']['name']}")
        print(f"  ✓ Has parameters")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 7: Notification methods
    print("\n[Test 7] Notification methods...")
    try:
        call_notif = tool.get_call_notification({"message": "test"})
        result_notif = tool.get_result_notification({"success": True, "message": "test"})
        
        # SendMessageTool should return None for notifications (it's the final message)
        assert call_notif is None, "Call notification should be None"
        assert result_notif is None, "Result notification should be None"
        print(f"  ✓ Notification methods return None (as expected)")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed += 1
    
    # Test 8: Agent tool property
    print("\n[Test 8] Agent tool property...")
    try:
        assert tool.agent_tool is True, "Should be exposed to agent"
        print(f"  ✓ Agent tool property: {tool.agent_tool}")
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
    asyncio.run(test_send_message_tool())

