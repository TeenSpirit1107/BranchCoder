#!/usr/bin/env python3
"""
Search Replace Tool - Replace code blocks by content matching
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from utils.logger import Logger
from tools.base_tool import MCPTool

logger = Logger('search_replace_tool', log_to_file=False)


class SearchReplaceTool(MCPTool):
    """Tool for replacing code blocks by content matching (no line numbers needed)."""
    
    def __init__(self):
        """Initialize search replace tool."""
        self.workspace_dir: Optional[str] = None
    
    def set_workspace_dir(self, workspace_dir: str):
        """
        Set the workspace directory.
        
        Args:
            workspace_dir: Path to workspace directory
        """
        if self.workspace_dir == workspace_dir:
            return
        
        self.workspace_dir = workspace_dir
        logger.info(f"Setting workspace directory for search_replace tool: {workspace_dir}")
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "search_replace"
    
    @property
    def agent_tool(self) -> bool:
        """This tool should be exposed to LLM agent."""
        return True
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": "search_replace",
                "description": "Replace code blocks in files by matching content (not line numbers). More reliable than patch tool because it doesn't depend on line numbers. Use this when you need to replace code blocks. Provide enough context in old_string to ensure unique matching.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Target file path. Can be absolute (e.g., /home/user/file.py) or relative to workspace directory (e.g., src/main.py)."
                        },
                        "old_string": {
                            "type": "string",
                            "description": "The code block to find and replace. Should include enough context (function signature, comments, surrounding code) to ensure unique matching. Use exact whitespace and formatting."
                        },
                        "new_string": {
                            "type": "string",
                            "description": "The replacement code block. Should match the formatting style of the file."
                        },
                        "count": {
                            "type": "integer",
                            "description": "Maximum number of replacements to make. If not specified, replaces all matches. If multiple matches found and count=1, will fail to ensure safety.",
                            "default": 1
                        }
                    },
                    "required": ["file_path", "old_string", "new_string"]
                }
            }
        }
    
    def get_call_notification(self, tool_args: Dict[str, Any]) -> Optional[str]:
        """Get custom notification for search_replace tool call."""
        file_path = tool_args.get("file_path", "")
        old_preview = tool_args.get("old_string", "")[:50]
        new_preview = tool_args.get("new_string", "")[:50]
        return f"正在替换代码块: {file_path}\n旧代码: {old_preview}...\n新代码: {new_preview}..."
    
    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[str]:
        """Get custom notification for search_replace tool result."""
        success = tool_result.get("success", False)
        replacements = tool_result.get("replacements", 0)
        
        if success:
            return f"✅ 替换成功 ({replacements} 处)"
        else:
            error = tool_result.get("error", "未知错误")
            return f"❌ 替换失败: {error}"
    
    def _find_all_matches(self, content: str, old_string: str) -> list:
        """
        Find all occurrences of old_string in content.
        
        Args:
            content: File content
            old_string: String to find
        
        Returns:
            List of (start_index, end_index) tuples
        """
        matches = []
        start = 0
        
        while True:
            index = content.find(old_string, start)
            if index == -1:
                break
            matches.append((index, index + len(old_string)))
            start = index + 1
        
        return matches
    
    def _get_line_number(self, content: str, position: int) -> int:
        """Get line number for a character position."""
        return content[:position].count('\n') + 1
    
    async def execute(
        self, 
        file_path: str, 
        old_string: str, 
        new_string: str,
        count: int = 1
    ) -> Dict[str, Any]:
        """
        Replace code blocks by content matching.
        
        Args:
            file_path: Path to the file to modify
            old_string: Code block to find and replace
            new_string: Replacement code block
            count: Maximum number of replacements (default: 1)
        
        Returns:
            Dictionary with execution results
        """
        logger.info("=" * 80)
        logger.info(f"Execute search_replace tool")
        logger.info(f"File path: {file_path}")
        logger.info(f"Old string length: {len(old_string)}")
        logger.info(f"New string length: {len(new_string)}")
        logger.info(f"Max replacements: {count}")
        
        # Resolve file path
        if not os.path.isabs(file_path):
            if self.workspace_dir:
                original_path = file_path
                file_path = os.path.join(self.workspace_dir, file_path)
                logger.info(f"Resolved relative path: '{original_path}' -> '{file_path}'")
            else:
                logger.error(f"file_path must be absolute or workspace_dir must be set")
                return {
                    "success": False,
                    "error": f"路径错误: 必须提供绝对路径或设置工作区目录\n收到路径: {file_path}",
                    "suggestion": "请使用绝对路径或确保工作区目录已设置"
                }
        
        resolved_path = Path(file_path).resolve()
        logger.info(f"Resolved file path: {resolved_path}")
        
        # Check if file exists
        if not resolved_path.exists():
            logger.error(f"File does not exist: {resolved_path}")
            return {
                "success": False,
                "error": f"文件不存在: {resolved_path}",
                "file_path": str(resolved_path)
            }
        
        try:
            # Read file content
            logger.debug(f"Reading file content from: {resolved_path}")
            with open(resolved_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.debug(f"File has {len(content)} characters, {content.count(chr(10))} lines")
            
            # Find all matches
            matches = self._find_all_matches(content, old_string)
            logger.info(f"Found {len(matches)} match(es) for old_string")
            
            if len(matches) == 0:
                logger.error("No matches found for old_string")
                
                # Try to provide helpful debugging info
                # Check if there are similar strings (fuzzy match)
                old_lines = old_string.split('\n')
                content_lines = content.split('\n')
                
                # Find lines that partially match
                similar_lines = []
                for i, old_line in enumerate(old_lines[:5]):  # Check first 5 lines
                    if old_line.strip():
                        for j, content_line in enumerate(content_lines):
                            if old_line.strip() in content_line or content_line.strip() in old_line:
                                similar_lines.append((j + 1, content_line[:80]))
                                if len(similar_lines) >= 3:
                                    break
                
                error_msg = f"未找到匹配的代码块"
                if similar_lines:
                    error_msg += f"\n💡 提示: 在文件中找到相似的行:\n"
                    for line_num, line_content in similar_lines:
                        error_msg += f"  第 {line_num} 行: {line_content}...\n"
                error_msg += f"\n请检查:\n"
                error_msg += f"  1. old_string 是否包含足够的上下文（函数签名、注释等）\n"
                error_msg += f"  2. 空白字符和格式是否完全匹配\n"
                error_msg += f"  3. 文件内容是否已更改"
                
                return {
                    "success": False,
                    "error": error_msg,
                    "file_path": str(resolved_path),
                    "matches_found": 0,
                    "similar_lines": similar_lines[:5] if similar_lines else None
                }
            
            # Safety check: if count=1 and multiple matches, fail
            if count == 1 and len(matches) > 1:
                logger.error(f"Multiple matches found ({len(matches)}) but count=1")
                match_locations = [
                    self._get_line_number(content, start) 
                    for start, _ in matches
                ]
                
                return {
                    "success": False,
                    "error": f"找到 {len(matches)} 处匹配，但只允许替换 1 处。为确保安全，请提供更多上下文使 old_string 唯一匹配。",
                    "file_path": str(resolved_path),
                    "matches_found": len(matches),
                    "match_locations": match_locations,
                    "suggestion": "在 old_string 中包含更多上下文（如函数签名、类名、注释等）以确保唯一匹配"
                }
            
            # Perform replacements
            replacements = 0
            result_content = content
            last_end = 0
            
            # Replace from end to start to preserve indices
            for start, end in reversed(matches[:count]):
                if replacements >= count:
                    break
                
                result_content = (
                    result_content[:start] + 
                    new_string + 
                    result_content[end:]
                )
                replacements += 1
                line_num = self._get_line_number(content, start)
                logger.info(f"Replacement {replacements}: at position {start} (line {line_num})")
            
            # Write back to file
            logger.info(f"Writing modified content to: {resolved_path}")
            with open(resolved_path, 'w', encoding='utf-8') as f:
                f.write(result_content)
            
            logger.info(f"Search_replace completed successfully: {replacements} replacement(s)")
            logger.info("=" * 80)
            
            return {
                "success": True,
                "file_path": str(resolved_path),
                "replacements": replacements,
                "matches_found": len(matches),
                "message": f"成功替换 {replacements} 处"
            }
            
        except Exception as e:
            logger.error(f"Error in search_replace: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "file_path": str(resolved_path)
            }

