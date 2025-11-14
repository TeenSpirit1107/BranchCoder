#!/usr/bin/env python3
"""
Command Tool - Execute shell commands in the workspace
"""

import asyncio
from typing import Dict, Any, Optional
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
        
        # Determine working directory
        cwd = None
        if self.workspace_dir:
            workspace_path = Path(self.workspace_dir)
            if workspace_path.exists() and workspace_path.is_dir():
                cwd = str(workspace_path.resolve())
                logger.debug(f"Using workspace directory as cwd: {cwd}")
            else:
                logger.warning(f"Workspace directory does not exist or is not a directory: {self.workspace_dir}")
        
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

