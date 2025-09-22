import asyncio
import logging
import uuid
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Protocol

from .event import AgentEvent

logger = logging.getLogger(__name__)


class EventBuffer(Protocol):
    """事件缓冲抽象接口"""
    DEFAULT_MAX_SIZE = 1000  # 最大缓冲事件数量

    def __init__(self, agent_id: str, max_size: int = DEFAULT_MAX_SIZE):
        self.agent_id = agent_id
        self.max_size = max_size

    @abstractmethod
    def add_event(self, event: AgentEvent) -> int:
        """添加事件到缓冲区，返回序号"""
        pass

    @abstractmethod
    def get_events_from_sequence(self, from_sequence: int) -> List[AgentEvent]:
        """获取指定序号之后的事件"""
        pass

    @abstractmethod
    def has_done_event_as_last(self) -> bool:
        """检查最后一个事件是否是DoneEvent"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空缓冲区"""
        pass

    @property
    @abstractmethod
    def current_sequence(self) -> int:
        """获取当前序号"""
        pass


@dataclass
class EventSubscriber:
    """事件订阅者模型"""
    subscriber_id: str
    agent_id: str
    event_queue: asyncio.Queue
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    
    @classmethod
    def create(cls, agent_id: str) -> "EventSubscriber":
        """创建新的事件订阅者"""
        return cls(
            subscriber_id=str(uuid.uuid4()),
            agent_id=agent_id,
            event_queue=asyncio.Queue(maxsize=100)  # 限制队列大小防止内存泄漏
        )
    
    def update_activity(self) -> None:
        """更新活动时间"""
        self.last_activity = datetime.now()
    
    def deactivate(self) -> None:
        """停用订阅者"""
        self.is_active = False


@dataclass 
class AgentEventBroadcaster:
    """Agent事件广播器领域模型"""
    agent_id: str
    subscribers: Dict[str, EventSubscriber] = field(default_factory=dict)  # subscriber_id -> subscriber
    event_buffer: EventBuffer = None

    def __post_init__(self):
        """初始化后检查事件缓冲区"""
        if self.event_buffer is None:
            raise ValueError("Event buffer must be provided")
        if self.event_buffer.agent_id != self.agent_id:
            raise ValueError(f"Event buffer agent_id {self.event_buffer.agent_id} does not match broadcaster agent_id {self.agent_id}")

    def add_subscriber(self, subscriber: EventSubscriber) -> None:
        """添加订阅者"""
        if subscriber.agent_id != self.agent_id:
            raise ValueError(f"Subscriber agent_id {subscriber.agent_id} does not match broadcaster agent_id {self.agent_id}")
        self.subscribers[subscriber.subscriber_id] = subscriber
        logger.debug(f"Added subscriber {subscriber.subscriber_id} for agent {self.agent_id}")
    
    def remove_subscriber(self, subscriber_id: str) -> bool:
        """移除订阅者"""
        subscriber = self.subscribers.pop(subscriber_id, None)
        if subscriber:
            logger.debug(f"Removed subscriber {subscriber_id} for agent {self.agent_id}")
            return True
        return False

    def broadcast_event(self, event: AgentEvent) -> int:
        """广播事件给所有活跃订阅者，返回事件序号"""
        # 添加事件到缓冲区
        sequence = self.event_buffer.add_event(event)
        
        # 广播给所有活跃订阅者
        inactive_subscribers = []
        for subscriber_id, subscriber in self.subscribers.items():
            if not subscriber.is_active:
                inactive_subscribers.append(subscriber_id)
                continue
                
            try:
                # 非阻塞方式放入订阅者队列
                subscriber.event_queue.put_nowait(event)
                subscriber.update_activity()
                logger.debug(f"Broadcasted event to subscriber {subscriber_id}")
            except asyncio.QueueFull:
                logger.warning(f"Subscriber {subscriber_id} queue full, dropping event")
                # 标记为不活跃，稍后清理
                subscriber.deactivate()
                inactive_subscribers.append(subscriber_id)
        
        # 清理不活跃的订阅者
        for subscriber_id in inactive_subscribers:
            self.remove_subscriber(subscriber_id)
        
        logger.debug(f"Broadcasted event with sequence {sequence} to {len(self.subscribers)} subscribers for agent {self.agent_id}")
        return sequence

    def get_active_subscriber_count(self) -> int:
        """获取活跃订阅者数量"""
        return len([s for s in self.subscribers.values() if s.is_active])

    def cleanup_inactive_subscribers(self, timeout_minutes: int = 30) -> int:
        """清理不活跃的订阅者，返回清理数量"""
        cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)
        inactive_subscriber_ids = []
        
        for subscriber_id, subscriber in self.subscribers.items():
            if not subscriber.is_active or subscriber.last_activity < cutoff_time:
                inactive_subscriber_ids.append(subscriber_id)
        
        # 清理不活跃的订阅者
        for subscriber_id in inactive_subscriber_ids:
            self.remove_subscriber(subscriber_id)
        
        logger.info(f"Cleaned up {len(inactive_subscriber_ids)} inactive subscribers for agent {self.agent_id}")
        return len(inactive_subscriber_ids)
