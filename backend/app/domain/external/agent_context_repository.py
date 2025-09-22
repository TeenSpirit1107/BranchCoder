"""Agent上下文仓储接口"""

from abc import abstractmethod
from typing import Optional, List, Protocol

from app.domain.models.agent_context import AgentContext


class AgentContextRepository(Protocol):
    """Agent上下文仓储接口"""
    
    @abstractmethod
    async def save_context(self, context: AgentContext) -> None:
        """保存Agent上下文"""
        pass
    
    @abstractmethod
    async def get_context(self, agent_id: str) -> Optional[AgentContext]:
        """通过agent_id获取Agent上下文"""
        pass
    
    @abstractmethod
    async def update_context(self, context: AgentContext) -> None:
        """更新Agent上下文"""
        pass
    
    @abstractmethod
    async def delete_context(self, agent_id: str) -> bool:
        """删除Agent上下文"""
        pass
    
    @abstractmethod
    async def list_contexts(self, user_id: Optional[str] = None, status: Optional[str] = None, 
                           limit: int = 50, offset: int = 0) -> List[AgentContext]:
        """列出Agent上下文（支持按用户和状态过滤）"""
        pass
    
    @abstractmethod
    async def get_contexts_by_user(self, user_id: str) -> List[AgentContext]:
        """获取指定用户的所有Agent上下文"""
        pass
    
    @abstractmethod
    async def get_contexts_by_status(self, status: str) -> List[AgentContext]:
        """获取指定状态的所有Agent上下文"""
        pass
    
    @abstractmethod
    async def update_status(self, agent_id: str, status: str) -> bool:
        """更新Agent状态"""
        pass
    
    @abstractmethod
    async def update_last_message(self, agent_id: str, message: str, timestamp: Optional[int] = None) -> bool:
        """更新最后消息"""
        pass
    
    @abstractmethod
    async def set_sandbox_id(self, agent_id: str, sandbox_id: str) -> bool:
        """设置沙盒ID"""
        pass
    
    @abstractmethod
    async def context_exists(self, agent_id: str) -> bool:
        """检查Agent上下文是否存在"""
        pass 