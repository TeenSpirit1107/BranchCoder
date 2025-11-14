#!/usr/bin/env python3
"""
Command Tool - Execute shell commands in the workspace
"""

import asyncio
import re
import os
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from utils.logger import Logger
from tools.base_tool import MCPTool

logger = Logger('command_tool', log_to_file=False)


class CommandTool(MCPTool):
    """Tool for executing shell commands."""
    
    def __init__(self):
        """Initialize command tool."""
        self.workspace_dir: Optional[str] = None
    
    def set_workspace_dir(self, workspace_dir: str):
        """
        Set the workspace directory. Commands will be executed in this directory.
        
        Args:
            workspace_dir: Path to workspace directory
        """
        if self.workspace_dir == workspace_dir:
            return
        
        self.workspace_dir = workspace_dir
        logger.info(f"Setting workspace directory for command tool: {workspace_dir}")
    
    def _validate_path_safety(self, command: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that command doesn't attempt to escape workspace directory.
        
        Args:
            command: The command to validate
        
        Returns:
            Tuple of (is_safe, error_message)
        """
        if not self.workspace_dir:
            return False, "Workspace directory not set. Cannot execute commands without workspace boundary."
        
        workspace_path = Path(self.workspace_dir).resolve()
        if not workspace_path.exists() or not workspace_path.is_dir():
            return False, f"Workspace directory does not exist or is not a directory: {self.workspace_dir}"
        
        # Patterns that indicate path traversal attempts
        # More specific patterns to avoid false positives
        dangerous_patterns = [
            (r'\.\./', r'\.\./'),           # ../
            (r'\.\.\\', r'\.\.\\'),         # ..\ (Windows)
            (r'(?:^|\s)\.\.(?:\s|$|/)', r'\.\.'),  # .. as standalone or before /
            (r'~/', r'~/'),                 # Home directory expansion
            (r'\$HOME', r'\$HOME'),         # $HOME variable
            (r'\$\{HOME\}', r'\$\{HOME\}'), # ${HOME} variable
            (r'\$PWD', r'\$PWD'),           # $PWD variable
            (r'\$\{PWD\}', r'\$\{PWD\}'),   # ${PWD} variable
        ]
        
        # Check for dangerous patterns
        for pattern, pattern_name in dangerous_patterns:
            if re.search(pattern, command):
                return False, f"Command contains dangerous path pattern '{pattern_name}': {command}"
        
        # Extract potential file paths from common commands
        # This is a heuristic approach - we look for arguments that might be paths
        path_indicators = [
            r'(?:^|\s)(?:cat|ls|cd|rm|mv|cp|mkdir|rmdir|touch|chmod|chown|grep|find|python|python3|node|npm|git)\s+([^\s&|;]+)',
            r'(?:^|\s)(?:<|>|>>)\s*([^\s&|;]+)',  # Redirection operators
        ]
        
        extracted_paths = []
        for pattern in path_indicators:
            matches = re.finditer(pattern, command)
            for match in matches:
                if match.lastindex:
                    potential_path = match.group(1).strip()
                    # Remove quotes
                    potential_path = potential_path.strip('"\'')
                    if potential_path and not potential_path.startswith('-'):
                        extracted_paths.append(potential_path)
        
        # Validate extracted paths
        for path_str in extracted_paths:
            # Skip if it's clearly not a path (e.g., command options, URLs)
            if any(skip in path_str for skip in ['http://', 'https://', '://', '--', '-']):
                continue
            
            try:
                # Resolve path relative to workspace
                if os.path.isabs(path_str):
                    # Absolute path - check if it's within workspace
                    abs_path = Path(path_str).resolve()
                    try:
                        abs_path.relative_to(workspace_path)
                    except ValueError:
                        return False, f"Command attempts to access path outside workspace: {path_str}"
                else:
                    # Relative path - resolve it and check
                    resolved = (workspace_path / path_str).resolve()
                    try:
                        resolved.relative_to(workspace_path)
                    except ValueError:
                        return False, f"Command attempts to access path outside workspace: {resolved}"
            except Exception as e:
                # If path resolution fails, log but don't block (might be a non-path argument)
                logger.debug(f"Could not resolve path '{path_str}': {e}")
        
        return True, None
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "execute_command"
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": "execute_command",
                "description": "Execute a shell command in the workspace. Use this to run terminal commands, check file contents, list directories, etc. Be careful with destructive commands.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The shell command to execute (e.g., 'ls -la', 'cat file.txt', 'python script.py')"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds (default: 30)",
                            "default": 30
                        }
                    },
                    "required": ["command"]
                }
            }
        }
    
    async def execute(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute a shell command.
        
        Args:
            command: The command to execute
            timeout: Timeout in seconds
        
        Returns:
            Dictionary with stdout, stderr, returncode, and success status
        """
        logger.info(f"Executing command: {command}")
        
        # Validate path safety - ensure command stays within workspace
        is_safe, error_msg = self._validate_path_safety(command)
        if not is_safe:
            logger.warning(f"Command blocked by path fence: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "command": command
            }
        
        # Determine working directory
        cwd = None
        if self.workspace_dir:
            workspace_path = Path(self.workspace_dir)
            if workspace_path.exists() and workspace_path.is_dir():
                cwd = str(workspace_path.resolve())
                logger.debug(f"Using workspace directory as cwd: {cwd}")
            else:
                logger.warning(f"Workspace directory does not exist or is not a directory: {self.workspace_dir}")
                return {
                    "success": False,
                    "error": f"Workspace directory does not exist or is not a directory: {self.workspace_dir}",
                    "command": command
                }
        else:
            # Workspace directory must be set
            logger.warning("Command execution blocked: workspace directory not set")
            return {
                "success": False,
                "error": "Workspace directory not set. Cannot execute commands without workspace boundary.",
                "command": command
            }
        
        try:
            # Run command asynchronously
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True,
                cwd=cwd  # Set working directory to workspace_dir if available
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                stdout_str = stdout.decode('utf-8', errors='replace')
                stderr_str = stderr.decode('utf-8', errors='replace')
                returncode = process.returncode
                
                logger.info(f"Command completed with return code: {returncode}")
                
                return {
                    "success": returncode == 0,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "returncode": returncode,
                    "command": command
                }
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                logger.warning(f"Command timed out after {timeout} seconds")
                return {
                    "success": False,
                    "error": f"Command timed out after {timeout} seconds",
                    "command": command
                }
        except Exception as e:
            logger.error(f"Error executing command: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "command": command
            }

