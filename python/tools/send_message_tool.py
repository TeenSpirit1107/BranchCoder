#!/usr/bin/env python3
"""
Send Message Tool - Send final message to user
"""

from typing import Dict, Any, Optional
from utils.logger import Logger
from tools.base_tool import MCPTool
from models import ToolCallEvent, ToolResultEvent

logger = Logger('send_message_tool', log_to_file=False)


class SendMessageTool(MCPTool):
    """Tool for sending final messages to the user."""
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "send_message"
    
    @property
    def agent_tool(self) -> bool:
        """This tool should be exposed to LLM agent for sending final messages."""
        return True
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": "send_message",
                "description": "Send a final message to the user. Use this tool when you want to provide your final response, explanation, summary, or any message to the user. This should be called when you have completed your task and want to communicate the result to the user.",
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
        Get custom notification for send message tool call.
        
        Args:
            tool_args: Tool arguments containing 'message'
        
        Returns:
            Custom notification message string (None to skip notification)
        """
        # Don't show notification for message sending, it's the final response
        return None
    
    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[str]:
        """
        Get custom notification for send message tool result.
        
        Args:
            tool_result: Tool execution result
        
        Returns:
            Custom notification message string (None to skip notification)
        """
        # Don't show notification for message result, it's the final response
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

