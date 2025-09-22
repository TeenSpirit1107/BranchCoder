import asyncio
from abc import abstractmethod
from typing import Optional, Dict, Protocol

from app.domain.models.tool_result import ToolResult


class SandboxInterface(Protocol):
    """抽象沙箱接口，定义所有沙箱必须实现的方法"""    
    @staticmethod
    @abstractmethod
    async def get_or_create(sandbox_id: str, user_id: Optional[str] = None, environment_variables: Optional[Dict[str, str]] = None) -> 'SandboxInterface':
        """获取或创建沙箱实例，支持持久化存储卷
        
        Args:
            sandbox_id: 沙箱ID，用作容器名和存储卷名的一部分
            user_id: 可选的用户ID
            environment_variables: 可选的环境变量字典
            
        Returns:
            沙箱实例
        """
        pass
    
    @abstractmethod
    def get_cdp_url(self) -> str:
        """获取Chrome调试协议URL"""
        pass
    
    @abstractmethod
    def get_vnc_url(self) -> str:
        """获取VNC URL"""
        pass
    
    @abstractmethod
    def get_code_server_url(self) -> str:
        """获取Code Server URL"""
        pass
    
    @abstractmethod
    async def get_status(self) -> ToolResult:
        """获取沙箱状态，检查所有服务是否正常运行"""
        pass

    async def ensure_status(self) -> ToolResult:
        """确保沙箱状态正常"""
        retry = 5
        interval = 2
        for _ in range(retry):
            status = await self.get_status()
            if status.success:
                return status
            await asyncio.sleep(interval)
        return ToolResult(success=False, message="沙箱状态检查失败")
    
    @abstractmethod
    async def exec_command(self, session_id: str, exec_dir: str, command: str) -> ToolResult:
        """执行命令"""
        pass
    
    @abstractmethod
    async def view_shell(self, session_id: str) -> ToolResult:
        """查看shell输出"""
        pass
    
    @abstractmethod
    async def wait_for_process(self, session_id: str, seconds: Optional[int] = None) -> ToolResult:
        """等待进程完成"""
        pass
    
    @abstractmethod
    async def write_to_process(self, session_id: str, input_text: str, press_enter: bool = True) -> ToolResult:
        """向进程写入输入"""
        pass
    
    @abstractmethod
    async def kill_process(self, session_id: str) -> ToolResult:
        """终止进程"""
        pass
    
    @abstractmethod
    async def file_write(self, file: str, content: str, append: bool = False, 
                       leading_newline: bool = False, trailing_newline: bool = False, 
                       sudo: bool = False) -> ToolResult:
        """写入文件内容"""
        pass
    
    @abstractmethod
    async def file_read(self, file: str, start_line: int = None, 
                      end_line: int = None, sudo: bool = False) -> ToolResult:
        """读取文件内容"""
        pass
    
    @abstractmethod
    async def file_exists(self, path: str) -> ToolResult:
        """检查文件是否存在"""
        pass
    
    @abstractmethod
    async def file_delete(self, path: str) -> ToolResult:
        """删除文件"""
        pass
    
    @abstractmethod
    async def file_list(self, path: str) -> ToolResult:
        """列出目录内容"""
        pass
    
    @abstractmethod
    async def file_replace(self, file: str, old_str: str, new_str: str, sudo: bool = False) -> ToolResult:
        """替换文件中的字符串"""
        pass
    
    @abstractmethod
    async def file_search(self, file: str, regex: str, sudo: bool = False) -> ToolResult:
        """在文件内容中搜索"""
        pass
    
    @abstractmethod
    async def file_find(self, path: str, glob_pattern: str) -> ToolResult:
        """按名称模式查找文件"""
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    # MCP服务管理相关方法
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def mcp_uninstall(self, pkg: str) -> ToolResult:
        """
        停止并卸载MCP服务器
        
        Args:
            pkg: MCP包名称
            
        Returns:
            卸载结果
        """
        pass
    
    @abstractmethod
    async def mcp_list_servers(self) -> ToolResult:
        """
        列出所有已安装的MCP服务器
        
        Returns:
            服务器列表结果，包含各服务器的状态信息
        """
        pass
    
    @abstractmethod
    async def mcp_health_check(self, pkg: str) -> ToolResult:
        """
        检查MCP服务器健康状态
        
        Args:
            pkg: MCP包名称
            
        Returns:
            健康状态结果
        """
        pass
    
    @abstractmethod
    async def mcp_proxy_request(self, pkg: str, request: Dict) -> ToolResult:
        """
        代理JSON-RPC请求到MCP服务器
        
        Args:
            pkg: 目标MCP服务器包名
            request: JSON-RPC请求数据
            
        Returns:
            服务器响应结果
        """
        pass
    
    @abstractmethod
    async def mcp_get_capabilities(self, pkg: str) -> ToolResult:
        """
        获取MCP服务器能力信息
        
        Args:
            pkg: MCP包名称
            
        Returns:
            服务器能力信息结果
        """
        pass
    
    @abstractmethod
    async def mcp_shutdown_all(self) -> ToolResult:
        """
        关闭所有MCP服务器
        
        Returns:
            关闭操作结果
        """
        pass
    
    @abstractmethod
    async def close(self):
        """关闭连接，清理资源"""
        pass 