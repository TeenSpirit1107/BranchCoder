#!/usr/bin/env python3
"""
Flow Agent - Main agentic flow processor
Handles tool calls and orchestrates the conversation with LLM and tools.
"""

import json
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from utils.logger import Logger
from utils.apply_patch import ApplyPatch
from llm.chat_llm import AsyncChatClientWrapper
from tools.register import get_tool_definitions, get_tool, execute_tool_async

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
        
        # Set workspace directory for tools that support it
        if workspace_dir:
            # Initialize patch utility
            self.patch_util = ApplyPatch(workspace_dir=workspace_dir)

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
            Dict with message type and content:
            - {"type": "status", "content": "..."} - Status updates
            - {"type": "tool_call", "tool_name": "...", "content": "..."} - Tool call notifications
            - {"type": "tool_result", "tool_name": "...", "content": "..."} - Tool result summaries
            - {"type": "message", "content": "..."} - Final message (signals end)
        """
        logger.debug(f"Processing {len(messages)} messages through flow agent")
        
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
            yield {"type": "status", "content": f"思考中... (迭代 {iteration})"}
            
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
                
                # Yield tool call notification
                tool_display_name = tool_name.replace("_", " ").title()
                yield {
                    "type": "tool_call",
                    "tool_name": tool_name,
                    "content": f"正在调用工具: {tool_display_name}..."
                }
                
                # Execute the tool
                tool_result = await self._execute_tool(tool_name, tool_args)
                
                # Yield tool result summary
                success = tool_result.get("success", False)
                result_summary = f"工具 {tool_name} 执行{'成功' if success else '失败'}"
                if not success and "error" in tool_result:
                    result_summary += f": {tool_result.get('error', '')}"
                yield {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "content": result_summary
                }
                
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
                    
                    # Yield final message with patch application result
                    yield {"type": "message", "content": patch_result}
                    return
                elif response_type == "MESSAGE":
                    # Handle message response - send to frontend
                    logger.info("Detected MESSAGE type response")
                    
                    # Yield final message and return
                    yield {"type": "message", "content": content}
                    return
                else:
                    # No type marker found - treat as message but log warning
                    logger.warning("Response without type marker, treating as MESSAGE")
                    yield {"type": "message", "content": response}
                    return
        
        # If we hit max iterations, return error message
        logger.warning(f"Reached max iterations ({max_iterations}), returning error message")
        error_message = "抱歉，处理请求时遇到问题：已达到最大迭代次数。"
        yield {"type": "message", "content": error_message}
    
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
    
    async def _apply_patch_from_response(self, patch_content: str) -> str:
        """
        Apply patch from response content.
        
        Args:
            patch_content: The patch content to apply
        
        Returns:
            Message with patch application results
        """
        logger.info("Applying patch from response")
        
        # Apply the patch
        try:
            result = await self.patch_util.apply(patch_content=patch_content)
            
            if result.get("success", False):
                applied_count = result.get("patches_applied", 0)
                total_count = result.get("patches_total", 0)
                logger.info(f"Successfully applied {applied_count}/{total_count} patches")
                
                # Build success message
                message = f"[自动应用补丁成功] 已成功应用 {applied_count}/{total_count} 个补丁。\n\n"
                
                # Add details about each patch
                results = result.get("results", [])
                for i, patch_result in enumerate(results, 1):
                    if patch_result.get("success"):
                        file_path = patch_result.get("file_path", "unknown")
                        message += f"- 补丁 {i}: 已应用到 {file_path}\n"
                    else:
                        error = patch_result.get("error", "unknown error")
                        message += f"- 补丁 {i}: 应用失败 - {error}\n"
                
                return message.strip()
            else:
                error = result.get("error", "unknown error")
                logger.warning(f"Failed to apply patch: {error}")
                return f"[自动应用补丁失败] {error}"
        except Exception as e:
            logger.error(f"Error applying patch: {e}", exc_info=True)
            return f"[自动应用补丁出错] {str(e)}"
    
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
    

