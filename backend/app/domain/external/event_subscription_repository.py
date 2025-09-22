from abc import abstractmethod
from typing import List, Optional, AsyncGenerator, Protocol

from app.domain.models.event import AgentEvent
from app.domain.models.event_subscription import AgentEventBroadcaster


class EventBroadcastRepository(Protocol):
    """事件广播仓储接口"""

    @abstractmethod
    async def save_broadcaster(self, broadcaster: AgentEventBroadcaster) -> None:
        """保存广播器"""
        pass

    @abstractmethod
    async def get_broadcaster(self, agent_id: str) -> Optional[AgentEventBroadcaster]:
        """获取广播器"""
        pass

    @abstractmethod
    async def update_broadcaster(self, broadcaster: AgentEventBroadcaster) -> bool:
        """更新广播器"""
        pass

    @abstractmethod
    async def delete_broadcaster(self, agent_id: str) -> bool:
        """删除广播器"""
        pass


class EventStreamRepository(Protocol):
    """事件流仓储接口"""

    @abstractmethod
    async def get_events_from_sequence(self, agent_id: str, from_sequence: int = 1) -> AsyncGenerator[AgentEvent, None]:
        """从指定序号开始获取事件流（包含历史事件和实时事件）"""
        pass

    @abstractmethod
    async def get_buffered_events(self, agent_id: str, from_sequence: int = 1) -> List[AgentEvent]:
        """获取缓冲区中的事件"""
        pass

    @abstractmethod
    async def notify_new_event(self, agent_id: str, event: AgentEvent) -> None:
        """通知新事件"""
        pass

    @abstractmethod
    async def cleanup_agent_stream(self, agent_id: str) -> None:
        """清理agent的事件流"""
        pass 

class EventSubscriptionManager(Protocol):
    """事件订阅管理器接口"""

    @abstractmethod
    async def notify_event(self, agent_id: str, event: AgentEvent) -> None:
        """通知新事件"""
        pass
