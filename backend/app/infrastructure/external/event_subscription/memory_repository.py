import asyncio
import logging
from typing import List, Optional, Dict, AsyncGenerator

from app.domain.external.event_subscription_repository import (
    EventBroadcastRepository,
    EventStreamRepository
)
from app.domain.models.event import AgentEvent, DoneEvent
from app.domain.models.event_subscription import AgentEventBroadcaster, EventSubscriber, EventBuffer

logger = logging.getLogger(__name__)


class MemoryEventBuffer:
    """内存版本的事件缓冲实现"""
    
    def __init__(self, agent_id: str, max_size: int = EventBuffer.DEFAULT_MAX_SIZE):
        self.agent_id = agent_id
        self.max_size = max_size
        self.events: List[AgentEvent] = []
        self._current_sequence: int = 0

    def add_event(self, event: AgentEvent) -> int:
        """添加事件到缓冲区，返回序号"""
        self._current_sequence += 1
        
        # 如果缓冲区满了，移除最老的事件
        if len(self.events) >= self.max_size:
            self.events.pop(0)
        
        self.events.append(event)
        return self._current_sequence

    def get_events_from_sequence(self, from_sequence: int) -> List[AgentEvent]:
        """获取指定序号之后的事件"""
        if from_sequence <= 0:
            return self.events.copy()
        
        # 计算起始位置
        start_index = max(0, from_sequence - (self._current_sequence - len(self.events) + 1))
        return self.events[start_index:]

    def has_done_event_as_last(self) -> bool:
        """检查最后一个事件是否是DoneEvent"""
        if not self.events:
            return False
        return isinstance(self.events[-1], DoneEvent)

    def clear(self) -> None:
        """清空缓冲区"""
        self.events.clear()

    @property
    def current_sequence(self) -> int:
        """获取当前序号"""
        return self._current_sequence


class MemoryEventBroadcastRepository(EventBroadcastRepository):
    """内存版本的事件广播仓储"""

    def __init__(self):
        self._broadcasters: Dict[str, AgentEventBroadcaster] = {}
        logger.info("MemoryEventBroadcastRepository initialized")

    def _create_broadcaster(self, agent_id: str) -> AgentEventBroadcaster:
        """创建新的广播器，使用内存版本的事件缓冲"""
        event_buffer = MemoryEventBuffer(agent_id)
        return AgentEventBroadcaster(
            agent_id=agent_id,
            event_buffer=event_buffer
        )

    async def save_broadcaster(self, broadcaster: AgentEventBroadcaster) -> None:
        """保存广播器"""
        self._broadcasters[broadcaster.agent_id] = broadcaster
        logger.debug(f"Saved broadcaster for agent {broadcaster.agent_id}")

    async def get_broadcaster(self, agent_id: str) -> Optional[AgentEventBroadcaster]:
        """获取广播器"""
        return self._broadcasters.get(agent_id)

    async def update_broadcaster(self, broadcaster: AgentEventBroadcaster) -> bool:
        """更新广播器"""
        if broadcaster.agent_id not in self._broadcasters:
            return False
        
        self._broadcasters[broadcaster.agent_id] = broadcaster
        logger.debug(f"Updated broadcaster for agent {broadcaster.agent_id}")
        return True

    async def delete_broadcaster(self, agent_id: str) -> bool:
        """删除广播器"""
        broadcaster = self._broadcasters.pop(agent_id, None)
        if broadcaster:
            logger.debug(f"Deleted broadcaster for agent {agent_id}")
            return True
        return False


