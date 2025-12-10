#!/usr/bin/env python3
"""
Apply Patch Tool - Apply unified diff patches to files
"""

import os
import re
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from datetime import datetime
from utils.logger import Logger
from tools.base_tool import MCPTool

logger = Logger('apply_patch_tool', log_to_file=False)

# Configuration for patch saving
ENABLE_PATCH_SAVE = True  # Set to False to disable patch saving
PATCH_SAVE_DIR = Path("/home/ym/Documents/Projects/Course/CSC4100/group_project/BranchCoder/logs/patches")


class ApplyPatchTool(MCPTool):
    """Tool for applying unified diff patches to files."""
    
    def __init__(self):
        """Initialize apply patch tool."""
        self.workspace_dir: Optional[str] = None
    
    def set_workspace_dir(self, workspace_dir: str):
        """
        Set the workspace directory. Patches will be applied relative to this directory.
        
        Args:
            workspace_dir: Path to workspace directory
        """
        if self.workspace_dir == workspace_dir:
            return
        
        self.workspace_dir = workspace_dir
        logger.info(f"Setting workspace directory for apply patch tool: {workspace_dir}")
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "apply_patch"
    
    @property
    def agent_tool(self) -> bool:
        """This tool should be exposed to LLM agent for applying patches."""
        return True
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": "apply_patch",
                "description": "Apply unified diff patches to files. Use this tool when you need to apply code changes to files. The target_file_path must be an absolute path (beginning with /).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_file_path": {
                            "type": "string",
                            "description": "Target file absolute path (begin with /, not with workspace_dir)"
                        },
                        "patch_content": {
                            "type": "string",
                            "description": "Patch content in unified diff format. E.g. --- test.txt+++ test.txt@@ -1,5 +1,5 @@Line 1-Line 2+Line 2 Modified Line 3 Line 4 Line 5"
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "If True, only validate without applying (default: False)",
                            "default": False
                        }
                    },
                    "required": ["patch_content", "target_file_path"]
                }
            }
        }
    
    def get_call_notification(self, tool_args: Dict[str, Any]) -> Optional[str]:
        """
        Get custom notification for apply patch tool call.
        
        Args:
            tool_args: Tool arguments containing 'patch_content' and 'target_file_path'
        
        Returns:
            Custom notification message string
        """
        patch_content = tool_args.get("patch_content", "")
        target_file_path = tool_args.get("target_file_path", "")
        dry_run = tool_args.get("dry_run", False)
        # Truncate long patch content for display
        display_content = patch_content[:50] + "..." if len(patch_content) > 50 else patch_content
        mode = "验证" if dry_run else "应用"
        return f"正在{mode}补丁到 {target_file_path}: {display_content}"
    
    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[str]:
        """
        Get custom notification for apply patch tool result.
        
        Args:
            tool_result: Tool execution result
        
        Returns:
            Custom notification message string
        """
        success = tool_result.get("success", False)
        patches_applied = tool_result.get("patches_applied", 0)
        patches_total = tool_result.get("patches_total", 0)
        
        if success:
            return f"补丁应用成功 ({patches_applied}/{patches_total})"
        else:
            error = tool_result.get("error", "未知错误")
            return f"补丁应用失败: {error}"
    
    def _parse_patch(self, patch_content: str) -> List[Tuple[str, List[str], List[str]]]:
        """
        Parse unified diff patch content.
        Supports both standard unified diff format and simplified format:
        - Standard: --- file_path\n+++ file_path\n@@ ... @@\n...
        - Simplified: *** Begin Patch\n*** Update File: file_path\n+line\n-line\n*** End Patch
        
        Args:
            patch_content: Patch content string
        
        Returns:
            List of tuples: (file_path, old_lines, new_lines)
        """
        patches = []
        lines = patch_content.split('\n')
        
        # Try to detect simplified format first
        if '*** Begin Patch' in patch_content or '*** Update File:' in patch_content:
            return self._parse_simplified_patch(patch_content)
        
        i = 0
        
        while i < len(lines):
            # Look for patch header: --- file_path
            if lines[i].startswith('---'):
                old_file = lines[i][4:].strip()
                # Remove timestamp if present (format: --- a/file.txt\t2024-01-01 12:00:00)
                old_file = old_file.split('\t')[0].strip()
                # Remove 'a/' or 'b/' prefix if present
                # Note: If original path was absolute like /home/..., git diff shows it as a/home/...
                # After removing a/, we need to restore the leading /
                if old_file.startswith('a/') or old_file.startswith('b/'):
                    old_file = old_file[2:]
                    # If the path doesn't start with / after removing a/ or b/,
                    # it means the original path was absolute, so add / back
                    if not old_file.startswith('/'):
                        old_file = '/' + old_file
                
                i += 1
                if i < len(lines) and lines[i].startswith('+++'):
                    new_file = lines[i][4:].strip()
                    new_file = new_file.split('\t')[0].strip()
                    if new_file.startswith('a/') or new_file.startswith('b/'):
                        new_file = new_file[2:]
                        # Restore leading / for absolute paths
                        if not new_file.startswith('/'):
                            new_file = '/' + new_file
                    
                    # Use new_file as target, or old_file if new_file is /dev/null
                    target_file = new_file if new_file != '/dev/null' else old_file
                    if target_file == '/dev/null':
                        target_file = old_file
                    
                    i += 1
                    
                    # Parse all hunks for this file
                    # Collect all changes across multiple hunks
                    all_old_lines = []
                    all_new_lines = []
                    in_hunk = False
                    hunk_old_lines = []
                    hunk_new_lines = []
                    
                    while i < len(lines):
                        line = lines[i]
                        
                        # Check for next patch header (new file)
                        if line.startswith('---') and not in_hunk:
                            break
                        
                        # Hunk header: @@ -start,count +start,count @@
                        # Must match pattern: @@ -number,number +number,number @@
                        # This prevents code lines starting with @@ from being misidentified
                        # Pattern allows optional spaces but requires -digit and +digit patterns
                        # More flexible: allows @@-1,5+1,5@@ or @@ -1,5 +1,5 @@ formats
                        # Must have both - and + signs (though spaces are optional)
                        is_hunk_header = False
                        if line.startswith('@@'):
                            # Try strict pattern first
                            hunk_header_pattern = r'^@@\s*-\d+(?:,\d+)?\s*\+\d+(?:,\d+)?\s*@@'
                            is_hunk_header = bool(re.match(hunk_header_pattern, line))
                            
                            # Fallback: if line starts with @@ and contains both -digit and +digit patterns,
                            # treat it as hunk header even if format is slightly off
                            if not is_hunk_header:
                                # Check if it has digit patterns after - and + (allowing for no spaces)
                                if re.search(r'-\d+', line) and re.search(r'\+\d+', line):
                                    is_hunk_header = True
                                    logger.debug(f"Using fallback hunk header detection for: {line[:50]}")
                            
                            # Additional fallback: if it looks like a hunk header (starts with @@ and ends with @@)
                            # and has some numeric content, treat it as hunk header
                            if not is_hunk_header and line.strip().endswith('@@') and re.search(r'\d+', line):
                                # Very permissive: if it starts with @@, ends with @@, and has numbers
                                # This handles edge cases where format is non-standard
                                is_hunk_header = True
                                logger.debug(f"Using very permissive hunk header detection for: {line[:50]}")
                        
                        if is_hunk_header:
                            # If we were in a hunk, save it before starting new one
                            if in_hunk:
                                all_old_lines.extend(hunk_old_lines)
                                all_new_lines.extend(hunk_new_lines)
                                hunk_old_lines = []
                                hunk_new_lines = []
                            
                            in_hunk = True
                            i += 1
                            continue
                        
                        # If line starts with @@ but is not a valid hunk header
                        if line.startswith('@@') and not is_hunk_header:
                            if in_hunk:
                                # If we're in a hunk and this line starts with @@ but is not a valid header,
                                # it might be a new hunk header with non-standard format, or malformed content
                                # End the current hunk and skip this line (treat as malformed)
                                logger.warning(f"Found @@ line in hunk that is not a valid header, ending hunk: {line[:50]}")
                                all_old_lines.extend(hunk_old_lines)
                                all_new_lines.extend(hunk_new_lines)
                                hunk_old_lines = []
                                hunk_new_lines = []
                                in_hunk = False
                            # Skip this line whether in hunk or not
                            i += 1
                            continue
                        
                        # If we encounter patch content lines (space, -, +) but not in a hunk,
                        # it might be a patch without hunk header (non-standard but possible)
                        # Start processing anyway
                        if not in_hunk and (line.startswith(' ') or line.startswith('-') or line.startswith('+')):
                            logger.warning(f"Found patch content line without hunk header, starting hunk anyway: {line[:50]}")
                            in_hunk = True
                            # Don't increment i, process this line below
                        
                        if in_hunk:
                            if line.startswith(' '):
                                # Context line (unchanged) - add to both
                                hunk_old_lines.append(line[1:])
                                hunk_new_lines.append(line[1:])
                            elif line.startswith('-'):
                                # Removed line - only in old
                                hunk_old_lines.append(line[1:])
                            elif line.startswith('+'):
                                # Added line - only in new
                                hunk_new_lines.append(line[1:])
                            elif line.strip() == '':
                                # Empty line in hunk - preserve as context
                                hunk_old_lines.append('')
                                hunk_new_lines.append('')
                            elif line.startswith('\\'):
                                # No newline at end of file marker
                                pass
                            else:
                                # End of hunk - save current hunk
                                all_old_lines.extend(hunk_old_lines)
                                all_new_lines.extend(hunk_new_lines)
                                hunk_old_lines = []
                                hunk_new_lines = []
                                in_hunk = False
                                # Continue to see if there's another hunk
                        
                        i += 1
                    
                    # Save last hunk if any
                    if in_hunk:
                        all_old_lines.extend(hunk_old_lines)
                        all_new_lines.extend(hunk_new_lines)
                    
                    # Only add patch if we have content
                    if all_old_lines or all_new_lines:
                        logger.debug(f"Parsed patch for file: {target_file} ({len(all_old_lines)} old lines, {len(all_new_lines)} new lines)")
                        patches.append((target_file, all_old_lines, all_new_lines))
                    continue
            
            i += 1
        
        return patches
    
    def _parse_simplified_patch(self, patch_content: str) -> List[Tuple[str, List[str], List[str]]]:
        """
        Parse simplified patch format:
        *** Begin Patch
        *** Update File: /path/to/file
        +new line
        -old line
        context line (no prefix)
        *** End Patch
        
        Args:
            patch_content: Simplified patch content string
        
        Returns:
            List of tuples: (file_path, old_lines, new_lines)
        """
        patches = []
        lines = patch_content.split('\n')
        i = 0
        current_file = None
        old_lines = []
        new_lines = []
        in_patch = False
        
        while i < len(lines):
            line = lines[i]
            
            # Look for patch start
            if '*** Begin Patch' in line or '*** Update File:' in line:
                in_patch = True
                # Extract file path from "*** Update File: /path/to/file"
                if '*** Update File:' in line:
                    current_file = line.split('*** Update File:')[1].strip()
                    # Ensure absolute path
                    if current_file and not current_file.startswith('/'):
                        current_file = '/' + current_file
                i += 1
                continue
            
            # Look for patch end
            if '*** End Patch' in line:
                if current_file and (old_lines or new_lines):
                    patches.append((current_file, old_lines, new_lines))
                current_file = None
                old_lines = []
                new_lines = []
                in_patch = False
                i += 1
                continue
            
            if in_patch and current_file:
                # Parse patch lines
                if line.startswith('+'):
                    # Added line - only in new
                    new_lines.append(line[1:])
                    # For pure additions, old_lines should be empty or match context
                    # We'll handle this by making old_lines empty for pure additions
                elif line.startswith('-'):
                    # Removed line - only in old
                    old_lines.append(line[1:])
                    # If there's no corresponding new line, add empty to new_lines
                    if len(new_lines) < len(old_lines):
                        new_lines.append('')
                elif line.strip() == '':
                    # Empty line - add to both if we have context, otherwise skip
                    if old_lines or new_lines:
                        # Only add if we're in the middle of a patch
                        if len(old_lines) < len(new_lines):
                            old_lines.append('')
                        elif len(new_lines) < len(old_lines):
                            new_lines.append('')
                        else:
                            old_lines.append('')
                            new_lines.append('')
                elif not line.startswith('***'):
                    # Context line (no prefix) - this means unchanged line
                    # Add to both old and new
                    old_lines.append(line)
                    new_lines.append(line)
            
            i += 1
        
        # Handle case where patch doesn't end with "*** End Patch"
        if in_patch and current_file and (old_lines or new_lines):
            patches.append((current_file, old_lines, new_lines))
        
        return patches
    
    def _apply_patch_to_file(self, file_path: str, old_lines: List[str], new_lines: List[str], dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply patch to a single file.
        
        Args:
            file_path: Path to the file to patch (should be absolute path from LLM)
            old_lines: Expected old lines (for validation)
            new_lines: New lines to apply
            dry_run: If True, only validate without applying
        
        Returns:
            Dictionary with result information
        """
        logger.info(f"Applying patch to file: {file_path}")
        logger.debug(f"  - Old lines count: {len(old_lines)}")
        logger.debug(f"  - New lines count: {len(new_lines)}")
        logger.debug(f"  - Dry run: {dry_run}")
        
        # Use file_path directly as it should be an absolute path from LLM
        # No need to concatenate with workspace_dir
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
        
        logger.info(f"File exists, proceeding with patch application")
        
        try:
            # Read current file content
            logger.debug(f"Reading file content from: {resolved_path}")
            with open(resolved_path, 'r', encoding='utf-8') as f:
                current_lines = f.readlines()
            
            logger.debug(f"File has {len(current_lines)} lines")
            
            # Remove trailing newlines for comparison
            current_lines = [line.rstrip('\n\r') for line in current_lines]
            old_lines = [line.rstrip('\n\r') for line in old_lines]
            
            # Handle pure addition case (old_lines is empty)
            if not old_lines and new_lines:
                logger.info("Pure addition patch: appending new lines to end of file")
                patch_start = len(current_lines)
            else:
                # Normalize old_lines: remove leading/trailing empty lines for better matching
                # But keep track of the original for actual replacement
                normalized_old_lines = old_lines
                leading_empty = 0
                trailing_empty = 0
                
                # Count leading empty lines
                for line in old_lines:
                    if line.strip() == '':
                        leading_empty += 1
                    else:
                        break
                
                # Count trailing empty lines
                for line in reversed(old_lines):
                    if line.strip() == '':
                        trailing_empty += 1
                    else:
                        break
                
                # If all lines are empty, keep as is
                if leading_empty < len(old_lines):
                    # Remove leading/trailing empty lines for matching
                    normalized_old_lines = old_lines[leading_empty:len(old_lines)-trailing_empty] if trailing_empty > 0 else old_lines[leading_empty:]
                    logger.debug(f"Normalized old_lines: removed {leading_empty} leading and {trailing_empty} trailing empty lines")
                
                # Try to find the location to apply the patch
                # First try exact match with normalized lines
                logger.debug(f"Searching for patch location (looking for {len(normalized_old_lines)} normalized lines, {len(old_lines)} total)")
                patch_start = -1
                
                # Search from beginning
                for i in range(len(current_lines) - len(normalized_old_lines) + 1):
                    if current_lines[i:i+len(normalized_old_lines)] == normalized_old_lines:
                        # Found match, adjust for leading empty lines
                        patch_start = max(0, i - leading_empty)
                        logger.info(f"Found exact match at line {patch_start + 1} (normalized match at {i + 1})")
                        break
                
                # If not found, try searching from the end (for cases where content is at file end)
                if patch_start == -1:
                    logger.debug("Exact match not found from beginning, trying from end")
                    for i in range(len(current_lines) - len(normalized_old_lines), -1, -1):
                        if i >= 0 and current_lines[i:i+len(normalized_old_lines)] == normalized_old_lines:
                            patch_start = max(0, i - leading_empty)
                            logger.info(f"Found exact match at line {patch_start + 1} (searched from end, normalized match at {i + 1})")
                            break
                
                # If still not found, try with original old_lines (in case normalization removed important context)
                if patch_start == -1:
                    logger.debug("Trying exact match with original old_lines")
                    for i in range(len(current_lines) - len(old_lines) + 1):
                        if current_lines[i:i+len(old_lines)] == old_lines:
                            patch_start = i
                            logger.info(f"Found exact match at line {patch_start + 1} (using original old_lines)")
                            break
                
                if patch_start == -1:
                    logger.warning("Exact match not found, trying fuzzy matching")
                    # Try fuzzy matching - find at least 50% match
                    best_match = -1
                    best_score = 0
                    
                    # Try with normalized lines first
                    for i in range(len(current_lines) - len(normalized_old_lines) + 1):
                        match_count = sum(1 for j, old_line in enumerate(normalized_old_lines) 
                                        if i + j < len(current_lines) and current_lines[i + j] == old_line)
                        score = match_count / len(normalized_old_lines) if normalized_old_lines else 0
                        if score > best_score:
                            best_score = score
                            best_match = max(0, i - leading_empty)
                    
                    # Also try from the end
                    for i in range(len(current_lines) - len(normalized_old_lines), -1, -1):
                        if i >= 0:
                            match_count = sum(1 for j, old_line in enumerate(normalized_old_lines) 
                                            if i + j < len(current_lines) and current_lines[i + j] == old_line)
                            score = match_count / len(normalized_old_lines) if normalized_old_lines else 0
                            if score > best_score:
                                best_score = score
                                best_match = max(0, i - leading_empty)
                    
                    # Fallback to original old_lines if normalized didn't work well
                    if best_score < 0.5:
                        logger.debug("Trying fuzzy match with original old_lines")
                        for i in range(len(current_lines) - len(old_lines) + 1):
                            match_count = sum(1 for j, old_line in enumerate(old_lines) 
                                            if i + j < len(current_lines) and current_lines[i + j] == old_line)
                            score = match_count / len(old_lines) if old_lines else 0
                            if score > best_score:
                                best_score = score
                                best_match = i
                    
                    if best_score < 0.5:
                        logger.error(f"Could not find patch location. Best match score: {best_score:.2f}")
                        logger.debug(f"Expected context ({len(old_lines)} lines, showing first 10):")
                        for i, line in enumerate(old_lines[:10], 1):
                            logger.debug(f"  Expected {i}: {repr(line)}")
                        logger.debug(f"Actual file content (showing first 20 lines):")
                        for i, line in enumerate(current_lines[:20], 1):
                            logger.debug(f"  Actual {i}: {repr(line)}")
                        logger.debug(f"Actual file content (showing last 20 lines):")
                        for i, line in enumerate(current_lines[-20:], len(current_lines) - 19):
                            logger.debug(f"  Actual {i}: {repr(line)}")
                        
                        # Try to find partial matches for debugging
                        if best_match >= 0:
                            logger.debug(f"Best match location: line {best_match + 1}")
                            logger.debug(f"Best match context:")
                            for i in range(min(5, len(old_lines))):
                                if best_match + i < len(current_lines):
                                    match_indicator = "✓" if i < len(old_lines) and best_match + i < len(current_lines) and current_lines[best_match + i] == old_lines[i] else "✗"
                                    logger.debug(f"  {match_indicator} Expected: {repr(old_lines[i]) if i < len(old_lines) else 'N/A'}")
                                    logger.debug(f"    Actual:   {repr(current_lines[best_match + i]) if best_match + i < len(current_lines) else 'N/A'}")
                        
                        return {
                            "success": False,
                            "error": f"Could not find patch location in file. Expected context not found.",
                            "file_path": str(resolved_path),
                            "expected_context": old_lines[:10] if len(old_lines) > 10 else old_lines,
                            "actual_file_preview": current_lines[:20] if len(current_lines) > 20 else current_lines,
                            "actual_file_end": current_lines[-20:] if len(current_lines) > 20 else current_lines,
                            "best_match_score": best_score,
                            "best_match_location": best_match + 1 if best_match >= 0 else None,
                            "expected_lines_count": len(old_lines),
                            "actual_lines_count": len(current_lines),
                            "suggestion": "The file content may have changed since the patch was generated, or there may be whitespace/formatting differences. Please verify the patch matches the current file state."
                        }
                    else:
                        patch_start = best_match
                        logger.warning(f"Using fuzzy match (score: {best_score:.2f}) at line {patch_start + 1} for patch application")
            
            if dry_run:
                logger.info(f"Dry run: Patch would be applied at line {patch_start + 1}")
                return {
                    "success": True,
                    "dry_run": True,
                    "file_path": str(resolved_path),
                    "patch_location": patch_start,
                    "lines_to_replace": len(old_lines),
                    "lines_to_add": len(new_lines),
                    "message": "Patch validated successfully (dry run)"
                }
            
            # Apply the patch
            logger.info(f"Applying patch at line {patch_start + 1}: replacing {len(old_lines)} lines with {len(new_lines)} lines")
            new_file_lines = (
                current_lines[:patch_start] +
                new_lines +
                current_lines[patch_start + len(old_lines):]
            )
            
            logger.debug(f"New file will have {len(new_file_lines)} lines (was {len(current_lines)})")
            
            # Write back to file
            logger.info(f"Writing patched content to: {resolved_path}")
            with open(resolved_path, 'w', encoding='utf-8') as f:
                for line in new_file_lines:
                    f.write(line + '\n')
            
            logger.info(f"Patch applied successfully to {resolved_path}")
            return {
                "success": True,
                "file_path": str(resolved_path),
                "patch_location": patch_start,
                "lines_replaced": len(old_lines),
                "lines_added": len(new_lines),
                "message": "Patch applied successfully"
            }
            
        except Exception as e:
            logger.error(f"Error applying patch to {resolved_path}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "file_path": str(resolved_path)
            }
    
    def _save_patch_to_file(self, patch_content: str, target_file_path: str, success: bool) -> Optional[str]:
        """
        Save patch content to a file for record keeping.
        
        Args:
            patch_content: The patch content to save
            target_file_path: The target file path that was patched
            success: Whether the patch was successfully applied
        
        Returns:
            Path to saved patch file, or None if saving failed
        """
        try:
            # Create patches directory if it doesn't exist
            PATCH_SAVE_DIR.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            # Extract filename from target path for better organization
            target_filename = Path(target_file_path).name
            status = "success" if success else "failed"
            patch_filename = f"{timestamp}_{target_filename}_{status}.patch"
            patch_file_path = PATCH_SAVE_DIR / patch_filename
            
            # Write patch content to file
            with open(patch_file_path, 'w', encoding='utf-8') as f:
                f.write(f"# Patch for: {target_file_path}\n")
                f.write(f"# Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"# Status: {status}\n")
                f.write(f"# {'=' * 76}\n\n")
                f.write(patch_content)
            
            logger.info(f"Patch saved to: {patch_file_path}")
            return str(patch_file_path)
        except Exception as e:
            logger.error(f"Failed to save patch to file: {e}", exc_info=True)
            return None
    
    async def execute(self, patch_content: str, target_file_path: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply a patch to a file.
        
        Args:
            patch_content: Patch content in unified diff format, or path to patch file
            target_file_path: Target file absolute path (required)
            dry_run: If True, only validate without applying
        
        Returns:
            Dictionary with execution results
        """
        logger.info("=" * 80)
        logger.info(f"Execute apply_patch tool (dry_run={dry_run})")
        logger.info(f"Target file path: {target_file_path}")
        logger.info(f"Patch content length: {len(patch_content)} characters")
        
        # Validate target_file_path is absolute
        if not os.path.isabs(target_file_path):
            logger.error(f"target_file_path must be an absolute path, got: {target_file_path}")
            return {
                "success": False,
                "error": f"target_file_path must be an absolute path, got: {target_file_path}"
            }
        
        # Check if patch_content is a file path
        patch_text = patch_content
        if os.path.exists(patch_content):
            try:
                logger.info(f"Reading patch from file: {patch_content}")
                with open(patch_content, 'r', encoding='utf-8') as f:
                    patch_text = f.read()
                logger.debug(f"Read {len(patch_text)} characters from patch file")
            except Exception as e:
                logger.error(f"Error reading patch file: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": f"Failed to read patch file: {str(e)}"
                }
        
        # Parse the patch
        logger.info("Parsing patch content...")
        try:
            patches = self._parse_patch(patch_text)
            logger.info(f"Parsed {len(patches)} patch(es) from content")
        except Exception as e:
            logger.error(f"Error parsing patch: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to parse patch: {str(e)}"
            }
        
        if not patches:
            logger.error("No valid patches found in patch content")
            return {
                "success": False,
                "error": "No valid patches found in patch content. Patch should be in unified diff format starting with '---' and '+++'."
            }
        
        # Log parsed patches
        for i, (file_path, old_lines, new_lines) in enumerate(patches, 1):
            logger.info(f"Patch {i}: old_lines={len(old_lines)}, new_lines={len(new_lines)}")
        
        # Apply patch to target_file_path (use first patch's content, ignore file path from patch)
        if len(patches) > 1:
            logger.warning(f"Multiple patches found ({len(patches)}), but only one target_file_path provided. Using first patch content.")
        
        # Use the first patch's content
        _, old_lines, new_lines = patches[0]
        
        logger.info(f"Applying patch to: {target_file_path}")
        result = self._apply_patch_to_file(target_file_path, old_lines, new_lines, dry_run)
        
        if result.get("success"):
            logger.info("Patch applied successfully")
        else:
            logger.error(f"Patch failed: {result.get('error', 'unknown error')}")
        
        # Save patch to file for record keeping (only if not dry_run)
        saved_patch_path = None
        
        if not dry_run and ENABLE_PATCH_SAVE:
            saved_patch_path = self._save_patch_to_file(
                patch_text, 
                target_file_path,
                result.get("success", False)
            )
        
        logger.info(f"Patch application complete: {'success' if result.get('success') else 'failed'}")
        logger.info("=" * 80)
        
        return_dict = {
            "success": result.get("success", False),
            "patches_applied": 1 if result.get("success") else 0,
            "patches_total": 1,
            "results": [result]
        }
        
        # Include dry_run flag if result has it
        if dry_run or result.get("dry_run", False):
            return_dict["dry_run"] = True
        
        # Include saved patch path if available
        if saved_patch_path:
            return_dict["saved_patch_path"] = saved_patch_path
        
        return return_dict

