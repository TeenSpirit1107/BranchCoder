#!/usr/bin/env python3
"""
Workspace Structure Tool - Get file structure of the workspace
"""

import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from utils.logger import Logger
from tools.base_tool import MCPTool

logger = Logger('workspace_structure_tool', log_to_file=False)


class WorkspaceStructureTool(MCPTool):
    """Tool for getting the file structure of the workspace."""
    
    @property
    def agent_tool(self) -> bool:
        """This tool is not exposed to LLM agent (internal use only)."""
        return False
    
    # Default ignore patterns
    DEFAULT_IGNORE_PATTERNS = [
        '__pycache__',
        '.git',
        '.pytest_cache',
        '.mypy_cache',
        'node_modules',
        '.venv',
        'venv',
        'env',
        '.env',
        '*.pyc',
        '*.pyo',
        '*.pyd',
        '.DS_Store',
        '*.egg-info',
        'dist',
        'build',
        '.rag_store',
    ]
    
    def __init__(self):
        """Initialize workspace structure tool."""
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
        logger.info(f"Setting workspace directory for workspace structure tool: {workspace_dir}")
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "get_workspace_structure"
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": "get_workspace_structure",
                "description": "Get the file and directory structure of the workspace. Returns a tree-like representation of the workspace files and folders. Useful for understanding the project layout.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "max_depth": {
                            "type": "integer",
                            "description": "Maximum depth to traverse (default: 5, 0 means unlimited)",
                            "default": 5
                        },
                        "include_files": {
                            "type": "boolean",
                            "description": "Whether to include files in the structure (default: True)",
                            "default": True
                        },
                        "include_hidden": {
                            "type": "boolean",
                            "description": "Whether to include hidden files/directories (default: False)",
                            "default": False
                        }
                    },
                    "required": []
                }
            }
        }
    
    def _should_ignore(self, path: Path, ignore_patterns: List[str], include_hidden: bool) -> bool:
        """
        Check if a path should be ignored.
        
        Args:
            path: Path to check
            ignore_patterns: List of patterns to ignore
            include_hidden: Whether to include hidden files
        
        Returns:
            True if path should be ignored
        """
        path_str = str(path)
        name = path.name
        
        # Check hidden files
        if not include_hidden and name.startswith('.'):
            return True
        
        # Check ignore patterns
        for pattern in ignore_patterns:
            if pattern in path_str or name == pattern or name.endswith(pattern.lstrip('*')):
                return True
        
        return False
    
    def _build_tree(self, root: Path, prefix: str = "", is_last: bool = True, 
                    max_depth: int = 5, current_depth: int = 0,
                    include_files: bool = True, include_hidden: bool = False,
                    ignore_patterns: List[str] = None) -> List[str]:
        """
        Build a tree representation of the directory structure.
        
        Args:
            root: Root directory path
            prefix: Prefix for current line
            is_last: Whether this is the last item in parent
            max_depth: Maximum depth to traverse
            current_depth: Current depth level
            include_files: Whether to include files
            include_hidden: Whether to include hidden files
            ignore_patterns: List of patterns to ignore
        
        Returns:
            List of tree lines
        """
        if ignore_patterns is None:
            ignore_patterns = self.DEFAULT_IGNORE_PATTERNS
        
        lines = []
        
        # Check if we should ignore this path
        if self._should_ignore(root, ignore_patterns, include_hidden):
            return lines
        
        # Check depth limit
        if max_depth > 0 and current_depth >= max_depth:
            return lines
        
        # Get the display name
        if current_depth == 0:
            display_name = str(root)
        else:
            display_name = root.name
        
        # Add current item
        connector = "└── " if is_last else "├── "
        lines.append(prefix + connector + display_name)
        
        # Update prefix for children
        extension = "    " if is_last else "│   "
        new_prefix = prefix + extension
        
        # Get children
        try:
            if root.is_dir():
                children = sorted([p for p in root.iterdir()], 
                                key=lambda p: (p.is_file(), p.name.lower()))
                
                # Filter children
                filtered_children = []
                for child in children:
                    if not self._should_ignore(child, ignore_patterns, include_hidden):
                        if child.is_dir() or include_files:
                            filtered_children.append(child)
                
                # Recursively add children
                for i, child in enumerate(filtered_children):
                    is_last_child = (i == len(filtered_children) - 1)
                    child_lines = self._build_tree(
                        child, new_prefix, is_last_child,
                        max_depth, current_depth + 1,
                        include_files, include_hidden, ignore_patterns
                    )
                    lines.extend(child_lines)
        except PermissionError:
            lines.append(new_prefix + "    [Permission Denied]")
        except Exception as e:
            logger.warning(f"Error accessing {root}: {e}")
            lines.append(new_prefix + f"    [Error: {str(e)}]")
        
        return lines
    
    async def execute(self, max_depth: int = 5, include_files: bool = True, 
                     include_hidden: bool = False) -> Dict[str, Any]:
        """
        Get the workspace file structure.
        
        Args:
            max_depth: Maximum depth to traverse (0 means unlimited)
            include_files: Whether to include files in the structure
            include_hidden: Whether to include hidden files/directories
        
        Returns:
            Dictionary with structure tree and metadata
        """
        # Determine workspace directory
        workspace_path = None
        if self.workspace_dir:
            workspace_path = Path(self.workspace_dir)
            if not workspace_path.exists() or not workspace_path.is_dir():
                logger.warning(f"Workspace directory does not exist or is not a directory: {self.workspace_dir}")
                return {
                    "error": f"Workspace directory does not exist or is not a directory: {self.workspace_dir}",
                    "workspace_dir": self.workspace_dir
                }
        else:
            # Use current working directory
            workspace_path = Path.cwd()
            logger.info(f"No workspace directory set, using current directory: {workspace_path}")
        
        try:
            workspace_path = workspace_path.resolve()
            logger.info(f"Getting workspace structure for: {workspace_path}")
            
            # Build tree structure
            tree_lines = self._build_tree(
                workspace_path,
                max_depth=max_depth,
                current_depth=0,
                include_files=include_files,
                include_hidden=include_hidden
            )
            
            # Combine into a single string
            tree_str = "\n".join(tree_lines) if tree_lines else "[Empty directory]"
            
            # Count files and directories
            file_count = 0
            dir_count = 0
            
            def count_items(path: Path, depth: int = 0):
                nonlocal file_count, dir_count
                
                if max_depth > 0 and depth >= max_depth:
                    return
                
                if self._should_ignore(path, self.DEFAULT_IGNORE_PATTERNS, include_hidden):
                    return
                
                try:
                    if path.is_dir():
                        dir_count += 1
                        for child in path.iterdir():
                            if not self._should_ignore(child, self.DEFAULT_IGNORE_PATTERNS, include_hidden):
                                if child.is_dir():
                                    count_items(child, depth + 1)
                                elif include_files:
                                    file_count += 1
                    elif include_files:
                        file_count += 1
                except (PermissionError, OSError):
                    pass
            
            count_items(workspace_path)
            
            return {
                "success": True,
                "workspace_dir": str(workspace_path),
                "structure": tree_str,
                "file_count": file_count,
                "directory_count": dir_count,
                "max_depth": max_depth,
                "include_files": include_files,
                "include_hidden": include_hidden
            }
            
        except Exception as e:
            logger.error(f"Error getting workspace structure: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "workspace_dir": str(workspace_path) if workspace_path else None
            }

