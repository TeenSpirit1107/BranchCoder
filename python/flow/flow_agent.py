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

def _generate_system_prompt(workspace_dir: Optional[str] = None, workspace_structure: Optional[str] = None) -> str:
    """
    Generate system prompt with workspace directory, current time, and workspace structure.
    
    Args:
        workspace_dir: Optional workspace directory path
        workspace_structure: Optional workspace file structure tree
    
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
    
    if workspace_structure:
        prompt += f"\n\nWorkspace File Structure:\n{workspace_structure}"
    
    return prompt.format(current_time=current_time)


class FlowAgent:
    """Main flow agent that orchestrates LLM interactions with tools."""
    
    def __init__(self, workspace_dir: Optional[str] = None):
        """
        Initialize the flow agent with LLM client and tools.
        
        Args:
            workspace_dir: Optional workspace directory (used for RAG tool initialization)
        """
        try:
            self.llm_client = AsyncChatClientWrapper()
            logger.info("LLM client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}", exc_info=True)
            raise
        
        # Get all registered tools (automatically registered via tools.register)
        self.tools = get_tool_definitions()
        
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
            
            # Set workspace directory for Apply Patch tool
            patch_tool = get_tool("apply_patch")
            if patch_tool and hasattr(patch_tool, 'set_workspace_dir'):
                patch_tool.set_workspace_dir(workspace_dir)
            
            # Set workspace directory for Workspace Structure tool
            structure_tool = get_tool("get_workspace_structure")
            if structure_tool and hasattr(structure_tool, 'set_workspace_dir'):
                structure_tool.set_workspace_dir(workspace_dir)
        
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
        
        # Get workspace structure if workspace_dir is available
        workspace_structure = None
        if workspace_dir:
            try:
                structure_tool = get_tool("get_workspace_structure")
                if structure_tool:
                    # Set workspace directory if not already set
                    if hasattr(structure_tool, 'set_workspace_dir'):
                        structure_tool.set_workspace_dir(workspace_dir)
                    
                    # Get workspace structure (with reasonable defaults)
                    structure_result = await execute_tool_async(
                        "get_workspace_structure",
                        max_depth=5,
                        include_files=True,
                        include_hidden=False
                    )
                    
                    if structure_result.get("success") and "structure" in structure_result:
                        workspace_structure = structure_result["structure"]
                        logger.debug(f"Retrieved workspace structure ({structure_result.get('file_count', 0)} files, {structure_result.get('directory_count', 0)} directories)")
            except Exception as e:
                logger.warning(f"Failed to get workspace structure: {e}", exc_info=True)
                # Continue without structure if it fails
        
        # Add system prompt to messages (includes workspace_dir, current time, and workspace structure)
        system_prompt = _generate_system_prompt(
            workspace_dir=workspace_dir,
            workspace_structure=workspace_structure
        )
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
                
                # Check if response contains a patch and auto-apply it
                response = await self._auto_apply_patch_if_needed(response, workspace_dir)
                
                return response
        
        # If we hit max iterations, return the last response
        logger.warning(f"Reached max iterations ({max_iterations}), returning last response")
        final_response = result.get("answer", "I apologize, but I encountered an issue processing your request.")
        
        # Check if response contains a patch and auto-apply it
        final_response = await self._auto_apply_patch_if_needed(final_response, workspace_dir)
        
        return final_response
    
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
    
    def _detect_patch_in_response(self, response: str) -> Optional[str]:
        """
        Detect if the response contains a unified diff patch.
        
        Args:
            response: The LLM response text
        
        Returns:
            Patch content if detected, None otherwise
        """
        # Look for unified diff format: starts with --- and +++
        lines = response.split('\n')
        
        # Find potential patch start
        for i, line in enumerate(lines):
            if line.strip().startswith('---'):
                # Check if next line starts with +++
                if i + 1 < len(lines) and lines[i + 1].strip().startswith('+++'):
                    # Found patch start, extract the patch
                    # Look for the end of the patch (next --- or end of response)
                    patch_lines = [lines[i]]
                    j = i + 1
                    while j < len(lines):
                        # Stop if we find another patch header (but not the first one)
                        if j > i + 1 and lines[j].strip().startswith('---'):
                            break
                        patch_lines.append(lines[j])
                        j += 1
                    
                    patch_content = '\n'.join(patch_lines)
                    logger.info("Detected patch in LLM response")
                    return patch_content
        
        return None
    
    async def _auto_apply_patch_if_needed(self, response: str, workspace_dir: Optional[str] = None) -> str:
        """
        Automatically detect and apply patches in the LLM response.
        
        Args:
            response: The LLM response text
            workspace_dir: Optional workspace directory
        
        Returns:
            Modified response with patch application results appended
        """
        patch_content = self._detect_patch_in_response(response)
        
        if patch_content:
            logger.info("Auto-applying detected patch")
            
            # Get apply_patch tool
            patch_tool = get_tool("apply_patch")
            if patch_tool:
                # Set workspace directory if available
                if workspace_dir and hasattr(patch_tool, 'set_workspace_dir'):
                    patch_tool.set_workspace_dir(workspace_dir)
                
                # Apply the patch
                try:
                    result = await execute_tool_async("apply_patch", patch_content=patch_content)
                    
                    if result.get("success", False):
                        applied_count = result.get("patches_applied", 0)
                        total_count = result.get("patches_total", 0)
                        logger.info(f"Successfully applied {applied_count}/{total_count} patches")
                        
                        # Append success message to response
                        response += f"\n\n[自动应用补丁成功] 已成功应用 {applied_count}/{total_count} 个补丁。"
                        
                        # Add details about each patch
                        results = result.get("results", [])
                        for i, patch_result in enumerate(results, 1):
                            if patch_result.get("success"):
                                file_path = patch_result.get("file_path", "unknown")
                                response += f"\n- 补丁 {i}: 已应用到 {file_path}"
                            else:
                                error = patch_result.get("error", "unknown error")
                                response += f"\n- 补丁 {i}: 应用失败 - {error}"
                    else:
                        error = result.get("error", "unknown error")
                        logger.warning(f"Failed to apply patch: {error}")
                        response += f"\n\n[自动应用补丁失败] {error}"
                except Exception as e:
                    logger.error(f"Error auto-applying patch: {e}", exc_info=True)
                    response += f"\n\n[自动应用补丁出错] {str(e)}"
            else:
                logger.warning("apply_patch tool not found")
                response += "\n\n[警告] 检测到补丁但无法应用（apply_patch 工具未找到）"
        
        return response

