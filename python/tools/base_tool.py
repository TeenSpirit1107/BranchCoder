#!/usr/bin/env python3
"""
Base MCP Tool Interface
All tools should inherit from this base class to conform to MCP (Model Context Protocol) format.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class MCPTool(ABC):
    """
    Base class for MCP (Model Context Protocol) tools.
    All tools must implement this interface to be automatically registered.
    """
    
    @property
    def agent_tool(self) -> bool:
        """
        Whether this tool should be exposed to the LLM agent.
        If False, the tool will be registered but not available for LLM function calling.
        
        Returns:
            True if tool should be available to LLM, False otherwise (default: True)
        """
        return True
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Tool name - must be unique and match the function name in tool definition.
        
        Returns:
            Tool name string
        """
        pass
    
    @abstractmethod
    def get_tool_definition(self) -> Dict[str, Any]:
        """
        Get the MCP tool definition for LLM function calling.
        This should return a dictionary conforming to OpenAI function calling format.
        
        Returns:
            Dictionary with tool definition containing:
            - type: "function"
            - function: {
                - name: tool name
                - description: tool description
                - parameters: JSON schema for parameters
            }
        """
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool with given arguments.
        
        Args:
            **kwargs: Tool-specific arguments
        
        Returns:
            Dictionary with execution results
        """
        pass

    @abstractmethod
    def get_call_notification(self, tool_args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get notification to display when tool is called.
        Override this method to provide custom notification for tool calls.
        
        Args:
            tool_args: The arguments passed to the tool
        
        Returns:
            Optional dictionary or message model instance (e.g., ToolCallMessage):
            - type: "tool_call"
            - tool_name: tool name
            - content: notification message
            Can return a dict or a message model instance (e.g., ToolCallMessage).
            The caller will handle conversion to dict for serialization.
            If None is returned, flow_agent will use default notification.
        """
        return None


    @abstractmethod
    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get notification to display when tool execution completes.
        Override this method to provide custom notification for tool results.
        
        Args:
            tool_result: The result dictionary from tool execution
        
        Returns:
            Optional dictionary or message model instance (e.g., ToolResultMessage):
            - type: "tool_result"
            - tool_name: tool name
            - content: notification message
            Can return a dict or a message model instance (e.g., ToolResultMessage).
            The caller will handle conversion to dict for serialization.
            If None is returned, flow_agent will use default notification.
        """
        return None

    def get_name(self) -> str:
        """
        Get tool name (convenience method).
        
        Returns:
            Tool name
        """
        return self.name