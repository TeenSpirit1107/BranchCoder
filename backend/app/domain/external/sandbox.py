from typing import Optional, Protocol, Dict

from app.domain.models.tool_result import ToolResult


class Sandbox(Protocol):
    """Sandbox service gateway interface"""
    
    async def exec_command(
        self,
        session_id: str,
        exec_dir: str,
        command: str
    ) -> ToolResult:
        """Execute command
        
        Args:
            session_id: Session ID
            exec_dir: Execution directory
            command: Command to execute
            
        Returns:
            Command execution result
        """
        ...
    
    async def view_shell(self, session_id: str) -> ToolResult:
        """View shell status
        
        Args:
            session_id: Session ID
            
        Returns:
            Shell status information
        """
        ...
    
    async def wait_for_process(
        self,
        session_id: str,
        seconds: Optional[int] = None
    ) -> ToolResult:
        """Wait for process
        
        Args:
            session_id: Session ID
            seconds: Wait seconds
            
        Returns:
            Wait result
        """
        ...
    
    async def write_to_process(
        self,
        session_id: str,
        input_text: str,
        press_enter: bool = True
    ) -> ToolResult:
        """Write input to process
        
        Args:
            session_id: Session ID
            input_text: Input text
            press_enter: Whether to press enter
            
        Returns:
            Write result
        """
        ...
    
    async def kill_process(self, session_id: str) -> ToolResult:
        """Terminate process
        
        Args:
            session_id: Session ID
            
        Returns:
            Termination result
        """
        ...
    
    async def file_write(
        self, 
        file: str, 
        content: str, 
        append: bool = False, 
        leading_newline: bool = False, 
        trailing_newline: bool = False, 
        sudo: bool = False
    ) -> ToolResult:
        """Write content to file
        
        Args:
            file: File path
            content: Content to write
            append: Whether to append content
            leading_newline: Whether to add newline before content
            trailing_newline: Whether to add newline after content
            sudo: Whether to use sudo privileges
            
        Returns:
            Write operation result
        """
        ...
    
    async def file_read(
        self, 
        file: str, 
        start_line: int = None, 
        end_line: int = None, 
        sudo: bool = False
    ) -> ToolResult:
        """Read file content
        
        Args:
            file: File path
            start_line: Start line number
            end_line: End line number
            sudo: Whether to use sudo privileges
            
        Returns:
            File content
        """
        ...
    
    async def file_exists(self, path: str) -> ToolResult:
        """Check if file exists
        
        Args:
            path: File path
            
        Returns:
            Whether file exists
        """
        ...
    
    async def file_delete(self, path: str) -> ToolResult:
        """Delete file
        
        Args:
            path: File path
            
        Returns:
            Delete operation result
        """
        ...
    
    async def file_list(self, path: str) -> ToolResult:
        """List directory contents
        
        Args:
            path: Directory path
            
        Returns:
            Directory content list
        """
        ...
    
    async def file_replace(
        self, 
        file: str, 
        old_str: str, 
        new_str: str, 
        sudo: bool = False
    ) -> ToolResult:
        """Replace string in file
        
        Args:
            file: File path
            old_str: String to replace
            new_str: Replacement string
            sudo: Whether to use sudo privileges
            
        Returns:
            Replace operation result
        """
        ...
    
    async def file_search(
        self, 
        file: str, 
        regex: str, 
        sudo: bool = False
    ) -> ToolResult:
        """Search in file content
        
        Args:
            file: File path
            regex: Regular expression
            sudo: Whether to use sudo privileges
            
        Returns:
            Search result
        """
        ...
    
    async def file_find(
        self, 
        path: str, 
        glob_pattern: str
    ) -> ToolResult:
        """Find files by name pattern
        
        Args:
            path: Search directory path
            glob_pattern: Glob matching pattern
            
        Returns:
            Found file list
        """
        ...
    
    async def file_upload(
        self, 
        file_path: str, 
        content: bytes, 
        make_executable: bool = False
    ) -> ToolResult:
        """Upload file
        
        Args:
            file_path: Target file path in sandbox
            content: Binary file content
            make_executable: Whether to make file executable
            
        Returns:
            Upload result
        """
        ...

    async def file_download(self, file_path: str) -> bytes:
        """Download file
        
        Args:
            file_path: File path in sandbox
            
        Returns:
            Binary file content
            
        Raises:
            FileNotFoundError: When file does not exist
            PermissionError: When permission is denied
            Exception: Other errors
        """
        ...

    async def get_status(self) -> ToolResult:
        """Get sandbox status, check if all services are running properly
        
        Returns:
            Sandbox status information
        """
        ...

    async def ensure_status(self) -> ToolResult:
        """Ensure sandbox status is normal
        
        Returns:
            Sandbox status
        """
        ...
    
    def get_cdp_url(self) -> str:
        """Get Chrome DevTools Protocol URL
        
        Returns:
            CDP URL string
        """
        ...
    
    def get_vnc_url(self) -> str:
        """Get VNC URL
        
        Returns:
            VNC URL string
        """
        ...

    def get_code_server_url(self) -> str:
        """Get Code Server URL
        
        Returns:
            Code Server URL string
        """
        ...
    
    # MCP Service Management Methods
    async def mcp_install(
        self, 
        pkg: str, 
        lang: str, 
        args: Optional[list] = None
    ) -> ToolResult:
        """Install and start MCP server
        
        Args:
            pkg: MCP package name
            lang: Programming language type ("python" or "node")
            args: Optional startup arguments list
            
        Returns:
            Installation result
        """
        ...
    
    async def mcp_uninstall(self, pkg: str) -> ToolResult:
        """Stop and uninstall MCP server
        
        Args:
            pkg: MCP package name
            
        Returns:
            Uninstallation result
        """
        ...
    
    async def mcp_list_servers(self) -> ToolResult:
        """List all installed MCP servers
        
        Returns:
            Server list result with status information for each server
        """
        ...
    
    async def mcp_health_check(self, pkg: str) -> ToolResult:
        """Check MCP server health status
        
        Args:
            pkg: MCP package name
            
        Returns:
            Health status result
        """
        ...
    
    async def mcp_proxy_request(
        self, 
        pkg: str, 
        request: Dict
    ) -> ToolResult:
        """Proxy JSON-RPC request to MCP server
        
        Args:
            pkg: Target MCP server package name
            request: JSON-RPC request data
            
        Returns:
            Server response result
        """
        ...
    
    async def mcp_get_capabilities(self, pkg: str) -> ToolResult:
        """Get MCP server capability information
        
        Args:
            pkg: MCP package name
            
        Returns:
            Server capability information result
        """
        ...
    
    async def mcp_shutdown_all(self) -> ToolResult:
        """Shutdown all MCP servers
        
        Returns:
            Shutdown operation result
        """
        ...
    
    async def close(self):
        """Close gateway connection and clean up resources"""
        ... 