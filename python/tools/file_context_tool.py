#!/usr/bin/env python3
"""
File Context Tool - Manage file context for dynamic inclusion in system prompts
"""

from typing import Dict, Any, Optional, List
from utils.logger import Logger
from tools.base_tool import MCPTool
from tools.file_context_manager import FileContextManager, FileOpenMode, get_file_context_manager

logger = Logger('file_context_tool', log_to_file=False)


class FileContextTool(MCPTool):
    """Tool for managing file context - opening/closing files for dynamic context inclusion."""
    
    def __init__(self):
        self.workspace_dir: Optional[str] = None
    
    @property
    def name(self) -> str:
        return "manage_file_context"
    
    def set_workspace_dir(self, workspace_dir: str) -> None:
        if self.workspace_dir == workspace_dir:
            return
        self.workspace_dir = workspace_dir
        logger.info(f"File context tool workspace set to: {workspace_dir}")
    
    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "manage_file_context",
                "description": (
                    "Manage file context for dynamic inclusion in system prompts. "
                    "Opens files to include their content in the context, or closes files to remove them. "
                    "File contents are automatically loaded and included in the system prompt for each LLM call. "
                    "Use this when you need to keep certain files' content available in context without repeatedly reading them."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["open", "close", "close_all", "list"],
                            "description": (
                                "Action to perform: "
                                "'open' - open files for context inclusion, "
                                "'close' - close specific files, "
                                "'close_all' - close all open files, "
                                "'list' - list currently open files"
                            )
                        },
                        "files": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": (
                                "List of file paths to open or close. "
                                "Can be absolute paths or relative to workspace. "
                                "Required for 'open' and 'close' actions, ignored for others."
                            )
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["persistent", "temporary"],
                            "default": "persistent",
                            "description": (
                                "File open mode (only for 'open' action): "
                                "'persistent' - file stays open until explicitly closed (default), "
                                "'temporary' - file is only open for this iteration, auto-closed after use"
                            )
                        }
                    },
                    "required": ["action"]
                }
            }
        }
    
    def get_call_notification(self, tool_args: Dict[str, Any]) -> Optional[str]:
        """Return a simple notification message."""
        action = tool_args.get("action", "unknown")
        files = tool_args.get("files", [])
        
        if action == "open":
            file_count = len(files) if files else 0
            mode = tool_args.get("mode", "persistent")
            return f"Opening {file_count} file(s) for context ({mode} mode)"
        elif action == "close":
            file_count = len(files) if files else 0
            return f"Closing {file_count} file(s)"
        elif action == "close_all":
            return "Closing all open files"
        elif action == "list":
            return "Listing open files"
        return None
    
    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[str]:
        """Return a simple notification message."""
        action = tool_result.get("action", "unknown")
        success = tool_result.get("success", False)
        
        if not success:
            error = tool_result.get("error", "Unknown error")
            return f"File context operation failed: {error}"
        
        if action == "open":
            opened = tool_result.get("opened", [])
            failed = tool_result.get("failed", [])
            parts = []
            if opened:
                parts.append(f"Opened {len(opened)} file(s)")
            if failed:
                parts.append(f"Failed to open {len(failed)} file(s)")
            return " | ".join(parts) if parts else "No files to open"
        elif action == "close":
            closed = tool_result.get("closed", [])
            return f"Closed {len(closed)} file(s)" if closed else "No files to close"
        elif action == "close_all":
            count = tool_result.get("closed_count", 0)
            return f"Closed all {count} file(s)"
        elif action == "list":
            files = tool_result.get("files", [])
            return f"{len(files)} file(s) currently open"
        
        return None
    
    async def execute(
        self,
        action: str,
        files: Optional[List[str]] = None,
        mode: str = "persistent"
    ) -> Dict[str, Any]:
        """
        Execute file context management action.
        
        Args:
            action: Action to perform ("open", "close", "close_all", "list")
            files: List of file paths (required for "open" and "close")
            mode: File open mode ("persistent" or "temporary", only for "open")
        
        Returns:
            Dictionary with execution results
        """
        if not self.workspace_dir:
            return {
                "success": False,
                "error": "Workspace directory not set",
                "action": action
            }
        
        manager = get_file_context_manager(self.workspace_dir)
        
        try:
            if action == "open":
                if not files:
                    return {
                        "success": False,
                        "error": "No files provided for open action",
                        "action": action
                    }
                
                # Parse mode
                open_mode = FileOpenMode.PERSISTENT if mode == "persistent" else FileOpenMode.TEMPORARY
                
                opened = []
                failed = []
                
                for file_path in files:
                    if manager.open_file(file_path, open_mode):
                        opened.append(file_path)
                    else:
                        failed.append(file_path)
                
                return {
                    "success": True,
                    "action": action,
                    "opened": opened,
                    "failed": failed,
                    "mode": mode
                }
            
            elif action == "close":
                if not files:
                    return {
                        "success": False,
                        "error": "No files provided for close action",
                        "action": action
                    }
                
                closed = []
                for file_path in files:
                    if manager.close_file(file_path):
                        closed.append(file_path)
                
                return {
                    "success": True,
                    "action": action,
                    "closed": closed
                }
            
            elif action == "close_all":
                open_files = manager.get_open_files()
                count = len(open_files)
                manager.close_all_files()
                
                return {
                    "success": True,
                    "action": action,
                    "closed_count": count
                }
            
            elif action == "list":
                open_files = manager.get_open_files()
                
                return {
                    "success": True,
                    "action": action,
                    "files": open_files,
                    "count": len(open_files)
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "action": action
                }
        
        except Exception as e:
            error_msg = f"Error executing file context action: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "action": action
            }

