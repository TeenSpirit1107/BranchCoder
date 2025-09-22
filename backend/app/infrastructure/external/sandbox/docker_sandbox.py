from typing import Dict, Any, Optional, List
import uuid
import httpx
import docker
import socket
import logging
import asyncio
import os
import random
from app.infrastructure.config import get_settings
from urllib.parse import urlparse
from app.domain.models.tool_result import ToolResult
from app.infrastructure.external.sandbox.sandbox_interface import SandboxInterface

logger = logging.getLogger(__name__)

class DockerSandbox(SandboxInterface):
    def __init__(
            self, 
            container_name: str, 
            ip: str = None, 
            api_server_port: int = 8080, 
            vnc_port: int = 5901, 
            cdp_port: int = 9222, 
            code_server_port: int = 8443,
            user_id: Optional[str] = None, 
            environment_variables: Optional[Dict[str, str]] = None
        ):
        """Initialize Docker sandbox and API interaction client"""
        self.container_name = container_name
        self.client = httpx.AsyncClient(timeout=600)
        self.ip = ip
        self.base_url = f"http://{self.ip}:{api_server_port}"
        self.vnc_url = f"ws://{self.ip}:{vnc_port}"
        self.cdp_url = f"http://{self.ip}:{cdp_port}"
        self.code_server_url = f"http://{self.ip}:{code_server_port}"
        self.user_id = user_id
        self.environment_variables = environment_variables or {}

    @staticmethod
    def _create_docker_client(settings):
        """创建Docker客户端连接
        
        支持本地和远程Docker主机连接，支持TLS认证
        优先使用配置中的设置，如果未配置则尝试使用环境变量
        
        Args:
            settings: 应用配置
            
        Returns:
            Docker客户端实例
        """
        # 检查是否使用远程Docker主机
        docker_url = settings.docker_host_url
        
        # 如果未配置docker_host_url，但存在DOCKER_HOST环境变量，则使用环境变量
        if not docker_url and os.environ.get('DOCKER_HOST'):
            docker_url = os.environ.get('DOCKER_HOST')
            logger.info(f"Using DOCKER_HOST from environment: {docker_url}")
            
        if docker_url:
            # 连接到远程Docker主机
            docker_client = docker.DockerClient(
                base_url=docker_url, 
                timeout=settings.docker_timeout or 120
            )
            logger.info(f"Connected to remote Docker host: {docker_url}")
        else:
            # 使用from_env()从环境变量中读取配置连接到Docker
            docker_client = docker.from_env()
            logger.info("Connected to local Docker host using environment configuration")
            
        # 测试docker连接是否正常
        try:
            docker_client.ping()
            logger.info("Docker connection test passed")
        except Exception as e:
            logger.error(f"Docker connection test failed: {str(e)}")
            raise Exception(f"Docker connection test failed: {str(e)}")
        return docker_client

    @staticmethod
    async def get_or_create(sandbox_id: str, user_id: Optional[str] = None, environment_variables: Optional[Dict[str, str]] = None) -> 'DockerSandbox':
        """获取或创建Docker沙箱，支持持久化存储卷
        
        Args:
            sandbox_id: 沙箱ID，用作容器名和存储卷名
            user_id: 可选的用户ID
            environment_variables: 可选的环境变量字典
            
        Returns:
            DockerSandbox实例
        """
        return await asyncio.to_thread(DockerSandbox._get_or_create_task, sandbox_id, user_id, environment_variables)
    
    @staticmethod
    def _get_or_create_task(sandbox_id: str, user_id: Optional[str] = None, environment_variables: Optional[Dict[str, str]] = None) -> 'DockerSandbox':
        """获取或创建Docker沙箱的同步实现
        
        Args:
            sandbox_id: 沙箱ID，用作容器名和存储卷名
            user_id: 可选的用户ID
            environment_variables: 可选的环境变量字典
            
        Returns:
            DockerSandbox实例
        """
        settings = get_settings()
        
        # 使用sandbox_id作为容器名和存储卷名
        container_name = f"{settings.sandbox_name_prefix}-{sandbox_id}"
        volume_name = f"{settings.sandbox_name_prefix}-vol-{sandbox_id}"
        
        try:
            # 创建Docker客户端
            docker_client = DockerSandbox._create_docker_client(settings)
            
            # 判断是否为远程Docker
            is_remote_docker = settings.docker_host_url or os.environ.get('DOCKER_HOST')
            
            # 检查容器是否已存在且正在运行
            try:
                existing_container = docker_client.containers.get(container_name)
                if existing_container.status == 'running':
                    logger.info(f"Found existing running container: {container_name}")
                    
                    # 获取容器IP地址
                    existing_container.reload()
                    network_settings = existing_container.attrs['NetworkSettings']
                    ip_address = network_settings['IPAddress']
                    
                    # 如果默认网络没有IP，尝试从其他网络获取IP
                    if not ip_address and 'Networks' in network_settings:
                        networks = network_settings['Networks']
                        for network_name, network_config in networks.items():
                            if 'IPAddress' in network_config and network_config['IPAddress']:
                                ip_address = network_config['IPAddress']
                                break
                    
                    # 对于远程Docker，使用配置的远程地址
                    if is_remote_docker and settings.sandbox_remote_address:
                        # 获取端口映射
                        ports = existing_container.attrs['NetworkSettings']['Ports']
                        api_server_port = int(ports['8080/tcp'][0]['HostPort']) if ports.get('8080/tcp') else 8080
                        vnc_port = int(ports['5901/tcp'][0]['HostPort']) if ports.get('5901/tcp') else 5901
                        cdp_port = int(ports['9222/tcp'][0]['HostPort']) if ports.get('9222/tcp') else 9222
                        code_server_port = int(ports['8443/tcp'][0]['HostPort']) if ports.get('8443/tcp') else 8443

                        return DockerSandbox(
                            container_name=container_name,
                            ip=settings.sandbox_remote_address,
                            api_server_port=api_server_port,
                            vnc_port=vnc_port,
                            cdp_port=cdp_port,
                            code_server_port=code_server_port,
                            user_id=user_id,
                            environment_variables=environment_variables
                        )
                    
                    return DockerSandbox(
                        container_name=container_name,
                        ip=ip_address,
                        user_id=user_id,
                        environment_variables=environment_variables
                    )
                else:
                    # 容器存在但未运行，删除它
                    logger.info(f"Found stopped container {container_name}, removing it")
                    existing_container.remove(force=True)
            except docker.errors.NotFound:
                # 容器不存在，继续创建新容器
                logger.info(f"Container {container_name} not found, creating new one")
                pass
            
            # 确保存储卷存在
            try:
                volume = docker_client.volumes.get(volume_name)
                logger.info(f"Found existing volume: {volume_name}")
            except docker.errors.NotFound:
                # 创建新的存储卷
                volume = docker_client.volumes.create(
                    name=volume_name,
                    driver='local'
                )
                logger.info(f"Created new volume: {volume_name}")

            # 准备环境变量
            env_vars = {
                "SERVICE_TIMEOUT_MINUTES": settings.sandbox_ttl_minutes,
                "CHROME_ARGS": settings.sandbox_chrome_args,
                "HTTPS_PROXY": settings.sandbox_https_proxy,
                "HTTP_PROXY": settings.sandbox_http_proxy,
                "NO_PROXY": settings.sandbox_no_proxy
            }
            
            # 添加用户ID到环境变量
            if user_id:
                env_vars["USER_ID"] = user_id
                logger.info(f"Setting USER_ID={user_id} for sandbox container")
            
            # 添加自定义环境变量
            if environment_variables:
                for key, value in environment_variables.items():
                    env_vars[key] = value
                logger.info(f"Adding {len(environment_variables)} custom environment variables to sandbox container")

            # 准备容器配置
            container_config = {
                "image": settings.sandbox_image,
                "name": container_name,
                "detach": True,
                # 自动删除容器但保留命名卷，以便持久化数据
                "remove": True,
                "environment": env_vars,
                "volumes": {
                    volume_name: {
                        'bind': '/home/ubuntu',
                        'mode': 'rw'
                    }
                }
            }

            if is_remote_docker:
                port_range = range(30720, 40730)
                api_server_port = random.choice(port_range)
                vnc_port = random.choice(port_range)
                cdp_port = random.choice(port_range)
                code_server_port = random.choice(port_range)
                container_config["ports"] = {
                    "8080": {
                        "HostPort": api_server_port
                    },
                    "5901": {
                        "HostPort": vnc_port
                    },
                    "9222": {
                        "HostPort": cdp_port
                    },
                    "8443": {
                        "HostPort": code_server_port
                    }
                }
            
            # 添加网络配置
            if settings.sandbox_network:
                container_config["network"] = settings.sandbox_network
            
            # 创建容器
            container = docker_client.containers.run(**container_config)
            logger.info(f"Created new container: {container_name} with volume: {volume_name}")
            
            # 获取容器IP地址
            container.reload()
            network_settings = container.attrs['NetworkSettings']
            ip_address = network_settings['IPAddress']
            
            # 如果默认网络没有IP，尝试从其他网络获取IP
            if not ip_address and 'Networks' in network_settings:
                networks = network_settings['Networks']
                for network_name, network_config in networks.items():
                    if 'IPAddress' in network_config and network_config['IPAddress']:
                        ip_address = network_config['IPAddress']
                        break
            
            # 对于远程Docker，使用配置的远程地址
            if is_remote_docker and settings.sandbox_remote_address:
                logger.info(f"Using configured remote sandbox address: {settings.sandbox_remote_address}")
                return DockerSandbox(
                    container_name=container_name,
                    ip=settings.sandbox_remote_address,
                    api_server_port=api_server_port,
                    vnc_port=vnc_port,
                    cdp_port=cdp_port,
                    code_server_port=code_server_port,
                    user_id=user_id,
                    environment_variables=environment_variables
                )
            
            # 创建并返回DockerSandbox实例
            return DockerSandbox(
                container_name=container_name,
                ip=ip_address,
                user_id=user_id,
                environment_variables=environment_variables
            )
            
        except Exception as e:
            logger.exception(f"Failed to get or create Docker sandbox: {str(e)}")
            raise Exception(f"Failed to get or create Docker sandbox: {str(e)}")
    
    def get_cdp_url(self) -> str:
        return self.cdp_url

    def get_vnc_url(self) -> str:
        return self.vnc_url

    def get_code_server_url(self) -> str:
        return self.code_server_url

    async def get_status(self) -> ToolResult:
        """获取沙箱状态
        
        返回沙箱中各服务的运行状态
        
        Returns:
            ToolResult: 包含沙箱服务状态的工具结果
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/supervisor/status")
            return ToolResult(**response.json())
        except Exception as e:
            return ToolResult(success=False, message=f"获取沙箱状态失败: {str(e)}")

    async def exec_command(self, session_id: str, exec_dir: str, command: str) -> ToolResult:
        response = await self.client.post(
            f"{self.base_url}/api/v1/shell/exec",
            json={
                "id": session_id,
                "exec_dir": exec_dir,
                "command": command
            }
        )
        return ToolResult(**response.json())

    async def view_shell(self, session_id: str) -> ToolResult:
        try:
            # 设置超时时间为10秒，防止请求卡住
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/shell/view",
                    json={"id": session_id}
                )
                return ToolResult(**response.json())
        except httpx.TimeoutException:
            logger.warning(f"视图Shell请求超时 - session_id: {session_id}")
            return ToolResult(success=False, message="请求超时，可能是因为Shell会话处理了大量输出")
        except httpx.RemoteProtocolError as e:
            logger.error(f"远程协议错误 - session_id: {session_id}, 错误: {str(e)}")
            return ToolResult(success=False, message=f"连接错误: {str(e)}")
        except Exception as e:
            logger.exception(f"查看Shell输出时出错 - session_id: {session_id}")
            return ToolResult(success=False, message=f"查看Shell输出失败: {str(e)}")

    async def wait_for_process(self, session_id: str, seconds: Optional[int] = None) -> ToolResult:
        response = await self.client.post(
            f"{self.base_url}/api/v1/shell/wait",
            json={
                "id": session_id,
                "seconds": seconds
            }
        )
        return ToolResult(**response.json())

    async def write_to_process(self, session_id: str, input_text: str, press_enter: bool = True) -> ToolResult:
        response = await self.client.post(
            f"{self.base_url}/api/v1/shell/write",
            json={
                "id": session_id,
                "input": input_text,
                "press_enter": press_enter
            }
        )
        return ToolResult(**response.json())

    async def kill_process(self, session_id: str) -> ToolResult:
        response = await self.client.post(
            f"{self.base_url}/api/v1/shell/kill",
            json={"id": session_id}
        )
        return ToolResult(**response.json())

    async def file_write(self, file: str, content: str, append: bool = False, 
                        leading_newline: bool = False, trailing_newline: bool = False, 
                        sudo: bool = False) -> ToolResult:
        """Write content to file
        
        Args:
            file: File path
            content: Content to write
            append: Whether to append content
            leading_newline: Whether to add newline before content
            trailing_newline: Whether to add newline after content
            sudo: Whether to use sudo privileges
            
        Returns:
            Result of write operation
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/file/write",
            json={
                "file": file,
                "content": content,
                "append": append,
                "leading_newline": leading_newline,
                "trailing_newline": trailing_newline,
                "sudo": sudo
            }
        )
        return ToolResult(**response.json())

    async def file_read(self, file: str, start_line: int = None, 
                        end_line: int = None, sudo: bool = False) -> ToolResult:
        """Read file content
        
        Args:
            file: File path
            start_line: Start line number
            end_line: End line number
            sudo: Whether to use sudo privileges
            
        Returns:
            File content
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/file/read",
            json={
                "file": file,
                "start_line": start_line,
                "end_line": end_line,
                "sudo": sudo
            }
        )
        return ToolResult(**response.json())
        
    async def file_exists(self, path: str) -> ToolResult:
        """Check if file exists
        
        Args:
            path: File path
            
        Returns:
            Whether file exists
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/file/exists",
            json={"path": path}
        )
        return ToolResult(**response.json())
        
    async def file_delete(self, path: str) -> ToolResult:
        """Delete file
        
        Args:
            path: File path
            
        Returns:
            Result of delete operation
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/file/delete",
            json={"path": path}
        )
        return ToolResult(**response.json())
        
    async def file_list(self, path: str) -> ToolResult:
        """List directory contents
        
        Args:
            path: Directory path
            
        Returns:
            List of directory contents
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/file/list",
            json={"path": path}
        )
        return ToolResult(**response.json())

    async def file_replace(self, file: str, old_str: str, new_str: str, sudo: bool = False) -> ToolResult:
        """Replace string in file
        
        Args:
            file: File path
            old_str: String to replace
            new_str: String to replace with
            sudo: Whether to use sudo privileges
            
        Returns:
            Result of replace operation
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/file/replace",
            json={
                "file": file,
                "old_str": old_str,
                "new_str": new_str,
                "sudo": sudo
            }
        )
        return ToolResult(**response.json())

    async def file_search(self, file: str, regex: str, sudo: bool = False) -> ToolResult:
        """Search in file content
        
        Args:
            file: File path
            regex: Regular expression
            sudo: Whether to use sudo privileges
            
        Returns:
            Search results
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/file/search",
            json={
                "file": file,
                "regex": regex,
                "sudo": sudo
            }
        )
        return ToolResult(**response.json())

    async def file_find(self, path: str, glob_pattern: str) -> ToolResult:
        """Find files by name pattern
        
        Args:
            path: Search directory path
            glob_pattern: Glob match pattern
            
        Returns:
            List of found files
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/file/find",
            json={
                "path": path,
                "glob": glob_pattern
            }
        )
        return ToolResult(**response.json())

    async def file_upload(self, file_path: str, content: bytes, make_executable: bool = False) -> ToolResult:
        """
        上传二进制文件内容到沙箱
        
        Args:
            file_path: 在沙箱中的目标文件路径
            content: 文件二进制内容
            make_executable: 是否将文件设置为可执行
            
        Returns:
            上传结果
        """
        await self.ensure_status()
        # 使用multipart/form-data上传二进制内容
        import io
        import aiohttp
        from aiohttp import FormData
        
        form = FormData()
        form.add_field('file', 
                       io.BytesIO(content),
                       filename=os.path.basename(file_path))
        form.add_field('path', file_path)
        form.add_field('make_executable', str(make_executable).lower())
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/api/v1/file/upload", data=form) as response:
                result_json = await response.json()
                return ToolResult(**result_json)
                
    async def file_download(self, file_path: str) -> bytes:
        """
        从沙箱下载文件的二进制内容
        
        Args:
            file_path: 沙箱中的文件路径
            
        Returns:
            文件的二进制内容
            
        Raises:
            FileNotFoundError: 当文件不存在时
            PermissionError: 当权限不足时
            Exception: 其他错误
        """
        import aiohttp
        
        # 首先检查文件是否存在
        result = await self.file_exists(file_path)
        if not result.success or not result.data.get("exists", False):
            raise FileNotFoundError(f"文件在沙箱中不存在: {file_path}")
        
        # 发起下载请求
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/v1/file/download",
                json={"path": file_path}
            ) as response:
                if response.status == 200:
                    return await response.read()
                elif response.status == 404:
                    raise FileNotFoundError(f"文件在沙箱中不存在: {file_path}")
                elif response.status == 403:
                    raise PermissionError(f"没有权限访问文件: {file_path}")
                else:
                    error_text = await response.text()
                    raise Exception(f"下载文件失败 ({response.status}): {error_text}")

    @staticmethod
    async def _resolve_hostname_to_ip(hostname: str) -> str:
        """Resolve hostname to IP address
        
        Args:
            hostname: Hostname to resolve
            
        Returns:
            Resolved IP address, or None if resolution fails
        """
        try:
            # First check if hostname is already in IP address format
            try:
                socket.inet_pton(socket.AF_INET, hostname)
                # If successfully parsed, it's an IPv4 address format, return directly
                return hostname
            except OSError:
                # Not a valid IP address format, proceed with DNS resolution
                pass
                
            # Use socket.getaddrinfo for DNS resolution
            addr_info = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
            # Return the first IPv4 address found
            if addr_info and len(addr_info) > 0:
                return addr_info[0][4][0]  # Return sockaddr[0] from (family, type, proto, canonname, sockaddr), which is the IP address
            return None
        except Exception as e:
            # Log error and return None on failure
            logger.error(f"Failed to resolve hostname {hostname}: {str(e)}")
            return None

    async def close(self):
        """关闭连接和清理资源"""
        try:
            # 清理Docker容器
            settings = get_settings()
            try:
                # 创建Docker客户端
                docker_client = self._create_docker_client(settings)
                
                # 尝试查找匹配IP的容器
                containers = docker_client.containers.list(
                    filters={"name": self.container_name}
                )
                
                for container in containers:
                    container.stop()
                    try:
                        container.remove(force=True)
                    except Exception as e:
                        logger.error(f"Failed to remove container {container.name}: {str(e)}")
            except Exception as e:
                logger.error(f"清理Docker容器时出错: {str(e)}")
        except Exception as e:
            logger.error(f"关闭沙箱连接时出错: {str(e)}")
        
        # 关闭HTTP客户端
        if self.client:
            await self.client.aclose()

    # MCP服务管理相关方法
    async def mcp_install(self, pkg: str, lang: str, args: Optional[list] = None) -> ToolResult:
        """
        安装并启动MCP服务器
        
        Args:
            pkg: MCP包名称
            lang: 编程语言类型 ("python" 或 "node")
            args: 可选的启动参数列表
            
        Returns:
            安装结果
        """
        await self.ensure_status()
        response = await self.client.post(
            f"{self.base_url}/api/v1/mcp/install",
            json={
                "pkg": pkg,
                "lang": lang,
                "args": args
            }
        )

        if response.status_code == 200:
            # 转换沙箱返回格式为ToolResult格式
            response_data = response.json()
            # status, message
            return ToolResult(
                success=response_data["status"] == "ok",
                message=response_data["message"]
            )
        else:
            return ToolResult(
                success=False,
                message=response.text
            )
    
    async def mcp_uninstall(self, pkg: str) -> ToolResult:
        """
        停止并卸载MCP服务器
        
        Args:
            pkg: MCP包名称
            
        Returns:
            卸载结果
        """
        await self.ensure_status()
        response = await self.client.delete(
            f"{self.base_url}/api/v1/mcp/uninstall/{pkg}"
        )
        
        if response.status_code == 200:
            # 转换沙箱返回格式为ToolResult格式
            response_data = response.json()
            # status, message
            return ToolResult(
                success=response_data["status"] == "ok",
                message=response_data["message"]
            )
        else:
            return ToolResult(
                success=False,
                message=response.text
            )
    
    async def mcp_list_servers(self) -> ToolResult:
        """
        列出所有已安装的MCP服务器
        
        Returns:
            服务器列表结果，包含各服务器的状态信息
        """
        await self.ensure_status()
        response = await self.client.get(
            f"{self.base_url}/api/v1/mcp/list"
        )
        
        if response.status_code == 200:
            # 转换沙箱返回格式为ToolResult格式
            response_data = response.json()
            # servers
            return ToolResult(
                success=True,
                data=response_data["servers"]
            )
        else:
            return ToolResult(
                success=False,
                message=response.text
            )
    
    async def mcp_health_check(self, pkg: str) -> ToolResult:
        """
        检查MCP服务器健康状态
        
        Args:
            pkg: MCP包名称
            
        Returns:
            健康检查结果
        """
        await self.ensure_status()
        response = await self.client.get(
            f"{self.base_url}/api/v1/mcp/health/{pkg}"
        )
        
        if response.status_code == 200:
            # 转换沙箱返回格式为ToolResult格式
            response_data = response.json()
            # pkg, alive, uptime
            return ToolResult(
                success=True,
                data=response_data
            )
        else:
            return ToolResult(
                success=False,
                message=response.text
            )
    
    async def mcp_proxy_request(self, pkg: str, request: Dict) -> ToolResult:
        """
        向MCP服务器发送代理请求
        
        Args:
            pkg: MCP包名称
            request: 请求内容字典
            
        Returns:
            代理请求结果
        """
        await self.ensure_status()
        response = await self.client.post(
            f"{self.base_url}/api/v1/mcp/proxy/{pkg}",
            json=request
        )
        
        # 对于proxy请求，处理原始响应内容
        if response.status_code < 400:
            try:
                response_data = response.json()
                return ToolResult(
                    success=True,
                    message="MCP proxy request completed",
                    data=response_data
                )
            except Exception:
                # 如果不是JSON，返回原始内容
                return ToolResult(
                    success=True,
                    message="MCP proxy request completed",
                    data={"content": response.text}
                )
        else:
            return ToolResult(
                success=False,
                message=f"MCP proxy request failed with status {response.status_code}",
                data={"status_code": response.status_code, "content": response.text}
            )
    
    async def mcp_get_capabilities(self, pkg: str) -> ToolResult:
        """
        获取MCP服务器的能力信息
        
        Args:
            pkg: MCP包名称
            
        Returns:
            服务器能力信息
        """
        await self.ensure_status()
        response = await self.client.get(
            f"{self.base_url}/api/v1/mcp/capabilities/{pkg}"
        )
        
        if response.status_code == 200:
            # 转换沙箱返回格式为ToolResult格式
            response_data = response.json()
            # pkg, tools_count, tools
            return ToolResult(
                success=True,
                data=response_data
            )
        else:
            return ToolResult(
                success=False,
                message=response.text
            )
    
    async def mcp_shutdown_all(self) -> ToolResult:
        """
        关闭所有MCP服务器
        
        Returns:
            关闭操作结果
        """
        await self.ensure_status()
        response = await self.client.post(
            f"{self.base_url}/api/v1/mcp/shutdown"
        )
        
        if response.status_code == 200:
            # 转换沙箱返回格式为ToolResult格式
            response_data = response.json()
            # status, message
            return ToolResult(
                success=response_data["status"] == "ok",
                message=response_data["message"]
            )
        else:
            return ToolResult(
                success=False,
                message=response.text
            )
