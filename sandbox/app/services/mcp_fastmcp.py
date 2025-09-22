"""
FastMCP Service Implementation

Uses FastMCP client library to manage MCP server lifecycle and communication.
Provides a simplified interface compared to the manual StdioBridge implementation.
"""
import asyncio
import json
import logging
from typing import Dict, List
import os

from fastmcp import Client
from fastmcp.exceptions import McpError, ClientError
from fastmcp.client.transports import UvxStdioTransport, NpxStdioTransport, StdioTransport

from app.core.exceptions import AppException, ResourceNotFoundException, BadRequestException
from app.models.mcp import (
    Language, McpInstallRequest, McpInstallResponse,
    McpServerInfo, McpListResponse, McpUninstallResponse,
    McpHealthResponse
)


logger = logging.getLogger(__name__)


class FastMcpService:
    """
    FastMCP Service Manager
    
    Uses FastMCP client library to handle MCP server installation, lifecycle management, 
    and request proxying. Provides a simplified interface compared to manual implementation.
    """
    
    def __init__(self):
        """Initialize FastMCP service with empty registry."""
        self._registry: Dict[str, tuple[Client, Language, bool]] = {}  # client, language, initialized
        self._lock = asyncio.Lock()
        
    def _make_python_cmd(self, pkg: str, args: List[str] = None) -> List[str]:
        """
        Build command to launch Python MCP server via uvx.
        
        Args:
            pkg: PyPI package name
            args: Additional command line arguments
            
        Returns:
            Command line arguments
        """
        cmd = ["uvx", pkg]
        if args:
            cmd.extend(args)
        return cmd
        
    def _make_node_cmd(self, pkg: str, args: List[str] = None) -> List[str]:
        """
        Build command to launch Node.js MCP server via npx.
        
        Args:
            pkg: npm package name
            args: Additional command line arguments
            
        Returns:
            Command line arguments
        """
        cmd = ["npx", pkg]
        if args:
            cmd.extend(args)
        return cmd

    async def install(self, request: McpInstallRequest) -> McpInstallResponse:
        """
        Install and start MCP server using FastMCP client.
        
        Args:
            request: Installation request with package info
            
        Returns:
            Installation response with status
        """
        async with self._lock:
            pkg = request.pkg
            lang = request.lang
            args = request.args
            
            logger.info(f"Installing MCP server: {pkg} ({lang}) with args: {args}")
            
            # Check if already running
            if pkg in self._registry:
                client, _, _ = self._registry[pkg]
                if client.is_connected():
                    logger.info(f"MCP server {pkg} already running")
                    return McpInstallResponse(
                        status="ok",
                        message=f"MCP server {pkg} is already running"
                    )
                else:
                    # Remove dead entry
                    logger.info(f"Removing dead MCP server entry: {pkg}")
                    await self._cleanup_client(client)
                    del self._registry[pkg]
            
            try:
                # Prepare environment variables
                process_env = os.environ.copy()
                logger.info(f"Process environment: {process_env}")

                # Create FastMCP client with appropriate transport
                if lang == Language.PYTHON:
                    # 1. 优先尝试用 StdioTransport 直接启动
                    logger.info(f"Attempting direct launch for Python package '{pkg}' with StdioTransport.")
                    module_name = pkg.replace("-", "_")
                    direct_transport = StdioTransport("/opt/py313/bin/python", ["-m", module_name] + (request.args or []), env=process_env)
                    direct_client = Client(direct_transport, timeout=300.0)
                    try:
                        async with direct_client:
                            await direct_client.ping()
                        
                        # 成功！注册客户端并立即返回
                        logger.info(f"Successfully started pre-installed Python server '{pkg}'.")
                        self._registry[pkg] = (direct_client, lang, False)
                        return McpInstallResponse(
                            status="ok",
                            message=f"MCP server {pkg} started directly as pre-installed module."
                        )
                    except Exception as e:
                        # 直接启动失败，记录警告并准备回退
                        logger.info(f"Direct launch for '{pkg}' failed: {e}. Falling back to uvx.")
                        try:
                            await direct_client.close()  # 确保清理失败的尝试
                        except Exception as close_exc:
                            logger.warning(f"Failed to cleanly close direct_client for '{pkg}': {close_exc}")
                        # --- 回退到 UVX (作为第二选择) ---
                        # 2. 如果失败，则使用 UvxStdioTransport 启动
                        # For Python packages, use UvxStdioTransport
                        logger.info(f"Attempting uvx launch for Python package '{pkg}' with UvxStdioTransport.")
                        transport = UvxStdioTransport(
                            tool_name=pkg,
                            env_vars=process_env,
                            tool_args=args  # Pass arguments to the package
                        )
                        client = Client(transport, timeout=300.0)
                elif lang == Language.NODE:
                    # For Node packages, use NpxStdioTransport
                    transport = NpxStdioTransport(
                        package=pkg,
                        env_vars=process_env,
                        args=args  # Pass arguments to the package
                    )
                    client = Client(transport, timeout=300.0)
                else:
                    raise BadRequestException(f"Unsupported language: {lang}")
                
                logger.info(f"MCP server: {pkg} using {type(transport).__name__}")
                
                # Test connection by connecting and pinging
                async with client:
                    await client.ping()
                    logger.info(f"MCP server {pkg} started successfully")
                
                # Store in registry (not initialized yet)
                self._registry[pkg] = (client, lang, False)
                
                return McpInstallResponse(
                    status="ok",
                    message=f"MCP server {pkg} installed and started successfully"
                )
                
            except Exception as e:
                logger.error(f"Failed to start MCP server {pkg}: {e}")
                raise AppException(message=f"Failed to start MCP server {pkg}: {str(e)}")

    async def uninstall(self, pkg: str) -> McpUninstallResponse:
        """
        Stop and remove MCP server.
        
        Args:
            pkg: Package name to uninstall
            
        Returns:
            Uninstall response with status
        """
        async with self._lock:
            if pkg not in self._registry:
                raise ResourceNotFoundException(f"MCP server {pkg} not found")
            
            client, _, _ = self._registry[pkg]
            
            try:
                await self._cleanup_client(client)
                del self._registry[pkg]
                
                logger.info(f"MCP server {pkg} uninstalled successfully")
                return McpUninstallResponse(
                    status="ok",
                    message=f"MCP server {pkg} stopped and removed"
                )
                
            except Exception as e:
                logger.error(f"Error uninstalling MCP server {pkg}: {e}")
                # Remove from registry anyway
                del self._registry[pkg]
                return McpUninstallResponse(
                    status="error",
                    message=f"MCP server {pkg} removed with errors: {str(e)}"
                )

    async def list_servers(self) -> McpListResponse:
        """
        List all registered MCP servers.
        
        Returns:
            List response with server information
        """
        async with self._lock:
            servers = []
            dead_servers = []
            
            for pkg, (client, lang, _) in self._registry.items():
                try:
                    # Check if client is connected by attempting a quick ping
                    async with client:
                        await asyncio.wait_for(client.ping(), timeout=5.0)
                        servers.append(McpServerInfo(
                            pkg=pkg,
                            lang=lang,
                            alive=True,
                            pid=getattr(client.transport, 'pid', None) if hasattr(client, 'transport') else None
                        ))
                except Exception as e:
                    logger.warning(f"MCP server {pkg} appears to be dead: {e}")
                    dead_servers.append(pkg)
                    servers.append(McpServerInfo(
                        pkg=pkg,
                        lang=lang,
                        alive=False,
                        pid=None
                    ))
            
            # Clean up dead servers
            for pkg in dead_servers:
                logger.info(f"Cleaning up dead MCP server: {pkg}")
                client, _, _ = self._registry[pkg]
                await self._cleanup_client(client)
                del self._registry[pkg]
            
            return McpListResponse(servers=servers)

    async def proxy_request(self, pkg: str, payload: bytes) -> bytes:
        """
        Proxy JSON-RPC request to MCP server using FastMCP client.
        
        Args:
            pkg: Package name of target server
            payload: Raw JSON-RPC request bytes
            
        Returns:
            Raw JSON-RPC response bytes
        """
        # Get client without holding lock during request
        client = None
        async with self._lock:
            if pkg not in self._registry:
                raise ResourceNotFoundException(f"MCP server {pkg} not found")
            
            client, _, _ = self._registry[pkg]
        
        try:
            # Parse the JSON-RPC request
            request_data = json.loads(payload.decode('utf-8'))
            method = request_data.get("method")
            params = request_data.get("params", {})
            request_id = request_data.get("id")
            
            # Use FastMCP client methods for known MCP methods
            async with client:
                if method == "tools/list":
                    result = await client.list_tools()
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"tools": [tool.model_dump() for tool in result]}
                    }
                elif method == "tools/call":
                    tool_name = params.get("name")
                    arguments = params.get("arguments", {})
                    result = await client.call_tool(tool_name, arguments)

                    # The result might be a single CallToolResult object instead of a list of contents.
                    # If so, we should iterate over its .content attribute.
                    logger.info(f"MCP tool call result type: {type(result)}, result: {result}")
                    iterable_content = result.content if hasattr(result, 'content') else result

                    response = {
                        "jsonrpc": "2.0", 
                        "id": request_id,
                        "result": {"content": [content.model_dump() for content in iterable_content]}
                    }
                elif method == "resources/list":
                    result = await client.list_resources()
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"resources": [resource.model_dump() for resource in result]}
                    }
                elif method == "resources/read":
                    uri = params.get("uri")
                    result = await client.read_resource(uri)
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"contents": [content.model_dump() for content in result]}
                    }
                elif method == "prompts/list":
                    result = await client.list_prompts()
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"prompts": [prompt.model_dump() for prompt in result]}
                    }
                elif method == "prompts/get":
                    name = params.get("name")
                    arguments = params.get("arguments", {})
                    result = await client.get_prompt(name, arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result.model_dump()
                    }
                elif method == "initialize":
                    # Handle initialize specially - return synthetic response
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {
                                "experimental": {},
                                "prompts": {"listChanged": False},
                                "tools": {"listChanged": False},
                                "resources": {"listChanged": False}
                            },
                            "serverInfo": {
                                "name": pkg,
                                "version": "1.0.0"
                            }
                        }
                    }
                else:
                    # For unknown methods, return method not found error
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}"
                        }
                    }
            
            return json.dumps(response).encode('utf-8')
            
        except ClientError as e:
            logger.error(f"MCP client error for {pkg}: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": request_data.get("id") if 'request_data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Client error: {str(e)}"
                }
            }
            return json.dumps(error_response).encode('utf-8')
        except McpError as e:
            logger.error(f"MCP protocol error for {pkg}: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": request_data.get("id") if 'request_data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"MCP protocol error: {str(e)}"
                }
            }
            return json.dumps(error_response).encode('utf-8')
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request to {pkg}: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }
            return json.dumps(error_response).encode('utf-8')
        except Exception as e:
            logger.error(f"Unexpected error proxying to {pkg}: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": request_data.get("id") if 'request_data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            return json.dumps(error_response).encode('utf-8')

    async def health_check(self, pkg: str) -> McpHealthResponse:
        """
        Check health of specific MCP server.
        
        Args:
            pkg: Package name to check
            
        Returns:
            Health response with status
        """
        async with self._lock:
            if pkg not in self._registry:
                raise ResourceNotFoundException(f"MCP server {pkg} not found")
            
            client, _, _ = self._registry[pkg]
            
            try:
                async with client:
                    await asyncio.wait_for(client.ping(), timeout=5.0)
                    return McpHealthResponse(
                        pkg=pkg,
                        alive=True,
                        uptime=0.0  # FastMCP doesn't provide uptime directly
                    )
            except (ClientError, McpError) as e:
                logger.warning(f"Health check failed for {pkg}: {e}")
                return McpHealthResponse(
                    pkg=pkg,
                    alive=False,
                    uptime=0.0
                )
            except Exception as e:
                logger.warning(f"Health check failed for {pkg}: {e}")
                return McpHealthResponse(
                    pkg=pkg,
                    alive=False,
                    uptime=0.0
                )

    async def get_capabilities(self, pkg: str) -> dict:
        """
        Get capabilities of specific MCP server.
        
        Args:
            pkg: Package name to check
            
        Returns:
            Server capabilities
        """
        async with self._lock:
            if pkg not in self._registry:
                raise ResourceNotFoundException(f"MCP server {pkg} not found")
            
            client, _, _ = self._registry[pkg]
            
        try:
            async with client:
                capabilities = {
                    "tools": {"listChanged": False, "count": 0},
                    "resources": {"listChanged": False, "count": 0},
                    "prompts": {"listChanged": False, "count": 0},
                    "experimental": {}
                }
                
                # Try to get tools (most common capability)
                try:
                    tools = await client.list_tools()
                    capabilities["tools"] = tools
                except (ClientError, McpError) as e:
                    logger.debug(f"Server {pkg} does not support tools: {e}")
                
                # Try to get resources (optional capability)
                try:
                    resources = await client.list_resources()
                    capabilities["resources"] = resources
                except (ClientError, McpError) as e:
                    logger.debug(f"Server {pkg} does not support resources: {e}")
                
                # Try to get prompts (optional capability)
                try:
                    prompts = await client.list_prompts()
                    capabilities["prompts"] = prompts
                except (ClientError, McpError) as e:
                    logger.debug(f"Server {pkg} does not support prompts: {e}")
                
                return capabilities
        except Exception as e:
            logger.error(f"Failed to get capabilities for {pkg}: {e}")
            raise AppException(message=f"Failed to get capabilities for {pkg}: {str(e)}")

    async def shutdown_all(self) -> None:
        """
        Gracefully shutdown all MCP servers.
        """
        async with self._lock:
            if not self._registry:
                return
            
            logger.info(f"Shutting down {len(self._registry)} MCP servers")
            
            # Stop all servers concurrently
            tasks = []
            for pkg, (client, _, _) in self._registry.items():
                tasks.append(self._stop_server_safe(pkg, client))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Clear registry
            self._registry.clear()
            logger.info("All MCP servers shutdown complete")

    async def _stop_server_safe(self, pkg: str, client: Client) -> None:
        """
        Safely stop a single MCP server with error handling.
        
        Args:
            pkg: Package name for logging
            client: FastMCP client to stop
        """
        try:
            await self._cleanup_client(client)
            logger.info(f"Stopped MCP server: {pkg}")
        except Exception as e:
            logger.error(f"Error stopping MCP server {pkg}: {e}")

    async def _cleanup_client(self, client: Client) -> None:
        """
        Clean up FastMCP client resources.
        
        Args:
            client: Client to clean up
        """
        try:
            if hasattr(client, 'close'):
                await client.close()
        except Exception as e:
            logger.debug(f"Error during client cleanup: {e}")


# Global service instance
fastmcp_service = FastMcpService() 