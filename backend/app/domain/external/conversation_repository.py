from abc import abstractmethod
from typing import Optional, List, Protocol
from app.domain.models.conversation import ConversationHistory, ConversationEvent

class ConversationRepository(Protocol):
    """会话仓储接口"""
    
    @abstractmethod
    async def save_history(self, history: ConversationHistory) -> None:
        """保存会话历史"""
        pass
    
    @abstractmethod
    async def get_history(self, agent_id: str) -> Optional[ConversationHistory]:
        """获取会话历史"""
        pass
    
    @abstractmethod
    async def add_event(self, agent_id: str, event_type: str, event_data: dict) -> ConversationEvent:
        """添加事件到会话历史"""
        pass
    
    @abstractmethod
    async def get_events_from_sequence(self, agent_id: str, from_sequence: int = 1) -> List[ConversationEvent]:
        """获取从指定序号开始的事件"""
        pass
    
    @abstractmethod
    async def delete_history(self, agent_id: str) -> bool:
        """删除会话历史"""
        pass
    
    @abstractmethod
    async def list_histories(self, user_id: str, limit: int = 50, offset: int = 0) -> List[ConversationHistory]:
        """列出会话历史（支持按用户过滤）"""
        pass 