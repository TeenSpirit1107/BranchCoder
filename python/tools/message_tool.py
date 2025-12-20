#!/usr/bin/env python3
"""
Message Tool - Send intermediate messages to the user
"""

from typing import Dict, Any, Optional
from utils.logger import Logger
from tools.base_tool import MCPTool

logger = Logger('message_tool', log_to_file=False)


class MessageTool(MCPTool):
    """Tool for sending intermediate messages to the user."""
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "send_message"
    
    @property
    def agent_tool(self) -> bool:
        """This tool should not be exposed to LLM agent - use message_to_user parameter instead."""
        return False
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": "send_message",
                "description": "Send an intermediate message to the user. Use this tool when you want to communicate progress, status updates, explanations, or any information to the user during task execution. This is for intermediate messages - use send_report for final messages.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The message content to send to the user"
                        }
                    },
                    "required": ["message"]
                }
            }
        }
    
    def get_call_notification(self, tool_args: Dict[str, Any]) -> Optional[str]:
        """
        Get custom notification for message tool call.
        
        Args:
            tool_args: Tool arguments containing 'message'
        
        Returns:
            Custom notification message string (None to skip notification)
        """
        # Don't show separate notification, the message itself will be shown
        return None
    
    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[str]:
        """
        Get custom notification for message tool result.
        
        Args:
            tool_result: Tool execution result
        
        Returns:
            Custom notification message string (None to skip notification)
        """
        # Don't show separate notification, the message itself was already shown
        return None
    
    async def execute(self, message: str) -> Dict[str, Any]:
        """
        Send a message to the user.
        
        Args:
            message: The message content to send
        
        Returns:
            Dictionary with execution results
        """
        logger.info(f"Sending message to user (length: {len(message)})")
        
        return {
            "success": True,
            "message": message,
            "message_length": len(message)
        }

