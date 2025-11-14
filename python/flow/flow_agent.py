#!/usr/bin/env python3
"""
Flow Agent - Main agentic flow processor
Handles tool calls and orchestrates the conversation with LLM and tools.
"""

import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from utils.logger import Logger
from llm.chat_llm import AsyncChatClientWrapper
from tools.register import get_tool_definitions, get_tool, execute_tool_async

logger = Logger('flow_agent', log_to_file=False)

def _generate_system_prompt(workspace_dir: Optional[str] = None) -> str:
    """
    Generate system prompt with workspace directory and current time.
    
    Args:
        workspace_dir: Optional workspace directory path
    
    Returns:
        System prompt string
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    prompt = """You are a helpful AI coding assistant integrated into VS Code. 
Your role is to assist developers with:
- Writing and debugging code
- Explaining code functionality
- Suggesting improvements and best practices
- Answering programming questions
- Helping with code refactoring

You have access to various tools that will be provided to you. Use them when appropriate to help the user. 
Provide clear, concise, and accurate responses.

Current Information:
- Current Time: {current_time}"""
    
    if workspace_dir:
        prompt += f"\n- Workspace Directory: {workspace_dir}"
    
    return prompt.format(current_time=current_time)


class FlowAgent:
    """Main flow agent that orchestrates LLM interactions with tools."""
    
    def __init__(self):
        """Initialize the flow agent with LLM client and tools."""
        try:
            self.llm_client = AsyncChatClientWrapper()
            logger.info("LLM client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}", exc_info=True)
            raise
        
        # Get all registered tools (automatically registered via tools.register)
        self.tools = get_tool_definitions()
        
        logger.info(f"Flow agent initialized with {len(self.tools)} tools: {[t['function']['name'] for t in self.tools]}")
    
    async def process(self, messages: List[Dict[str, str]], workspace_dir: Optional[str] = None) -> str:
        """
        Process messages through the flow agent with tool support.
        
        Args:
            messages: List of conversation messages (history + current message)
            workspace_dir: Optional workspace directory (used for RAG tool initialization and system prompt)
        
        Returns:
            Final response string
        """
        logger.debug(f"Processing {len(messages)} messages through flow agent")
        
        # Set workspace directory for tools that support it
        if workspace_dir:
            # Set workspace directory for RAG tool
            rag_tool = get_tool("workspace_rag_retrieve")
            if rag_tool and hasattr(rag_tool, 'set_workspace_dir'):
                rag_tool.set_workspace_dir(workspace_dir)
            
            # Set workspace directory for Command tool
            command_tool = get_tool("execute_command")
            if command_tool and hasattr(command_tool, 'set_workspace_dir'):
                command_tool.set_workspace_dir(workspace_dir)
        
        # Add system prompt to messages (includes workspace_dir and current time)
        system_prompt = _generate_system_prompt(workspace_dir=workspace_dir)
        messages_with_system = [
            {"role": "system", "content": system_prompt},
            *messages
        ]
        
        # Maximum iterations to prevent infinite loops
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"Flow iteration {iteration}")
            
            # Call LLM with tools
            result = await self.llm_client.ask(
                messages=messages_with_system,
                tools=self.tools,
            )
            
            # Handle tool calls
            if result["type"] == "tool_call":
                tool_name = result["tool_name"]
                tool_args = result["tool_args"] or {}
                
                logger.info(f"Tool call: {tool_name} with args: {tool_args}")
                
                # Execute the tool
                tool_result = await self._execute_tool(tool_name, tool_args)
                
                # Add tool result to conversation
                messages_with_system.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": f"call_{iteration}",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_args)
                        }
                    }]
                })
                messages_with_system.append({
                    "role": "tool",
                    "content": json.dumps(tool_result),
                    "tool_call_id": f"call_{iteration}"
                })
                
                # Continue loop to get LLM response with tool results
                continue
            else:
                # Got a final answer
                response = result.get("answer", "") or ""
                logger.info(f"Final response generated (length: {len(response)})")
                return response
        
        # If we hit max iterations, return the last response
        logger.warning(f"Reached max iterations ({max_iterations}), returning last response")
        return result.get("answer", "I apologize, but I encountered an issue processing your request.")
    
    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool by name using the tool registry.
        
        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments for the tool
        
        Returns:
            Tool execution result
        """
        try:
            # Get tool from registry
            tool = get_tool(tool_name)
            if tool is None:
                logger.error(f"Unknown tool: {tool_name}")
                return {"error": f"Unknown tool: {tool_name}"}
            
            # Execute the tool
            return await execute_tool_async(tool_name, **tool_args)
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {"error": f"Tool execution failed: {str(e)}"}

