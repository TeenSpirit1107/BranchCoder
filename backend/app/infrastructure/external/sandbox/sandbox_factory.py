from app.infrastructure.config import get_settings
from app.infrastructure.external.sandbox.sandbox_interface import SandboxInterface
from app.infrastructure.external.sandbox.docker_sandbox import DockerSandbox
from app.infrastructure.external.sandbox.k8s_sandbox import K8sSandbox
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class SandboxFactory:
    """沙箱工厂类，根据配置创建相应的沙箱实例"""
    @staticmethod
    async def get_or_create_sandbox(sandbox_id: str, user_id: Optional[str] = None, environment_variables: Optional[Dict[str, str]] = None) -> SandboxInterface:
        """获取或创建沙箱实例，支持持久化存储卷
        
        Args:
            sandbox_id: 沙箱ID，用作容器名和存储卷名的一部分
            user_id: 可选的用户ID
            environment_variables: 可选的环境变量字典
            
        Returns:
            沙箱实例
        """
        settings = get_settings()
        
        if settings.use_kubernetes:
            return await K8sSandbox.get_or_create(sandbox_id, user_id, environment_variables)
        else:
            return await DockerSandbox.get_or_create(sandbox_id, user_id, environment_variables) 