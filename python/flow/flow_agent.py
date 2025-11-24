#!/usr/bin/env python3
"""
Flow Agent - Main agentic flow processor
Handles tool calls and orchestrates the conversation with LLM and tools.
"""

import json
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from utils.logger import Logger
from llm.chat_llm import AsyncChatClientWrapper
from tools.register import get_tool_definitions, get_tool, execute_tool_async
from model import StatusMessage, ToolCallMessage, ToolResultMessage, FinalMessage

logger = Logger('flow_agent', log_to_file=False)


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
        
        logger.info(f"Flow agent initialized with {len(self.tools)} tools: {[t['function']['name'] for t in self.tools]}")
    
    async def generate_system_prompt(self, workspace_dir: Optional[str] = None) -> str:
        """
        Generate system prompt with workspace directory, current time, and workspace structure.
        This method will fetch the workspace structure each time it's called.
        
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

IMPORTANT: When you provide a final response (not a tool call), you MUST mark it with one of two types:
1. [TYPE: PATCH] - Use this when your response contains a unified diff patch that should be automatically applied to files.
   Format: Start your response with "[TYPE: PATCH]" followed by a newline, then provide the patch content.
   Example:
   [TYPE: PATCH]
   --- a/file.py
   +++ b/file.py
   @@ -1,3 +1,3 @@
   ...

2. [TYPE: MESSAGE] - Use this for all other responses (explanations, summaries, reports, etc.) that should be displayed to the user.
   Format: Start your response with "[TYPE: MESSAGE]" followed by a newline, then provide your message content.
   Example:
   [TYPE: MESSAGE]
   I've completed the task. Here's what I did...

You can call tools multiple times to complete tasks. When you're ready to provide your final response, use one of the above markers.

Current Information:
- Current Time: {current_time}"""
        
        if workspace_dir:
            prompt += f"\n- Workspace Directory: {workspace_dir}"
            
            # Get workspace structure if workspace_dir is available
            workspace_structure = None
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
            
            if workspace_structure:
                prompt += f"\n\nWorkspace File Structure:\n{workspace_structure}"
        
        return prompt.format(current_time=current_time)
    
    async def process(self, messages: List[Dict[str, str]], workspace_dir: Optional[str] = None):
        """
        Process messages through the flow agent with tool support.
        This is an async generator that yields intermediate messages for streaming to frontend.
        
        Args:
            messages: List of conversation messages (history + current message)
            workspace_dir: Optional workspace directory (used for RAG tool initialization and system prompt)
        
        Yields:
            Message objects (StatusMessage, ToolCallMessage, ToolResultMessage, FinalMessage) or dicts.
            The caller is responsible for converting these to dictionaries for JSON serialization.
            Message types:
            - StatusMessage(type="status", content="...") - Status updates
            - ToolCallMessage(type="tool_call", tool_name="...", content="...") - Tool call notifications
            - ToolResultMessage(type="tool_result", tool_name="...", content="...") - Tool result summaries
            - FinalMessage(type="message", content="...") - Final message (signals end)
        """
        logger.debug(f"Processing {len(messages)} messages through flow agent")
        
        # Update workspace directory for tools if provided
        if workspace_dir:
            # Set workspace directory for Apply Patch tool
            patch_tool = get_tool("apply_patch")
            if patch_tool and hasattr(patch_tool, 'set_workspace_dir'):
                patch_tool.set_workspace_dir(workspace_dir)
            
            # Set workspace directory for RAG tool
            rag_tool = get_tool("workspace_rag_retrieve")
            if rag_tool and hasattr(rag_tool, 'set_workspace_dir'):
                rag_tool.set_workspace_dir(workspace_dir)
            
            # Set workspace directory for Command tool
            command_tool = get_tool("execute_command")
            if command_tool and hasattr(command_tool, 'set_workspace_dir'):
                command_tool.set_workspace_dir(workspace_dir)
            
            # Set workspace directory for Workspace Structure tool
            structure_tool = get_tool("get_workspace_structure")
            if structure_tool and hasattr(structure_tool, 'set_workspace_dir'):
                structure_tool.set_workspace_dir(workspace_dir)
        
        # Generate system prompt (includes workspace_dir, current time, and workspace structure)
        system_prompt = await self.generate_system_prompt(workspace_dir=workspace_dir)
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
            
            # Yield status update
            yield StatusMessage(content=f"思考中... (迭代 {iteration})")
            
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
                
                # Get tool instance for custom notifications
                tool = get_tool(tool_name)
                
                # Yield tool call notification
                notification = tool.get_call_notification(tool_args)
                if notification is not None:
                    yield notification
                
                # Execute the tool
                tool_result = await self._execute_tool(tool_name, tool_args)
                
                # Yield tool result summary
                result_notification = tool.get_result_notification(tool_result)
                if result_notification is not None:
                    yield result_notification
                
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
                # Got a response without tool call - check for type markers
                response = result.get("answer", "") or ""
                logger.info(f"Response generated without tool call (length: {len(response)})")
                
                # Parse response type and content
                response_type, content = self._parse_response_type(response)
                
                if response_type == "PATCH":
                    # Handle patch response
                    logger.info("Detected PATCH type response")
                    
                    # Apply the patch
                    patch_result = await self._apply_patch_from_response(content)
                    
                    if patch_result.get("success", False):
                        # Success - yield message and return
                        yield FinalMessage(
                            content=f"[自动应用补丁成功]\n\n{patch_result['message']}"
                        )
                        return
                    else:
                        # Failed - add error to conversation and continue loop
                        error = patch_result.get("error", "unknown error")
                        logger.warning(f"Patch application failed: {error}")
                        
                        # Add assistant's patch attempt and error to conversation
                        messages_with_system.append({
                            "role": "assistant",
                            "content": response
                        })
                        messages_with_system.append({
                            "role": "user",
                            "content": f"补丁应用失败：{error}\n\n请检查补丁内容并重新生成正确的补丁。"
                        })
                        
                        # Continue loop to get LLM response with error feedback
                        continue
                elif response_type == "MESSAGE":
                    # Handle message response - send to frontend
                    logger.info("Detected MESSAGE type response")
                    
                    # Yield final message and return
                    yield FinalMessage(content=content)
                    return
                else:
                    # No type marker found - treat as message but log warning
                    logger.warning("Response without type marker, treating as MESSAGE")
                    yield FinalMessage(content=response)
                    return
        
        # If we hit max iterations, return error message
        logger.warning(f"Reached max iterations ({max_iterations}), returning error message")
        error_message = "抱歉，处理请求时遇到问题：已达到最大迭代次数。"
        yield FinalMessage(content=error_message)
    
    def _parse_response_type(self, response: str) -> Tuple[Optional[str], str]:
        """
        Parse response type marker and extract content.
        
        Args:
            response: The LLM response text
        
        Returns:
            Tuple of (response_type, content) where:
            - response_type: "PATCH", "MESSAGE", or None if no marker found
            - content: The content after the marker
        """
        response = response.strip()
        
        # Check for [TYPE: PATCH] marker
        if response.startswith("[TYPE: PATCH]"):
            content = response[len("[TYPE: PATCH]"):].strip()
            # Remove leading newline if present
            if content.startswith("\n"):
                content = content[1:]
            return "PATCH", content
        
        # Check for [TYPE: MESSAGE] marker
        if response.startswith("[TYPE: MESSAGE]"):
            content = response[len("[TYPE: MESSAGE]"):].strip()
            # Remove leading newline if present
            if content.startswith("\n"):
                content = content[1:]
            return "MESSAGE", content
        
        # No marker found
        return None, response
    
    async def _apply_patch_from_response(self, patch_content: str) -> Dict[str, Any]:
        """
        Apply patch from response content.
        
        Args:
            patch_content: The patch content to apply
        
        Returns:
            Dictionary with:
            - success: bool - Whether patch was applied successfully
            - message: str - Success message (if successful)
            - error: str - Error message (if failed)
            - details: List - Details about each patch (if successful)
        """
        logger.info("Applying patch from response")
        
        try:
            # Use apply_patch tool from registry
            result = await execute_tool_async("apply_patch", patch_content=patch_content)
            
            if result.get("success", False):
                applied_count = result.get("patches_applied", 0)
                total_count = result.get("patches_total", 0)
                logger.info(f"Successfully applied {applied_count}/{total_count} patches")
                
                # Build success message
                message = f"已成功应用 {applied_count}/{total_count} 个补丁。\n\n"
                
                # Add details about each patch
                details = []
                results = result.get("results", [])
                for i, patch_result in enumerate(results, 1):
                    if patch_result.get("success"):
                        file_path = patch_result.get("file_path", "unknown")
                        details.append(f"- 补丁 {i}: 已应用到 {file_path}")
                    else:
                        error = patch_result.get("error", "unknown error")
                        details.append(f"- 补丁 {i}: 应用失败 - {error}")
                
                message += "\n".join(details)
                
                return {
                    "success": True,
                    "message": message,
                    "details": details
                }
            else:
                error = result.get("error", "unknown error")
                logger.warning(f"Failed to apply patch: {error}")
                return {
                    "success": False,
                    "error": error
                }
        except Exception as e:
            logger.error(f"Error applying patch: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
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
    

