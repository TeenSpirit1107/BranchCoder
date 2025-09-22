from typing import Optional, List, AsyncGenerator
import logging
from app.domain.models.event_subscription import AgentEventBroadcaster
from app.domain.models.event import AgentEvent
from app.domain.external.event_subscription_repository import (
    EventBroadcastRepository,
    EventStreamRepository,
    EventSubscriptionManager
)

logger = logging.getLogger(__name__)


class EventSubscriptionDomainService:
    """事件订阅领域服务 - 纯发布订阅模式"""

    def __init__(
        self,
        broadcast_repository: EventBroadcastRepository,
        stream_repository: EventStreamRepository,
        event_subscription_manager: EventSubscriptionManager
    ):
        self.broadcast_repository = broadcast_repository
        self.stream_repository = stream_repository
        self.event_subscription_manager = event_subscription_manager

    async def broadcast_event(self, agent_id: str, event: AgentEvent) -> int:
        """广播事件给指定Agent的所有订阅者"""
        logger.debug(f"Broadcasting event {type(event).__name__} for agent {agent_id}")
        
        # 如果有底层管理器，直接调用其notify_event方法（包含广播器创建逻辑）
        await self.event_subscription_manager.notify_event(agent_id, event)
        
        # 获取广播器来返回序号
        broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
        if broadcaster:
            return broadcaster.event_buffer.current_sequence
        return 1

    async def get_event_stream(self, agent_id: str, from_sequence: int = 1) -> AsyncGenerator[AgentEvent, None]:
        """获取事件流（包含历史事件和实时事件）"""
        logger.info(f"Getting event stream for agent {agent_id} from sequence {from_sequence}")
        
        async for event in self.stream_repository.get_events_from_sequence(agent_id, from_sequence):
            yield event

    async def get_buffered_events(self, agent_id: str, from_sequence: int = 1) -> List[AgentEvent]:
        """获取缓冲区中的事件"""
        return await self.stream_repository.get_buffered_events(agent_id, from_sequence)

    async def get_agent_subscription_count(self, agent_id: str) -> int:
        """获取Agent的活跃订阅者数量"""
        broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
        if not broadcaster:
            return 0
        return broadcaster.get_active_subscriber_count()

    async def cleanup_agent_streams(self, agent_id: str) -> bool:
        """清理Agent的所有事件流和订阅者"""
        logger.info(f"Cleaning up all streams for agent {agent_id}")
        
        # 清理流（包括所有订阅者）
        await self.stream_repository.cleanup_agent_stream(agent_id)
        
        # 删除广播器
        await self.broadcast_repository.delete_broadcaster(agent_id)
        
        logger.info(f"Cleaned up streams for agent {agent_id}")
        return True

    async def cleanup_inactive_subscribers(self, agent_id: str, timeout_minutes: int = 30) -> int:
        """清理指定Agent的不活跃订阅者"""
        broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
        if not broadcaster:
            return 0
        
        cleaned_count = broadcaster.cleanup_inactive_subscribers(timeout_minutes)
        
        if cleaned_count > 0:
            await self.broadcast_repository.update_broadcaster(broadcaster)
            logger.info(f"Cleaned up {cleaned_count} inactive subscribers for agent {agent_id}")
        
        return cleaned_count 