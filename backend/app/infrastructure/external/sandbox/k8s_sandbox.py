from typing import Dict, Any, Optional, List
import uuid
import httpx
import socket
import logging
import asyncio
import yaml
import time
import json
import os
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from app.infrastructure.config import get_settings
from app.domain.models.tool_result import ToolResult
from app.infrastructure.external.sandbox.sandbox_interface import SandboxInterface

logger = logging.getLogger(__name__)

class K8sSandbox(SandboxInterface):
    def __init__(self, ip: str = None, pod_name: str = None, namespace: str = None, pod_ip: str = None, user_id: Optional[str] = None, environment_variables: Optional[Dict[str, str]] = None):
        """初始化Kubernetes沙箱和API交互客户端
        
        Args:
            ip: 沙箱服务地址（Service名称或IP）
            pod_name: Kubernetes Pod名称
            namespace: Kubernetes命名空间
            pod_ip: Pod的实际IP地址（用于Chrome CDP）
            user_id: 用户ID
            environment_variables: 环境变量字典
        """
        self.client = httpx.AsyncClient(timeout=600)
        self.ip = ip
        self.pod_name = pod_name
        self.namespace = namespace
        self.pod_ip = pod_ip or ip  # 如果没有提供pod_ip，则使用ip
        self.user_id = user_id
        self.environment_variables = environment_variables or {}
        self.base_url = f"http://{self.ip}:8080"
        self.vnc_url = f"ws://{self.ip}:5901"
        # Chrome CDP需要使用Pod IP
        self.cdp_url = f"http://{self.pod_ip}:9222"
        # Code Server URL
        self.code_server_url = f"http://{self.ip}:8443"

    @staticmethod
    async def get_or_create(sandbox_id: str, user_id: Optional[str] = None, environment_variables: Optional[Dict[str, str]] = None) -> 'K8sSandbox':
        """获取或创建K8s沙箱，支持持久化存储卷
        
        Args:
            sandbox_id: 沙箱ID，用作Pod名和PVC名
            user_id: 可选的用户ID
            environment_variables: 可选的环境变量字典
            
        Returns:
            K8sSandbox实例
        """
        return await asyncio.to_thread(K8sSandbox._get_or_create_task, sandbox_id, user_id, environment_variables)
    
    @staticmethod
    def _get_or_create_task(sandbox_id: str, user_id: Optional[str] = None, environment_variables: Optional[Dict[str, str]] = None) -> 'K8sSandbox':
        """获取或创建K8s沙箱的同步实现
        
        Args:
            sandbox_id: 沙箱ID，用作Pod名和PVC名
            user_id: 可选的用户ID
            environment_variables: 可选的环境变量字典
            
        Returns:
            K8sSandbox实例
        """
        settings = get_settings()
        
        # 使用sandbox_id作为Pod名和PVC名
        pod_name = f"{settings.sandbox_name_prefix}-{sandbox_id}"
        pvc_name = f"{settings.sandbox_name_prefix}-pvc-{sandbox_id}"
        
        try:
            # 创建Kubernetes客户端
            config.load_incluster_config()
            v1 = client.CoreV1Api()
            
            # 检查Pod是否已存在且正在运行
            try:
                existing_pod = v1.read_namespaced_pod(name=pod_name, namespace=settings.k8s_namespace)
                if existing_pod.status.phase == 'Running':
                    logger.info(f"Found existing running pod: {pod_name}")
                    
                    # 获取Pod IP
                    pod_ip = existing_pod.status.pod_ip
                    
                    return K8sSandbox(
                        pod_name=pod_name,
                        ip=pod_ip,
                        user_id=user_id,
                        environment_variables=environment_variables
                    )
                else:
                    # Pod存在但未运行，删除它
                    logger.info(f"Found non-running pod {pod_name}, deleting it")
                    v1.delete_namespaced_pod(name=pod_name, namespace=settings.k8s_namespace)
                    # 等待Pod删除完成
                    import time
                    time.sleep(5)
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    # Pod不存在，继续创建新Pod
                    logger.info(f"Pod {pod_name} not found, creating new one")
                else:
                    raise
            
            # 确保PVC存在
            try:
                existing_pvc = v1.read_namespaced_persistent_volume_claim(name=pvc_name, namespace=settings.k8s_namespace)
                logger.info(f"Found existing PVC: {pvc_name}")
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    # 创建新的PVC
                    pvc_spec = client.V1PersistentVolumeClaimSpec(
                        access_modes=['ReadWriteOnce'],
                        resources=client.V1ResourceRequirements(
                            requests={'storage': settings.k8s_pvc_size or '10Gi'}
                        )
                    )
                    
                    if settings.k8s_storage_class:
                        pvc_spec.storage_class_name = settings.k8s_storage_class
                    
                    pvc = client.V1PersistentVolumeClaim(
                        metadata=client.V1ObjectMeta(name=pvc_name),
                        spec=pvc_spec
                    )
                    
                    v1.create_namespaced_persistent_volume_claim(
                        namespace=settings.k8s_namespace,
                        body=pvc
                    )
                    logger.info(f"Created new PVC: {pvc_name}")
                else:
                    raise

            # 准备环境变量
            env_vars = [
                client.V1EnvVar(name="SERVICE_TIMEOUT_MINUTES", value=str(settings.sandbox_ttl_minutes)),
                client.V1EnvVar(name="CHROME_ARGS", value=settings.sandbox_chrome_args),
                client.V1EnvVar(name="HTTPS_PROXY", value=settings.sandbox_https_proxy),
                client.V1EnvVar(name="HTTP_PROXY", value=settings.sandbox_http_proxy),
                client.V1EnvVar(name="NO_PROXY", value=settings.sandbox_no_proxy)
            ]
            
            # 添加用户ID到环境变量
            if user_id:
                env_vars.append(client.V1EnvVar(name="USER_ID", value=user_id))
                logger.info(f"Setting USER_ID={user_id} for sandbox pod")
            
            # 添加自定义环境变量
            if environment_variables:
                for key, value in environment_variables.items():
                    env_vars.append(client.V1EnvVar(name=key, value=value))
                logger.info(f"Adding {len(environment_variables)} custom environment variables to sandbox pod")

            # 创建Pod规格
            container = client.V1Container(
                name="sandbox",
                image=settings.sandbox_image,
                env=env_vars,
                ports=[
                    client.V1ContainerPort(container_port=8080, name="api"),
                    client.V1ContainerPort(container_port=5901, name="vnc"),
                    client.V1ContainerPort(container_port=9222, name="cdp"),
                    client.V1ContainerPort(container_port=8443, name="code-server")
                ],
                volume_mounts=[
                    client.V1VolumeMount(
                        name="workspace",
                        mount_path="/home/ubuntu"
                    )
                ]
            )
            
            # 添加资源限制
            if settings.k8s_cpu_limit or settings.k8s_memory_limit:
                limits = {}
                requests = {}
                
                if settings.k8s_cpu_limit:
                    limits['cpu'] = settings.k8s_cpu_limit
                if settings.k8s_memory_limit:
                    limits['memory'] = settings.k8s_memory_limit
                if settings.k8s_cpu_request:
                    requests['cpu'] = settings.k8s_cpu_request
                if settings.k8s_memory_request:
                    requests['memory'] = settings.k8s_memory_request
                
                container.resources = client.V1ResourceRequirements(
                    limits=limits if limits else None,
                    requests=requests if requests else None
                )

            pod_spec = client.V1PodSpec(
                containers=[container],
                volumes=[
                    client.V1Volume(
                        name="workspace",
                        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                            claim_name=pvc_name
                        )
                    )
                ],
                restart_policy="Never"  # 不自动重启，保持持久化
            )

            pod = client.V1Pod(
                metadata=client.V1ObjectMeta(
                    name=pod_name,
                    labels={"app": "ai-manus-sandbox", "sandbox-id": sandbox_id}
                ),
                spec=pod_spec
            )

            # 创建Pod
            v1.create_namespaced_pod(namespace=settings.k8s_namespace, body=pod)
            logger.info(f"Created new pod: {pod_name} with PVC: {pvc_name}")

            # 等待Pod运行
            timeout = 300  # 5分钟超时
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    pod_status = v1.read_namespaced_pod(name=pod_name, namespace=settings.k8s_namespace)
                    if pod_status.status.phase == 'Running':
                        pod_ip = pod_status.status.pod_ip
                        logger.info(f"Pod {pod_name} is running with IP: {pod_ip}")
                        
                        return K8sSandbox(
                            pod_name=pod_name,
                            ip=pod_ip,
                            user_id=user_id,
                            environment_variables=environment_variables
                        )
                    elif pod_status.status.phase == 'Failed':
                        raise Exception(f"Pod {pod_name} failed to start")
                    
                    time.sleep(2)
                except client.exceptions.ApiException:
                    time.sleep(2)
            
            raise Exception(f"Timeout waiting for pod {pod_name} to start")
            
        except Exception as e:
            logger.exception(f"Failed to get or create K8s sandbox: {str(e)}")
            raise Exception(f"Failed to get or create K8s sandbox: {str(e)}")
    
    def get_cdp_url(self) -> str:
        """获取Chrome调试协议URL
        
        Returns:
            Chrome调试协议URL
        """
        return self.cdp_url

    def get_vnc_url(self) -> str:
        """获取VNC URL
        
        Returns:
            VNC URL
        """
        return self.vnc_url
    
    def get_code_server_url(self) -> str:
        """获取Code Server URL
        
        Returns:
            Code Server URL
        """
        return self.code_server_url
    
    async def get_status(self) -> ToolResult:
        """获取沙箱状态
        
        Returns:
            ToolResult: 包含沙箱服务状态的工具结果
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/supervisor/status")
            return ToolResult(**response.json())
        except Exception as e:
            return ToolResult(success=False, message=f"获取沙箱状态失败: {str(e)}")
    
    async def exec_command(self, session_id: str, exec_dir: str, command: str) -> ToolResult:
        """执行命令
        
        Args:
            session_id: 会话ID
            exec_dir: 执行目录
            command: 命令
            
        Returns:
            执行结果
        """
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
        """查看shell输出
        
        Args:
            session_id: 会话ID
            
        Returns:
            Shell输出
        """
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
        """等待进程完成
        
        Args:
            session_id: 会话ID
            seconds: 超时时间（秒）
            
        Returns:
            等待结果
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/shell/wait",
            json={
                "id": session_id,
                "seconds": seconds
            }
        )
        return ToolResult(**response.json())

    async def write_to_process(self, session_id: str, input_text: str, press_enter: bool = True) -> ToolResult:
        """向进程写入输入
        
        Args:
            session_id: 会话ID
            input_text: 输入文本
            press_enter: 是否按回车键
            
        Returns:
            写入结果
        """
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
        """终止进程
        
        Args:
            session_id: 会话ID
            
        Returns:
            终止结果
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/shell/kill",
            json={"id": session_id}
        )
        return ToolResult(**response.json())

    async def file_write(self, file: str, content: str, append: bool = False, 
                        leading_newline: bool = False, trailing_newline: bool = False, 
                        sudo: bool = False) -> ToolResult:
        """写入文件内容
        
        Args:
            file: 文件路径
            content: 内容
            append: 是否追加内容
            leading_newline: 是否在内容前添加换行符
            trailing_newline: 是否在内容后添加换行符
            sudo: 是否使用sudo权限
            
        Returns:
            写入结果
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
        """读取文件内容
        
        Args:
            file: 文件路径
            start_line: 开始行号
            end_line: 结束行号
            sudo: 是否使用sudo权限
            
        Returns:
            文件内容
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
        """检查文件是否存在
        
        Args:
            path: 文件路径
            
        Returns:
            文件是否存在
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/file/exists",
            json={"path": path}
        )
        return ToolResult(**response.json())
        
    async def file_delete(self, path: str) -> ToolResult:
        """删除文件
        
        Args:
            path: 文件路径
            
        Returns:
            删除结果
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/file/delete",
            json={"path": path}
        )
        return ToolResult(**response.json())
        
    async def file_list(self, path: str) -> ToolResult:
        """列出目录内容
        
        Args:
            path: 目录路径
            
        Returns:
            目录内容列表
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/file/list",
            json={"path": path}
        )
        return ToolResult(**response.json())

    async def file_replace(self, file: str, old_str: str, new_str: str, sudo: bool = False) -> ToolResult:
        """替换文件中的字符串
        
        Args:
            file: 文件路径
            old_str: 要替换的字符串
            new_str: 替换为的字符串
            sudo: 是否使用sudo权限
            
        Returns:
            替换结果
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
        """在文件内容中搜索
        
        Args:
            file: 文件路径
            regex: 正则表达式
            sudo: 是否使用sudo权限
            
        Returns:
            搜索结果
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
        """按名称模式查找文件
        
        Args:
            path: 搜索目录路径
            glob_pattern: Glob匹配模式
            
        Returns:
            找到的文件列表
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
        """将主机名解析为IP地址
        
        Args:
            hostname: 要解析的主机名
            
        Returns:
            解析的IP地址，或如果解析失败，则为None
        """
        try:
            # 首先检查主机名是否已经是IP地址格式
            try:
                socket.inet_pton(socket.AF_INET, hostname)
                # 如果解析成功，则是IPv4地址格式，直接返回
                return hostname
            except OSError:
                # 不是有效的IP地址格式，继续进行DNS解析
                pass
                
            # 使用socket.getaddrinfo进行DNS解析
            addr_info = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
            # 返回找到的第一个IPv4地址
            if addr_info and len(addr_info) > 0:
                return addr_info[0][4][0]  # Return sockaddr[0] from (family, type, proto, canonname, sockaddr), which is the IP address
            return None
        except Exception as e:
            # 记录错误并在失败时返回None
            logger.error(f"解析主机名失败 {hostname}: {str(e)}")
            return None

    async def close(self):
        """关闭连接和清理资源"""
        try:
            # 清理Kubernetes资源
            await self.cleanup()
        except Exception as e:
            logger.error(f"在close过程中清理Kubernetes资源失败: {str(e)}")
        
        # 关闭HTTP客户端
        if self.client:
            await self.client.aclose()
    
    async def cleanup(self):
        """清理Kubernetes资源"""
        if not self.pod_name or not self.namespace:
            return
            
        try:
            # 加载Kubernetes配置
            try:
                # 尝试从集群内部加载配置
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                # 如果失败，尝试从kubeconfig文件加载
                config.load_kube_config()
            
            # 创建Kubernetes API客户端
            v1 = client.CoreV1Api()
            
            # 删除Pod和Service
            v1.delete_namespaced_pod(name=self.pod_name, namespace=self.namespace)
            v1.delete_namespaced_service(name=self.pod_name, namespace=self.namespace)
            
            logger.info(f"清理了Kubernetes资源: pod={self.pod_name}, namespace={self.namespace}")
        except Exception as e:
            logger.error(f"清理Kubernetes资源失败: {str(e)}")

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
        