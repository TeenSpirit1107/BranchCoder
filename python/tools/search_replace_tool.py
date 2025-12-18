#!/usr/bin/env python3
"""
Search Replace Tool - Performs exact string replacements in files
"""

import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from utils.logger import Logger
from tools.base_tool import MCPTool

# Verbose logging flag: if True, log full file content on matching errors
VERBOSE = True

logger = Logger('search_replace_tool', log_to_file=False)


class SearchReplaceTool(MCPTool):
    """Tool for performing exact string replacements in files."""
    
    # Class-level dictionary to store file locks (shared across all instances)
    _file_locks: Dict[str, asyncio.Lock] = {}
    _locks_lock: Optional[asyncio.Lock] = None  # Lock to protect the _file_locks dictionary
    
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
                "description": "Performs exact string replacements in files.\n\nUsage:\n- When editing text, ensure you preserve the exact indentation (tabs/spaces) as it appears before.\n- ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.\n- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.\n- The edit will FAIL if old_string is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use replace_all to change every instance of old_string.\n- Use replace_all for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance.\n- To create or overwrite a file, you should prefer the write tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path to the file to modify. Always specify the target file as the first argument. You can use either a relative path in the workspace or an absolute path."
                        },
                        "old_string": {
                            "type": "string",
                            "description": "The text to replace"
                        },
                        "new_string": {
                            "type": "string",
                            "description": "The text to replace it with (must be different from old_string)"
                        },
                        "replace_all": {
                            "type": "boolean",
                            "description": "Replace all occurences of old_string (default false)"
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
        replace_all = tool_args.get("replace_all", False)
        mode = "all occurrences" if replace_all else "first occurrence"
        return f"Replacing string in {file_path} ({mode})\nOld: {old_preview}...\nNew: {new_preview}..."
    
    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[str]:
        """Get custom notification for search_replace tool result."""
        success = tool_result.get("success", False)
        
        if success:
            replacements_count = tool_result.get("replacements_count", 0)
            return f"✅ Replacement successful ({replacements_count} occurrence(s) replaced)"
        else:
            error = tool_result.get("error", "Unknown error")
            return f"❌ Replacement failed: {error}"
    
    def _normalize_line_endings(self, text: str) -> str:
        """
        Normalize line endings to \n (Unix style).
        Handles \r\n (Windows), \r (old Mac), and \n (Unix).
        
        Args:
            text: Text with potentially mixed line endings
        
        Returns:
            Text with normalized line endings
        """
        # Replace \r\n with \n first, then replace remaining \r with \n
        return text.replace('\r\n', '\n').replace('\r', '\n')
    
    def _format_string_for_log(self, text: str, max_length: int = 500) -> str:
        """
        Format a string for logging purposes.
        If the string is short, show it fully. If long, show preview.
        
        Args:
            text: String to format
            max_length: Maximum length to show fully
        
        Returns:
            Formatted string representation
        """
        if len(text) <= max_length:
            # Show full content using repr to display special characters
            return repr(text)
        else:
            # Show preview: first part + ... + last part
            preview_length = max_length // 2 - 10
            preview = repr(text[:preview_length]) + f"... (truncated, total {len(text)} chars) ..." + repr(text[-preview_length:])
            return preview
    
    def _find_all_matches(self, content: str, old_string: str) -> list:
        """
        Find all occurrences of old_string in content.
        Normalizes line endings before matching to handle cross-platform differences.
        
        Args:
            content: File content
            old_string: String to find
        
        Returns:
            List of (start_index, end_index) tuples
        """
        # Normalize line endings for both content and old_string
        normalized_content = self._normalize_line_endings(content)
        normalized_old_string = self._normalize_line_endings(old_string)
        
        # Find all exact matches
        matches = []
        start = 0
        
        while True:
            index = normalized_content.find(normalized_old_string, start)
            if index == -1:
                break
            matches.append((index, index + len(normalized_old_string)))
            start = index + 1
        
        return matches
    
    async def _get_file_lock(self, file_path: str) -> asyncio.Lock:
        """
        Get or create an asyncio lock for a specific file.
        
        Args:
            file_path: Absolute path to the file
            
        Returns:
            asyncio.Lock instance for the file
        """
        # Initialize _locks_lock if not already created
        if self._locks_lock is None:
            self._locks_lock = asyncio.Lock()
        
        async with self._locks_lock:
            if file_path not in self._file_locks:
                self._file_locks[file_path] = asyncio.Lock()
            return self._file_locks[file_path]
    
    async def execute(
        self, 
        file_path: str, 
        old_string: str,
        new_string: str,
        replace_all: bool = False
    ) -> Dict[str, Any]:
        """
        Perform exact string replacements in files.
        
        Args:
            file_path: Path to the file to modify
            old_string: The text to replace (must match exactly including whitespace)
            new_string: The text to replace it with (must be different from old_string)
            replace_all: If True, replace all occurrences; if False, only replace first occurrence
        
        Returns:
            Dictionary with execution results
        """
        logger.info("=" * 80)
        logger.info(f"Execute search_replace tool")
        logger.info(f"File path: {file_path}")
        logger.info(f"Old string length: {len(old_string)}")
        logger.info(f"Old string content: {self._format_string_for_log(old_string)}")
        logger.info(f"New string length: {len(new_string)}")
        logger.info(f"New string content: {self._format_string_for_log(new_string)}")
        logger.info(f"Replace all: {replace_all}")
        
        # Validate that old_string and new_string are different
        if old_string == new_string:
            logger.error("old_string and new_string are identical")
            return {
                "success": False,
                "error": "old_string and new_string must be different",
                "file_path": file_path
            }
        
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
                    "error": f"Path error: Must provide absolute path or set workspace directory\nReceived path: {file_path}",
                    "suggestion": "Please use absolute path or ensure workspace directory is set"
                }
        
        resolved_path = Path(file_path).resolve()
        logger.info(f"Resolved file path: {resolved_path}")
        
        # Check if file exists
        if not resolved_path.exists():
            logger.error(f"File does not exist: {resolved_path}")
            return {
                "success": False,
                "error": f"File does not exist: {resolved_path}",
                "file_path": str(resolved_path)
            }
        
        # Get file lock to ensure exclusive access
        file_lock = await self._get_file_lock(str(resolved_path))
        logger.info(f"Acquiring lock for file: {resolved_path}")
        
        try:
            # Acquire lock before modifying file
            async with file_lock:
                logger.info(f"Lock acquired for file: {resolved_path}")
                
                # Read file content
                logger.debug(f"Reading file content from: {resolved_path}")
                with open(resolved_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                logger.debug(f"File has {len(content)} characters")
                
                # Normalize line endings for matching (but preserve original for output)
                normalized_content = self._normalize_line_endings(content)
                normalized_old_string = self._normalize_line_endings(old_string)
                
                # Find all matches
                matches = self._find_all_matches(normalized_content, normalized_old_string)
                
                if not matches:
                    logger.error(f"old_string not found in file")
                    # Log full file content for debugging if VERBOSE is enabled
                    if VERBOSE:
                        logger.error(f"File content at time of error (full content, {len(content)} characters):")
                        logger.error("=" * 80)
                        logger.error(content)
                        logger.error("=" * 80)
                        logger.error(f"Searching for old_string (length {len(old_string)}):")
                        logger.error("=" * 80)
                        logger.error(repr(old_string))
                        logger.error("=" * 80)
                    return {
                        "success": False,
                        "error": f"old_string not found in file",
                        "file_path": str(resolved_path),
                        "suggestion": "Please check if old_string is correct and ensure it matches exactly (including whitespace, indentation, etc.)"
                    }
                
                # Check uniqueness if replace_all is False
                if not replace_all and len(matches) > 1:
                    logger.error(f"Found {len(matches)} occurrences of old_string, but replace_all is False")
                    # Log full file content for debugging if VERBOSE is enabled
                    if VERBOSE:
                        logger.error(f"File content at time of error (full content, {len(content)} characters):")
                        logger.error("=" * 80)
                        logger.error(content)
                        logger.error("=" * 80)
                    return {
                        "success": False,
                        "error": f"Found {len(matches)} occurrences of old_string. Either provide a larger string with more surrounding context to make it unique, or set replace_all=True to replace all occurrences.",
                        "file_path": str(resolved_path),
                        "matches_found": len(matches),
                        "suggestion": "Either provide more context in old_string to make it unique, or set replace_all=True"
                        }
                
                # Perform replacement(s)
                normalized_new_string = self._normalize_line_endings(new_string)
                
                if replace_all:
                    # Replace all occurrences (work backwards to preserve indices)
                    result_content = normalized_content
                    replacements_count = len(matches)
                    for start_pos, end_pos in reversed(matches):
                        result_content = result_content[:start_pos] + normalized_new_string + result_content[end_pos:]
                    logger.info(f"Replaced {replacements_count} occurrence(s)")
                else:
                    # Replace only first occurrence
                    start_pos, end_pos = matches[0]
                    result_content = normalized_content[:start_pos] + normalized_new_string + normalized_content[end_pos:]
                    replacements_count = 1
                    logger.info(f"Replaced first occurrence at position {start_pos}-{end_pos}")
                
                # Write back to file (preserve original line ending style)
                # Detect original line ending style
                if '\r\n' in content:
                    line_ending = '\r\n'
                elif '\r' in content and '\n' not in content:
                    line_ending = '\r'
                else:
                    line_ending = '\n'
                
                # Convert normalized result back to original line ending style
                if line_ending != '\n':
                    result_content = result_content.replace('\n', line_ending)
                
                logger.info(f"Writing modified content to: {resolved_path}")
                with open(resolved_path, 'w', encoding='utf-8') as f:
                    f.write(result_content)
                
                logger.info(f"Search_replace completed successfully")
                logger.info(f"Releasing lock for file: {resolved_path}")
                logger.info("=" * 80)
                
                return {
                    "success": True,
                    "file_path": str(resolved_path),
                    "replacements_count": replacements_count,
                    "message": f"Successfully replaced {replacements_count} occurrence(s)"
                }
                
        except Exception as e:
            logger.error(f"Error in search_replace: {e}", exc_info=True)
            # Try to log full file content if it was read and VERBOSE is enabled
            if VERBOSE:
                try:
                    if 'content' in locals():
                        logger.error(f"File content at time of error (full content, {len(content)} characters):")
                        logger.error("=" * 80)
                        logger.error(content)
                        logger.error("=" * 80)
                except:
                    pass  # Ignore errors when logging file content
            return {
                "success": False,
                "error": str(e),
                "file_path": str(resolved_path)
            }

