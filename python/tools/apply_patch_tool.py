#!/usr/bin/env python3
"""
Apply Patch Tool - Apply unified diff patches to files
"""

import os
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from utils.logger import Logger
from tools.base_tool import MCPTool
from model import ToolCallMessage, ToolResultMessage

logger = Logger('apply_patch_tool', log_to_file=False)


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
        """This tool should not be exposed to LLM agent (used internally)."""
        return False
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": "apply_patch",
                "description": "Apply unified diff patches to files in the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patch_content": {
                            "type": "string",
                            "description": "Patch content in unified diff format, or path to patch file"
                        },
                        "target_file": {
                            "type": "string",
                            "description": "Optional target file path (overrides patch header)"
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "If True, only validate without applying (default: False)",
                            "default": False
                        }
                    },
                    "required": ["patch_content"]
                }
            }
        }
    
    def get_call_notification(self, tool_args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get custom notification for apply patch tool call.
        
        Args:
            tool_args: Tool arguments containing 'patch_content'
        
        Returns:
            Custom notification dictionary
        """
        patch_content = tool_args.get("patch_content", "")
        dry_run = tool_args.get("dry_run", False)
        # Truncate long patch content for display
        display_content = patch_content[:50] + "..." if len(patch_content) > 50 else patch_content
        mode = "验证" if dry_run else "应用"
        return ToolCallMessage(
            tool_name=self.name,
            content=f"正在{mode}补丁: {display_content}"
        )
    
    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get custom notification for apply patch tool result.
        
        Args:
            tool_result: Tool execution result
        
        Returns:
            Custom notification dictionary
        """
        success = tool_result.get("success", False)
        patches_applied = tool_result.get("patches_applied", 0)
        patches_total = tool_result.get("patches_total", 0)
        
        if success:
            return ToolResultMessage(
                tool_name=self.name,
                content=f"补丁应用成功 ({patches_applied}/{patches_total})"
            )
        else:
            error = tool_result.get("error", "未知错误")
            return ToolResultMessage(
                tool_name=self.name,
                content=f"补丁应用失败: {error}"
            )
    
    def _parse_patch(self, patch_content: str) -> List[Tuple[str, List[str], List[str]]]:
        """
        Parse unified diff patch content.
        
        Args:
            patch_content: Patch content string
        
        Returns:
            List of tuples: (file_path, old_lines, new_lines)
        """
        patches = []
        lines = patch_content.split('\n')
        i = 0
        
        while i < len(lines):
            # Look for patch header: --- file_path
            if lines[i].startswith('---'):
                old_file = lines[i][4:].strip()
                # Remove timestamp if present (format: --- a/file.txt\t2024-01-01 12:00:00)
                old_file = old_file.split('\t')[0].strip()
                # Remove 'a/' or 'b/' prefix if present
                if old_file.startswith('a/') or old_file.startswith('b/'):
                    old_file = old_file[2:]
                
                i += 1
                if i < len(lines) and lines[i].startswith('+++'):
                    new_file = lines[i][4:].strip()
                    new_file = new_file.split('\t')[0].strip()
                    if new_file.startswith('a/') or new_file.startswith('b/'):
                        new_file = new_file[2:]
                    
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
                        if line.startswith('@@'):
                            # If we were in a hunk, save it before starting new one
                            if in_hunk:
                                all_old_lines.extend(hunk_old_lines)
                                all_new_lines.extend(hunk_new_lines)
                                hunk_old_lines = []
                                hunk_new_lines = []
                            
                            in_hunk = True
                            i += 1
                            continue
                        
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
                        patches.append((target_file, all_old_lines, all_new_lines))
                    continue
            
            i += 1
        
        return patches
    
    def _apply_patch_to_file(self, file_path: str, old_lines: List[str], new_lines: List[str], dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply patch to a single file.
        
        Args:
            file_path: Path to the file to patch
            old_lines: Expected old lines (for validation)
            new_lines: New lines to apply
            dry_run: If True, only validate without applying
        
        Returns:
            Dictionary with result information
        """
        # Resolve file path relative to workspace_dir if set
        if self.workspace_dir:
            if os.path.isabs(file_path):
                # If absolute path, use as is
                resolved_path = Path(file_path)
            else:
                # If relative, resolve relative to workspace_dir
                resolved_path = Path(self.workspace_dir) / file_path
        else:
            resolved_path = Path(file_path)
        
        resolved_path = resolved_path.resolve()
        
        # Check if file exists
        if not resolved_path.exists():
            return {
                "success": False,
                "error": f"File does not exist: {resolved_path}",
                "file_path": str(resolved_path)
            }
        
        try:
            # Read current file content
            with open(resolved_path, 'r', encoding='utf-8') as f:
                current_lines = f.readlines()
            
            # Remove trailing newlines for comparison
            current_lines = [line.rstrip('\n\r') for line in current_lines]
            old_lines = [line.rstrip('\n\r') for line in old_lines]
            
            # Try to find the location to apply the patch
            # Simple approach: find the first occurrence of old_lines in current_lines
            patch_start = -1
            for i in range(len(current_lines) - len(old_lines) + 1):
                if current_lines[i:i+len(old_lines)] == old_lines:
                    patch_start = i
                    break
            
            if patch_start == -1:
                # Try fuzzy matching - find at least 50% match
                best_match = -1
                best_score = 0
                for i in range(len(current_lines) - len(old_lines) + 1):
                    match_count = sum(1 for j, old_line in enumerate(old_lines) 
                                    if i + j < len(current_lines) and current_lines[i + j] == old_line)
                    score = match_count / len(old_lines) if old_lines else 0
                    if score > best_score:
                        best_score = score
                        best_match = i
                
                if best_score < 0.5:
                    return {
                        "success": False,
                        "error": f"Could not find patch location in file. Expected context not found.",
                        "file_path": str(resolved_path),
                        "expected_context": old_lines[:5] if len(old_lines) > 5 else old_lines,
                        "best_match_score": best_score
                    }
                else:
                    patch_start = best_match
                    logger.warning(f"Using fuzzy match (score: {best_score:.2f}) for patch application")
            
            if dry_run:
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
            new_file_lines = (
                current_lines[:patch_start] +
                new_lines +
                current_lines[patch_start + len(old_lines):]
            )
            
            # Write back to file
            with open(resolved_path, 'w', encoding='utf-8') as f:
                for line in new_file_lines:
                    f.write(line + '\n')
            
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
    
    async def execute(self, patch_content: str, target_file: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply a patch to a file.
        
        Args:
            patch_content: Patch content in unified diff format, or path to patch file
            target_file: Optional target file path (overrides patch header)
            dry_run: If True, only validate without applying
        
        Returns:
            Dictionary with execution results
        """
        logger.info(f"Applying patch (dry_run={dry_run})")
        
        # Check if patch_content is a file path
        patch_text = patch_content
        if os.path.exists(patch_content):
            try:
                with open(patch_content, 'r', encoding='utf-8') as f:
                    patch_text = f.read()
                logger.debug(f"Read patch from file: {patch_content}")
            except Exception as e:
                logger.error(f"Error reading patch file: {e}")
                return {
                    "success": False,
                    "error": f"Failed to read patch file: {str(e)}"
                }
        
        # Parse the patch
        try:
            patches = self._parse_patch(patch_text)
        except Exception as e:
            logger.error(f"Error parsing patch: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to parse patch: {str(e)}"
            }
        
        if not patches:
            return {
                "success": False,
                "error": "No valid patches found in patch content. Patch should be in unified diff format starting with '---' and '+++'."
            }
        
        # Apply each patch
        results = []
        for file_path, old_lines, new_lines in patches:
            # Use target_file if provided, otherwise use file_path from patch
            actual_target = target_file if target_file else file_path
            
            result = self._apply_patch_to_file(actual_target, old_lines, new_lines, dry_run)
            results.append(result)
        
        # Return summary
        success_count = sum(1 for r in results if r.get("success", False))
        total_count = len(results)
        
        return_dict = {
            "success": success_count == total_count,
            "patches_applied": success_count,
            "patches_total": total_count,
            "results": results
        }
        
        # Include dry_run flag if any result has it
        if dry_run or any(r.get("dry_run", False) for r in results):
            return_dict["dry_run"] = True
        
        return return_dict

