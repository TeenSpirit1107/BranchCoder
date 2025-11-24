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

    def get_call_notification(self, tool_args: Dict[str, Any]) -> Optional[str]:
        return None


    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[str]:
        return None


    def get_name(self) -> str:
        return self.name