class MemoryEventStreamRepository(EventStreamRepository):
    """内存版本的事件流仓储 - 发布订阅模式"""

    def __init__(self, broadcast_repository: MemoryEventBroadcastRepository):
        self.broadcast_repository = broadcast_repository
        logger.info("MemoryEventStreamRepository initialized with pub-sub pattern")

    async def get_events_from_sequence(self, agent_id: str, from_sequence: int = 1) -> AsyncGenerator[AgentEvent, None]:
        """从指定序号开始获取事件流（包含历史事件和实时事件）"""
        logger.info(f"Starting event stream for agent {agent_id} from sequence {from_sequence}")
        
        # 1. 首先检查是否有广播器，如果有的话检查是否已经有DoneEvent作为最后一个事件
        broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
        if broadcaster and broadcaster.event_buffer.has_done_event_as_last():
            # 如果最后一个事件是DoneEvent，只获取历史事件然后结束
            logger.info(f"Agent {agent_id} already has DoneEvent as last event, returning only buffered events")
            buffered_events = await self.get_buffered_events(agent_id, from_sequence)
            for event in buffered_events:
                yield event
            return
        
        # 2. 获取缓冲区中的历史事件 (不提前终止，即使遇到DoneEvent)
        buffered_events = await self.get_buffered_events(agent_id, from_sequence)
        for event in buffered_events:
            yield event
        
        # 3. 创建订阅者并注册到广播器
        subscriber = EventSubscriber.create(agent_id)
        await self._register_subscriber(agent_id, subscriber)
        
        try:
            # 4. 持续从订阅者的队列中获取实时事件
            while True:
                try:
                    # 使用超时来避免无限阻塞，同时更新活动时间
                    event = await asyncio.wait_for(subscriber.event_queue.get(), timeout=30.0)
                    subscriber.update_activity()
                    yield event
                    subscriber.event_queue.task_done()
                    
                    # 检查是否是DoneEvent，如果是则结束事件流
                    if isinstance(event, DoneEvent):
                        logger.info(f"Received DoneEvent for agent {agent_id}, terminating event stream")
                        return
                        
                except asyncio.TimeoutError:
                    # 超时时更新活动时间，保持连接活跃
                    subscriber.update_activity()
                    continue
        except asyncio.CancelledError:
            logger.info(f"Event stream for agent {agent_id} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in event stream for agent {agent_id}: {str(e)}")
            raise
        finally:
            # 5. 清理：注销订阅者
            await self._unregister_subscriber(agent_id, subscriber.subscriber_id)

    async def _register_subscriber(self, agent_id: str, subscriber: EventSubscriber) -> None:
        """注册订阅者到广播器"""
        # 获取或创建广播器
        broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
        if not broadcaster:
            broadcaster = self.broadcast_repository._create_broadcaster(agent_id)
            await self.broadcast_repository.save_broadcaster(broadcaster)
        
        # 添加订阅者
        broadcaster.add_subscriber(subscriber)
        await self.broadcast_repository.update_broadcaster(broadcaster)
        
        logger.debug(f"Registered subscriber {subscriber.subscriber_id} for agent {agent_id}")

    async def _unregister_subscriber(self, agent_id: str, subscriber_id: str) -> None:
        """从广播器中注销订阅者"""
        broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
        if broadcaster:
            broadcaster.remove_subscriber(subscriber_id)
            await self.broadcast_repository.update_broadcaster(broadcaster)
            logger.debug(f"Unregistered subscriber {subscriber_id} for agent {agent_id}")

    async def get_buffered_events(self, agent_id: str, from_sequence: int = 1) -> List[AgentEvent]:
        """获取缓冲区中的事件"""
        broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
        if not broadcaster:
            return []
        
        return broadcaster.event_buffer.get_events_from_sequence(from_sequence)

    async def notify_new_event(self, agent_id: str, event: AgentEvent) -> None:
        """通知新事件 - 通过广播器分发给所有订阅者"""
        # 获取或创建广播器
        broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
        if not broadcaster:
            broadcaster = self.broadcast_repository._create_broadcaster(agent_id)
            await self.broadcast_repository.save_broadcaster(broadcaster)
        
        # 广播事件
        broadcaster.broadcast_event(event)
        await self.broadcast_repository.update_broadcaster(broadcaster)
        
        logger.debug(f"Broadcasted event to {broadcaster.get_active_subscriber_count()} subscribers for agent {agent_id}")

    async def cleanup_agent_stream(self, agent_id: str) -> None:
        """清理agent的事件流"""
        broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
        if broadcaster:
            # 停用所有订阅者
            for subscriber in broadcaster.subscribers.values():
                subscriber.deactivate()
            # 清空订阅者列表
            broadcaster.subscribers.clear()
            await self.broadcast_repository.update_broadcaster(broadcaster)
            logger.debug(f"Cleaned up event stream for agent {agent_id}")


class MemoryEventSubscriptionManager:
    """内存版本的事件订阅管理器 - 纯发布订阅模式"""

    def __init__(self):
        self.broadcast_repository = MemoryEventBroadcastRepository()
        self.stream_repository = MemoryEventStreamRepository(self.broadcast_repository)
        logger.info("MemoryEventSubscriptionManager initialized with pure pub-sub pattern")

    async def notify_event(self, agent_id: str, event: AgentEvent) -> None:
        """通知新事件 - 直接通过流仓储的广播机制分发"""
        await self.stream_repository.notify_new_event(agent_id, event)

    async def cleanup_agent(self, agent_id: str) -> None:
        """清理agent相关的所有订阅资源"""
        # 清理流（包括所有订阅者）
        await self.stream_repository.cleanup_agent_stream(agent_id)
        
        # 清理广播器
        await self.broadcast_repository.delete_broadcaster(agent_id) 