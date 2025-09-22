"""
MCP (Model Context Protocol) Tool

Tool for managing and interacting with MCP servers in the sandbox environment.
Supports installing, uninstalling, listing, and communicating with MCP servers.
This is a dynamic tool that can discover and expose tools from installed MCP servers.
"""
import json
import logging
from typing import Dict, Any, Optional, List, Union
import asyncio

from app.domain.models.tool_result import ToolResult
from app.domain.services.tools.base import BaseTool, tool
from app.domain.external.sandbox import Sandbox

logger = logging.getLogger(__name__)


class McpServerConfig:
    """Configuration for an MCP server to be pre-installed."""
    
    def __init__(
        self,
        package_name: str,
        language: str = "python",
        args: Optional[List[str]] = None,
        description: Optional[str] = None
    ):
        """Initialize MCP server configuration.
        
        Args:
            package_name: Name of the MCP package to install
            language: Programming language ("python" or "node")
            args: Optional list of arguments to pass to the server
            description: Optional description for logging
        """
        self.package_name = package_name
        self.language = language
        self.args = args or []
        self.description = description or package_name


class McpTool(BaseTool):
    """Dynamic tool for managing MCP (Model Context Protocol) servers and exposing their tools."""

    name: str = "mcp"

    def __init__(
        self, 
        sandbox: Sandbox,
        pre_install_servers: Optional[List[Union[str, Dict[str, Any], McpServerConfig]]] = None
    ):
        """Initialize MCP tool with sandbox interface and optional pre-installed servers.
        
        Args:
            sandbox: Sandbox interface for MCP operations
            pre_install_servers: Optional list of servers to pre-install. Can be:
                - List of package names (strings)
                - List of dictionaries with server config
                - List of McpServerConfig objects
                Example:
                    ["mcp-filesystem", "mcp-brave-search"]
                    [{"package_name": "mcp-filesystem", "language": "python"}]
                    [McpServerConfig("mcp-filesystem", "python", ["/home/ubuntu"])]
        """
        super().__init__()
        self.sandbox = sandbox
        self._dynamic_tools_cache = None
        self._pre_install_servers = self._parse_pre_install_servers(pre_install_servers or [])
        self._initialized = False
        self._initialization_results = []

    def _parse_pre_install_servers(
        self, 
        pre_install_servers: List[Union[str, Dict[str, Any], McpServerConfig]]
    ) -> List[McpServerConfig]:
        """Parse and normalize pre-install servers configuration.
        
        Args:
            pre_install_servers: List of server configurations in various formats
            
        Returns:
            List of normalized McpServerConfig objects
        """
        configs = []
        
        for server in pre_install_servers:
            try:
                if isinstance(server, str):
                    # Simple package name
                    configs.append(McpServerConfig(server))
                elif isinstance(server, dict):
                    # Dictionary configuration
                    package_name = server.get("package_name")
                    if not package_name:
                        logger.warning(f"Skipping server config without package_name: {server}")
                        continue
                    
                    configs.append(McpServerConfig(
                        package_name=package_name,
                        language=server.get("language", "python"),
                        args=server.get("args"),
                        description=server.get("description")
                    ))
                elif isinstance(server, McpServerConfig):
                    # Already a proper config object
                    configs.append(server)
                else:
                    logger.warning(f"Skipping invalid server config: {server}")
            except Exception as e:
                logger.error(f"Error parsing server config {server}: {e}")
                
        return configs

    async def initialize(self) -> bool:
        """Initialize the MCP tool by pre-installing configured servers.
        
        This method should be called after creating the McpTool instance
        to install any pre-configured MCP servers.
        
        Returns:
            Initialization result with details about installed servers
        """
        if self._initialized:
            return True

        logger.info(f"Initializing MCP tool with {len(self._pre_install_servers)} pre-install servers")
        
        installation_results = []
        successful_installs = 0
        failed_installs = 0

        for server_config in self._pre_install_servers:
            try:
                logger.info(f"Pre-installing MCP server: {server_config.description}")
                
                result = await self.install_server(
                    package_name=server_config.package_name,
                    language=server_config.language,
                    args=server_config.args
                )
                
                installation_results.append({
                    "package_name": server_config.package_name,
                    "success": result.success,
                    "message": result.message,
                    "language": server_config.language
                })
                
                if result.success:
                    successful_installs += 1
                    logger.info(f"Successfully pre-installed: {server_config.package_name}")
                else:
                    failed_installs += 1
                    logger.error(f"Failed to pre-install {server_config.package_name}: {result.message}")
                    
            except Exception as e:
                failed_installs += 1
                error_msg = f"Error pre-installing {server_config.package_name}: {str(e)}"
                logger.error(error_msg)
                installation_results.append({
                    "package_name": server_config.package_name,
                    "success": False,
                    "message": error_msg,
                    "language": server_config.language
                })

        self._initialization_results = installation_results
        self._initialized = True

        # 清除缓存以确保新安装的工具被发现
        self.invalidate_cache()

        total_servers = len(self._pre_install_servers)
        if total_servers == 0:
            message = "MCP tool initialized with no pre-install servers"
        elif failed_installs == 0:
            message = f"MCP tool initialized successfully. All {successful_installs} servers installed."
        elif successful_installs == 0:
            message = f"MCP tool initialized with warnings. All {failed_installs} server installations failed."
        else:
            message = f"MCP tool initialized with warnings. {successful_installs} succeeded, {failed_installs} failed."

        logger.info(message)

        return failed_installs < total_servers

    async def _get_dynamic_tools(self) -> List[Dict[str, Any]]:
        """Get all tools from installed MCP servers dynamically.
        
        Returns:
            List of dynamic tools from MCP servers
        """
        if self._dynamic_tools_cache is not None:
            return self._dynamic_tools_cache
        
        # 确保初始化
        await self.initialize()

        dynamic_tools = []
        
        try:
            # 获取所有已安装的MCP服务器
            servers_result = await self.sandbox.mcp_list_servers()
            if not servers_result.success or not servers_result.data:
                logger.debug("No MCP servers found or failed to list servers")
                self._dynamic_tools_cache = []
                return []

            servers = servers_result.data
            
            for server in servers:
                package_name = server.get("pkg")
                alive = server.get("alive")
                
                if not package_name or not alive:
                    continue
                
                try:
                    # 获取服务器的工具列表
                    tools_result = await self.sandbox.mcp_get_capabilities(package_name)
                    if tools_result.success and tools_result.data:
                        tools = tools_result.data.get("tools", [])
                        
                        for tool_info in tools:
                            tool_name = tool_info.get("name")
                            if not tool_name:
                                continue
                            
                            # 构造动态工具的schema
                            dynamic_tool = {
                                "type": "function",
                                "function": {
                                    "name": f"mcp_{package_name}_{tool_name}",
                                    "description": f"[MCP:{package_name}] {tool_info.get('description', tool_name)}",
                                    "parameters": tool_info.get('inputSchema', {
                                        "type": "object",
                                        "properties": {},
                                        "required": []
                                    })
                                }
                            }
                            
                            dynamic_tools.append(dynamic_tool)
                            
                except Exception as e:
                    logger.error(f"Failed to get tools from MCP server {package_name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error getting dynamic MCP tools: {e}")
        
        self._dynamic_tools_cache = dynamic_tools
        return dynamic_tools

    async def get_tools(self) -> List[Dict[str, Any]]:
        """Get all tools including dynamic MCP tools (async version).
        
        Returns:
            List of all tools including dynamic ones
        """
        static_tools = await super().get_tools()
        dynamic_tools = await self._get_dynamic_tools()
        return static_tools + dynamic_tools

    async def has_function(self, function_name: str) -> bool:
        """Check if specified function exists (async version for dynamic tools).
        
        Args:
            function_name: Function name
            
        Returns:
            Whether the tool exists
        """
        # 先检查静态工具
        if await (super().has_function(function_name)):
            return True
        
        # 检查动态工具
        if function_name.startswith("mcp_"):
            dynamic_tools = await self._get_dynamic_tools()
            for tool in dynamic_tools:
                if tool["function"]["name"] == function_name:
                    return True
        
        return False

    async def invoke_function(self, function_name: str, **kwargs) -> ToolResult:
        """Invoke specified tool (supports both static and dynamic tools).
        
        Args:
            function_name: Function name
            **kwargs: Parameters
            
        Returns:
            Invocation result
            
        Raises:
            ValueError: Raised when tool doesn't exist
        """
        # 确保初始化
        await self.initialize()

        # 先尝试调用静态工具
        try:
            return await super().invoke_function(function_name, **kwargs)
        except ValueError:
            pass
        
        # 尝试调用动态MCP工具
        if function_name.startswith("mcp_"):
            try:
                # 为了稳健地解析包名和工具名（即使它们包含下划线），
                # 我们从缓存的工具定义中查找函数，并从其描述中提取包名。
                dynamic_tools = await self._get_dynamic_tools()
                target_tool_schema = next(
                    (t for t in dynamic_tools if t.get("function", {}).get("name") == function_name),
                    None
                )

                if not target_tool_schema:
                    raise ValueError(f"Tool '{function_name}' not found among dynamic MCP tools.")

                description = target_tool_schema["function"].get("description", "")
                # 描述格式为: "[MCP:{package_name}] {description}"
                if not description.startswith("[MCP:") or "]" not in description:
                    raise ValueError(
                        f"Could not determine package name for MCP tool '{function_name}' from description."
                    )

                start_index = 5  # len("[MCP:")
                end_index = description.find("]")
                package_name = description[start_index:end_index]
                
                prefix = f"mcp_{package_name}_"
                if not function_name.startswith(prefix):
                    # 正常情况下不应发生，作为安全措施
                    raise ValueError(
                        f"Mismatch between function name '{function_name}' and package name '{package_name}'."
                    )

                tool_name = function_name[len(prefix):]
                
                return await self.call_tool(package_name, tool_name, kwargs)
            except Exception as e:
                return ToolResult(success=False, message=f"Error calling MCP tool {function_name}: {str(e)}")
        
        raise ValueError(f"Tool '{function_name}' not found")

    def invalidate_cache(self):
        """Invalidate the dynamic tools cache to force refresh."""
        self._dynamic_tools_cache = None
        self._tools_cache = None

    @tool(
        name="mcp_install_server",
        description="Install and start an MCP server in the sandbox environment",
        parameters={
            "package_name": {
                "type": "string",
                "description": "Name of the MCP package to install (e.g., 'mcp-filesystem', '@modelcontextprotocol/server-filesystem')"
            },
            "language": {
                "type": "string",
                "description": "Programming language of the server",
                "enum": ["python", "node"],
                "default": "python"
            },
            "args": {
                "type": "array",
                "description": "Optional list of arguments to pass to the server",
                "items": {"type": "string"},
                "default": []
            }
        },
        required=["package_name"]
    )
    async def install_server(
        self, 
        package_name: str, 
        language: str = "python", 
        args: Optional[List[str]] = None
    ) -> ToolResult:
        """Install and start an MCP server.
        
        Args:
            package_name: Name of the MCP package to install
            language: Programming language ("python" or "node")
            args: Optional list of arguments to pass to the server
            
        Returns:
            Installation result
        """
        try:
            logger.info(f"Installing MCP server: {package_name} ({language})")
            
            result = await self.sandbox.mcp_install(
                pkg=package_name,
                lang=language,
                args=args
            )
            
            # 安装成功后清除缓存，强制重新获取工具列表
            if result.success:
                logger.info(f"Successfully installed MCP server: {package_name}")
                self.invalidate_cache()
            else:
                logger.error(f"Failed to install MCP server {package_name}: {result.message}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error installing MCP server {package_name}: {str(e)}"
            logger.error(error_msg)
            return ToolResult(success=False, message=error_msg)

    @tool(
        name="mcp_get_capabilities",
        description="Get the capabilities of a specific MCP server",
        parameters={
            "package_name": {
                "type": "string",
                "description": "Name of the MCP package"
            }
        },
        required=["package_name"]
    )
    async def get_capabilities(self, package_name: str) -> ToolResult:
        """Get the capabilities of an MCP server.
        
        Args:
            package_name: Name of the MCP package
            
        Returns:
            Server capabilities information
        """
        try:
            # 确保初始化
            await self.initialize()

            logger.debug(f"Getting capabilities of MCP server: {package_name}")
            
            result = await self.sandbox.mcp_get_capabilities(pkg=package_name)
            
            return result
            
        except Exception as e:
            error_msg = f"Error getting MCP server capabilities {package_name}: {str(e)}"
            logger.error(error_msg)
            return ToolResult(success=False, message=error_msg)

    @tool(
        name="mcp_list_tools",
        description="List all tools available in a specific MCP server",
        parameters={
            "package_name": {
                "type": "string",
                "description": "Name of the MCP package"
            }
        },
        required=["package_name"]
    )
    async def list_tools(self, package_name: str) -> ToolResult:
        """List tools available in an MCP server.
        
        Args:
            package_name: Name of the MCP package
            
        Returns:
            Available tools list
        """
        try:
            # 确保初始化
            await self.initialize()

            logger.debug(f"Listing tools for MCP server: {package_name}")
            
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            
            result = await self.sandbox.mcp_proxy_request(
                pkg=package_name,
                request=request
            )
            
            if result.success and result.data:
                try:
                    response = result.data if isinstance(result.data, dict) else json.loads(result.data)
                    if "result" in response and "tools" in response["result"]:
                        tools = response["result"]["tools"]
                        tool_list = [
                            {
                                "name": tool.get("name"),
                                "description": tool.get("description", ""),
                                "inputSchema": tool.get("inputSchema", {})
                            }
                            for tool in tools
                        ]
                        return ToolResult(
                            success=True,
                            message=f"Found {len(tool_list)} tools",
                            data={"tools": tool_list}
                        )
                    else:
                        return ToolResult(success=False, message="Invalid response format")
                except json.JSONDecodeError as e:
                    return ToolResult(success=False, message=f"Failed to parse response: {e}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error listing tools for MCP server {package_name}: {str(e)}"
            logger.error(error_msg)
            return ToolResult(success=False, message=error_msg)

    async def call_tool(
        self, 
        package_name: str, 
        tool_name: str, 
        arguments: Dict[str, Any]
    ) -> ToolResult:
        """Call a specific tool on an MCP server.
        
        Args:
            package_name: Name of the MCP package
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result
        """
        try:
            # 确保初始化
            await self.initialize()

            logger.info(f"Calling tool {tool_name} on MCP server {package_name}")
            
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            result = await self.sandbox.mcp_proxy_request(
                pkg=package_name,
                request=request
            )
            
            if result.success and result.data:
                try:
                    response = result.data if isinstance(result.data, dict) else json.loads(result.data)
                    if "result" in response:
                        return ToolResult(
                            success=True,
                            message=f"Tool {tool_name} executed successfully",
                            data=response["result"]
                        )
                    elif "error" in response:
                        error = response["error"]
                        return ToolResult(
                            success=False,
                            message=f"Tool error: {error.get('message', 'Unknown error')}"
                        )
                    else:
                        return ToolResult(success=False, message="Invalid response format")
                except json.JSONDecodeError as e:
                    return ToolResult(success=False, message=f"Failed to parse response: {e}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error calling tool {tool_name} on MCP server {package_name}: {str(e)}"
            logger.error(error_msg)
            return ToolResult(success=False, message=error_msg)

    async def list_servers(self) -> ToolResult:
        """List all installed MCP servers and their status.
        
        Returns:
            Server list with status information
        """
        try:
            # 确保初始化
            await self.initialize()

            logger.debug("Listing MCP servers")
            
            result = await self.sandbox.mcp_list_servers()
            
            if result.success:
                logger.debug(f"Found MCP servers: {result.data}")
            else:
                logger.error(f"Failed to list MCP servers: {result.message}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error listing MCP servers: {str(e)}"
            logger.error(error_msg)
            return ToolResult(success=False, message=error_msg)

    async def list_resources(self, package_name: str) -> ToolResult:
        """List resources available in an MCP server.
        
        Args:
            package_name: Name of the MCP package
            
        Returns:
            Available resources list
        """
        try:
            # 确保初始化
            await self.initialize()

            logger.debug(f"Listing resources for MCP server: {package_name}")
            
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "resources/list",
                "params": {}
            }
            
            result = await self.sandbox.mcp_proxy_request(
                pkg=package_name,
                request=request
            )
            
            if result.success and result.data:
                try:
                    response = result.data if isinstance(result.data, dict) else json.loads(result.data)
                    if "result" in response and "resources" in response["result"]:
                        resources = response["result"]["resources"]
                        resource_list = [
                            {
                                "uri": resource.get("uri"),
                                "name": resource.get("name", ""),
                                "description": resource.get("description", ""),
                                "mimeType": resource.get("mimeType", "")
                            }
                            for resource in resources
                        ]
                        return ToolResult(
                            success=True,
                            message=f"Found {len(resource_list)} resources",
                            data={"resources": resource_list}
                        )
                    else:
                        return ToolResult(success=False, message="Invalid response format")
                except json.JSONDecodeError as e:
                    return ToolResult(success=False, message=f"Failed to parse response: {e}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error listing resources for MCP server {package_name}: {str(e)}"
            logger.error(error_msg)
            return ToolResult(success=False, message=error_msg)

    async def read_resource(self, package_name: str, uri: str) -> ToolResult:
        """Read a specific resource from an MCP server.
        
        Args:
            package_name: Name of the MCP package
            uri: URI of the resource to read
            
        Returns:
            Resource content
        """
        try:
            # 确保初始化
            await self.initialize()

            logger.debug(f"Reading resource {uri} from MCP server: {package_name}")
            
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "resources/read",
                "params": {
                    "uri": uri
                }
            }
            
            result = await self.sandbox.mcp_proxy_request(
                pkg=package_name,
                request=request
            )
            
            if result.success and result.data:
                try:
                    response = result.data if isinstance(result.data, dict) else json.loads(result.data)
                    if "result" in response:
                        return ToolResult(
                            success=True,
                            message=f"Resource {uri} read successfully",
                            data=response["result"]
                        )
                    elif "error" in response:
                        error = response["error"]
                        return ToolResult(
                            success=False,
                            message=f"Resource error: {error.get('message', 'Unknown error')}"
                        )
                    else:
                        return ToolResult(success=False, message="Invalid response format")
                except json.JSONDecodeError as e:
                    return ToolResult(success=False, message=f"Failed to parse response: {e}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error reading resource {uri} from MCP server {package_name}: {str(e)}"
            logger.error(error_msg)
            return ToolResult(success=False, message=error_msg)
