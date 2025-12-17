#!/usr/bin/env python3
"""
Search Replace Tool - Replace code blocks by content matching
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
    """Tool for replacing code blocks by content matching (no line numbers needed)."""
    
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
                "description": "Replace code blocks in files by using start and end line content as anchors.The tool will find the range between the start_line_content and end_line_content (inclusive) and replace all lines in between with new_string.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Target file path. Can be absolute (e.g., /home/user/file.py) or relative to workspace directory (e.g., src/main.py)."
                        },
                        "start_line_content": {
                            "type": "string",
                            "description": "The content of the first line (anchor) to identify the start of the code block to replace. Should be unique enough to identify the correct location. Trailing whitespace is ignored for matching."
                        },
                        "end_line_content": {
                            "type": "string",
                            "description": "The content of the last line (anchor) to identify the end of the code block to replace. Should be unique enough to identify the correct location. Trailing whitespace is ignored for matching. If replacing only one line, set this equal to start_line_content."
                        },
                        "new_string": {
                            "type": "string",
                            "description": "The replacement code block. Should match the formatting style of the file."
                        },
                        "estimated_line_count": {
                            "type": "integer",
                            "description": "Estimated number of lines to be replaced (from start_line_content to end_line_content, inclusive). Used to disambiguate when multiple matches are found - the tool will select the match with line count closest to this estimate."
                        }
                    },
                    "required": ["file_path", "start_line_content", "end_line_content", "new_string"]
                }
            }
        }
    
    def get_call_notification(self, tool_args: Dict[str, Any]) -> Optional[str]:
        """Get custom notification for search_replace tool call."""
        file_path = tool_args.get("file_path", "")
        start_content = tool_args.get("start_line_content", "")[:50]
        end_content = tool_args.get("end_line_content", "")[:50]
        new_preview = tool_args.get("new_string", "")[:50]
        return f"Replacing code block: {file_path}\nStart line: {start_content}...\nEnd line: {end_content}...\nNew code: {new_preview}..."
    
    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[str]:
        """Get custom notification for search_replace tool result."""
        success = tool_result.get("success", False)
        
        if success:
            start_line = tool_result.get("start_line", 0)
            end_line = tool_result.get("end_line", 0)
            lines_replaced = tool_result.get("lines_replaced", 0)
            return f"✅ Replacement successful (lines {start_line}-{end_line}, {lines_replaced} lines total)"
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
    
    def _normalize_line_for_matching(self, line: str) -> str:
        """
        Normalize a line for fuzzy matching by removing trailing whitespace.
        Preserves leading whitespace (indentation) for context.
        
        Args:
            line: Line to normalize
        
        Returns:
            Normalized line
        """
        return line.rstrip()
    
    def _lines_match_fuzzy(self, line1: str, line2: str) -> bool:
        """
        Check if two lines match approximately (ignoring trailing whitespace).
        
        Args:
            line1: First line
            line2: Second line
        
        Returns:
            True if lines match approximately
        """
        return self._normalize_line_for_matching(line1) == self._normalize_line_for_matching(line2)
    
    def _find_fuzzy_matches(self, content: str, old_string: str) -> list:
        """
        Find all occurrences of old_string in content using fuzzy line-based matching.
        Matches lines approximately (ignoring trailing whitespace differences).
        Uses a more flexible matching strategy that allows skipping some non-matching lines.
        
        Args:
            content: File content
            old_string: String to find
        
        Returns:
            List of (start_index, end_index) tuples
        """
        normalized_content = self._normalize_line_endings(content)
        normalized_old_string = self._normalize_line_endings(old_string)
        
        # Split into lines
        old_lines = normalized_old_string.split('\n')
        content_lines = normalized_content.split('\n')
        
        if not old_lines:
            return []
        
        matches = []
        
        # Filter out empty lines from old_string for matching (keep track of original indices)
        non_empty_old_lines = [(i, line) for i, line in enumerate(old_lines) if line.strip()]
        
        if not non_empty_old_lines:
            # All lines are empty, can't do fuzzy matching
            return []
        
        # Use the first non-empty line as anchor
        first_non_empty_idx, first_non_empty_line = non_empty_old_lines[0]
        
        # Find all positions where the first non-empty line appears
        anchor_positions = []
        for i, content_line in enumerate(content_lines):
            if self._lines_match_fuzzy(first_non_empty_line, content_line):
                anchor_positions.append(i)
        
        logger.debug(f"Fuzzy matching: found {len(anchor_positions)} anchor position(s) for first line: {first_non_empty_line[:50]}...")
        
        # For each anchor position, try to match the pattern
        for anchor_pos in anchor_positions:
            # Calculate the start line (accounting for leading empty lines in old_string)
            start_line_idx = anchor_pos - first_non_empty_idx
            if start_line_idx < 0:
                continue
            
            # Try to match using a more flexible algorithm
            # We'll match non-empty lines in order, allowing some flexibility
            content_idx = start_line_idx
            matched_non_empty_count = 0
            matched_line_indices = []
            old_line_idx = 0
            
            # Track the range of matched lines
            min_matched_line = None
            max_matched_line = None
            
            while old_line_idx < len(old_lines):
                old_line = old_lines[old_line_idx]
                
                if not old_line.strip():
                    # Empty line in old_string: try to match empty line or skip
                    if content_idx < len(content_lines) and not content_lines[content_idx].strip():
                        # Matched empty line
                        if min_matched_line is None:
                            min_matched_line = content_idx
                        max_matched_line = content_idx
                        content_idx += 1
                    # Otherwise, just skip this empty line in old_string
                    old_line_idx += 1
                    continue
                
                # For non-empty line, try to find a match
                found_match = False
                # Allow searching ahead up to 5 lines for flexibility
                search_limit = min(content_idx + 5, len(content_lines))
                
                for search_idx in range(content_idx, search_limit):
                    if search_idx >= len(content_lines):
                        break
                    
                    content_line = content_lines[search_idx]
                    if self._lines_match_fuzzy(old_line, content_line):
                        # Found a match
                        matched_non_empty_count += 1
                        matched_line_indices.append(search_idx)
                        if min_matched_line is None:
                            min_matched_line = search_idx
                        max_matched_line = search_idx
                        content_idx = search_idx + 1
                        old_line_idx += 1
                        found_match = True
                        break
                
                if not found_match:
                    # Couldn't find this line
                    # If we haven't matched anything yet, this anchor position fails
                    if matched_non_empty_count == 0:
                        break
                    # Otherwise, skip this old_line and continue
                    old_line_idx += 1
            
            # If we matched at least 60% of non-empty lines, consider it a match
            # Also require at least 3 lines matched to avoid false positives
            match_ratio = matched_non_empty_count / len(non_empty_old_lines) if non_empty_old_lines else 0
            if match_ratio >= 0.6 and matched_non_empty_count >= 3 and min_matched_line is not None:
                logger.debug(f"Fuzzy match found: matched {matched_non_empty_count}/{len(non_empty_old_lines)} non-empty lines (ratio: {match_ratio:.2f})")
                logger.debug(f"Matched line range: {min_matched_line} to {max_matched_line}")
                
                # Calculate character positions using the matched line range
                start_line = min_matched_line
                end_line = max_matched_line
                
                # Calculate start position: sum of all characters in previous lines + newlines
                start_pos = 0
                for i in range(start_line):
                    start_pos += len(content_lines[i]) + 1  # +1 for newline
                
                # Calculate end position: include all lines from start_line to end_line
                end_pos = start_pos
                for i in range(start_line, end_line + 1):
                    end_pos += len(content_lines[i])
                    if i < end_line:  # Add newline after each line except the last
                        end_pos += 1
                
                # Verify the calculated positions
                logger.debug(f"Calculated positions: start={start_pos}, end={end_pos}")
                matches.append((start_pos, end_pos))
        
        logger.debug(f"Fuzzy matching completed: found {len(matches)} match(es)")
        return matches
    
    def _find_all_matches(self, content: str, old_string: str, fuzzy: bool = False) -> list:
        """
        Find all occurrences of old_string in content.
        Normalizes line endings before matching to handle cross-platform differences.
        
        Args:
            content: File content
            old_string: String to find
            fuzzy: If True, use fuzzy matching (approximate line matching)
        
        Returns:
            List of (start_index, end_index) tuples
        """
        # Normalize line endings for both content and old_string
        normalized_content = self._normalize_line_endings(content)
        normalized_old_string = self._normalize_line_endings(old_string)
        
        # First try exact match
        matches = []
        start = 0
        
        while True:
            index = normalized_content.find(normalized_old_string, start)
            if index == -1:
                break
            matches.append((index, index + len(normalized_old_string)))
            start = index + 1
        
        # If exact match found, return it
        if matches:
            return matches
        
        # If no exact match and fuzzy is enabled, try fuzzy matching
        if fuzzy:
            fuzzy_matches = self._find_fuzzy_matches(content, old_string)
            if fuzzy_matches:
                logger.info(f"Exact match not found, using fuzzy matching: found {len(fuzzy_matches)} match(es)")
                return fuzzy_matches
        
        return matches
    
    def _get_line_number(self, content: str, position: int) -> int:
        """Get line number for a character position."""
        return content[:position].count('\n') + 1
    
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
        start_line_content: str, 
        end_line_content: str,
        new_string: str,
        estimated_line_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Replace code blocks by using start and end line content as anchors.
        
        Args:
            file_path: Path to the file to modify
            start_line_content: Content of the first line (anchor) to identify start
            end_line_content: Content of the last line (anchor) to identify end
            new_string: Replacement code block
            estimated_line_count: Estimated number of lines to replace (used to disambiguate multiple matches)
        
        Returns:
            Dictionary with execution results
        """
        logger.info("=" * 80)
        logger.info(f"Execute search_replace tool")
        logger.info(f"File path: {file_path}")
        logger.info(f"Start line content: {start_line_content[:100]}")
        logger.info(f"End line content: {end_line_content[:100]}")
        logger.info(f"New string length: {len(new_string)}")
        if estimated_line_count is not None:
            logger.info(f"Estimated line count: {estimated_line_count}")
        
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
                
                # Normalize line endings for consistent matching
                normalized_content = self._normalize_line_endings(content)
                content_lines = normalized_content.split('\n')
                
                logger.debug(f"File has {len(content)} characters, {len(content_lines)} lines")
                
                # Normalize anchor lines (remove trailing whitespace for matching)
                normalized_start_content = self._normalize_line_for_matching(start_line_content)
                normalized_end_content = self._normalize_line_for_matching(end_line_content)
                
                # Find all possible start lines that match start_line_content
                start_line_indices = []
                for i, line in enumerate(content_lines):
                    if self._normalize_line_for_matching(line) == normalized_start_content:
                        start_line_indices.append(i)
                        logger.debug(f"Found start line candidate at index {i} (line {i+1}): {line[:80]}")
                
                if not start_line_indices:
                    logger.error(f"Start line content not found: {start_line_content[:100]}")
                    # Log full file content for debugging if VERBOSE is enabled
                    if VERBOSE:
                        logger.error(f"File content at time of error (full content, {len(content)} characters, {len(content_lines)} lines):")
                        logger.error("=" * 80)
                        logger.error(content)
                        logger.error("=" * 80)
                    return {
                        "success": False,
                        "error": f"Start line anchor not found: {start_line_content[:100]}",
                        "file_path": str(resolved_path),
                        "suggestion": "Please check if the start line content is correct and ensure there is a matching line in the file"
                    }
                
                # Find all possible matches (start_line, end_line pairs)
                matches = []
                for start_idx in start_line_indices:
                    # Find end line (must be after start line)
                    for i in range(start_idx, len(content_lines)):
                        line = content_lines[i]
                        if self._normalize_line_for_matching(line) == normalized_end_content:
                            line_count = i - start_idx + 1  # Inclusive
                            matches.append((start_idx, i, line_count))
                            logger.debug(f"Found match: start={start_idx+1}, end={i+1}, line_count={line_count}")
                            break
                
                if not matches:
                    logger.error(f"End line content not found after any start line: {end_line_content[:100]}")
                    # Log full file content for debugging if VERBOSE is enabled
                    if VERBOSE:
                        logger.error(f"File content at time of error (full content, {len(content)} characters, {len(content_lines)} lines):")
                        logger.error("=" * 80)
                        logger.error(content)
                        logger.error("=" * 80)
                    # Also log context around found start lines for quick reference
                    logger.error(f"Found start lines at: {[idx + 1 for idx in start_line_indices]}")
                    if VERBOSE:
                        for start_idx in start_line_indices[:3]:  # Log context for first 3 start lines
                            start_context = max(0, start_idx - 5)
                            end_context = min(len(content_lines), start_idx + 20)
                            context_lines = content_lines[start_context:end_context]
                            logger.error(f"Context around start line {start_idx + 1} (lines {start_context + 1}-{end_context}):")
                            for i, line in enumerate(context_lines, start=start_context + 1):
                                marker = ">>> " if i == start_idx + 1 else "    "
                                logger.error(f"{marker}{i:4d}: {line}")
                    return {
                        "success": False,
                        "error": f"End line anchor not found: {end_line_content[:100]} (after any start line)",
                        "file_path": str(resolved_path),
                        "start_lines_found": [idx + 1 for idx in start_line_indices],
                        "suggestion": "Please check if the end line content is correct and ensure there is a matching line after the start line"
                    }
                
                # If multiple matches found, use estimated_line_count to select the best match
                if len(matches) > 1:
                    logger.info(f"Found {len(matches)} possible matches, using estimated_line_count to disambiguate")
                    if estimated_line_count is not None:
                        # Select match with line count closest to estimated_line_count
                        best_match = min(matches, key=lambda m: abs(m[2] - estimated_line_count))
                        logger.info(f"Selected match with line_count={best_match[2]} (closest to estimated {estimated_line_count})")
                        start_line_idx, end_line_idx, _ = best_match
                    else:
                        # No estimate provided, use first match and warn
                        logger.warning(f"Multiple matches found ({len(matches)}) but no estimated_line_count provided, using first match")
                        # Log full file content and match locations for debugging if VERBOSE is enabled
                        if VERBOSE:
                            logger.error(f"File content at time of error (full content, {len(content)} characters, {len(content_lines)} lines):")
                            logger.error("=" * 80)
                            logger.error(content)
                            logger.error("=" * 80)
                        logger.error(f"Found {len(matches)} matches at locations: {[(s+1, e+1, lc) for s, e, lc in matches]}")
                        # Log context around each match for quick reference if VERBOSE is enabled
                        if VERBOSE:
                            for match_idx, (s, e, lc) in enumerate(matches[:3], 1):  # Log first 3 matches
                                start_context = max(0, s - 5)
                                end_context = min(len(content_lines), e + 5)
                                context_lines = content_lines[start_context:end_context]
                                logger.error(f"Match {match_idx} context (lines {start_context + 1}-{end_context}, match at {s+1}-{e+1}):")
                                for i, line in enumerate(context_lines, start=start_context + 1):
                                    marker = ">>> " if s + 1 <= i <= e + 1 else "    "
                                    logger.error(f"{marker}{i:4d}: {line}")
                        start_line_idx, end_line_idx, _ = matches[0]
                        return {
                            "success": False,
                            "error": f"Found {len(matches)} matches, but estimated_line_count parameter not provided. Please provide estimated_line_count to determine which location to replace.",
                            "file_path": str(resolved_path),
                            "matches_found": len(matches),
                            "match_locations": [(s+1, e+1, lc) for s, e, lc in matches],
                            "suggestion": "Please provide estimated_line_count parameter to help the tool select the correct match location"
                        }
                else:
                    # Single match found
                    start_line_idx, end_line_idx, _ = matches[0]
                    logger.info(f"Found single match: start={start_line_idx+1}, end={end_line_idx+1}")
                
                # Replace lines from start_line_idx to end_line_idx (inclusive)
                # Build new content: lines before start + new_string + lines after end
                normalized_new_string = self._normalize_line_endings(new_string)
                
                # Reconstruct file content
                new_lines = []
                # Add lines before start
                new_lines.extend(content_lines[:start_line_idx])
                # Add new content (split by newlines to handle multi-line replacements)
                new_lines.extend(normalized_new_string.split('\n'))
                # Add lines after end
                new_lines.extend(content_lines[end_line_idx + 1:])
                
                # Join lines back together
                result_content = '\n'.join(new_lines)
                
                actual_line_count = end_line_idx - start_line_idx + 1
                logger.info(f"Replacing lines {start_line_idx + 1} to {end_line_idx + 1} (inclusive, {actual_line_count} lines)")
                if estimated_line_count is not None:
                    logger.info(f"Actual line count: {actual_line_count}, estimated: {estimated_line_count}, difference: {abs(actual_line_count - estimated_line_count)}")
                
                # Write back to file (preserve original line ending style if possible)
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
                    "start_line": start_line_idx + 1,
                    "end_line": end_line_idx + 1,
                    "lines_replaced": end_line_idx - start_line_idx + 1,
                    "message": f"Successfully replaced lines {start_line_idx + 1} to {end_line_idx + 1}"
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

