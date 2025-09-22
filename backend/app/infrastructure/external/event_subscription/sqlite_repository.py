"""事件订阅仓储SQLite实现"""

import asyncio
import collections
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, AsyncGenerator

from sqlalchemy import select, delete, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

from app.domain.external.event_subscription_repository import (
    EventBroadcastRepository,
    EventStreamRepository
)
from app.domain.models.event import (
    AgentEvent, DoneEvent, MessageEvent, ErrorEvent, PauseEvent,
    ToolCallingEvent, ToolCalledEvent, ReportEvent, UserInputEvent,
    PlanCreatedEvent, PlanUpdatedEvent, StepStartedEvent, StepCompletedEvent,
    StepFailedEvent, PlanCompletedEvent
)
from app.domain.models.event_subscription import AgentEventBroadcaster, EventSubscriber, EventBuffer
from app.infrastructure.database.connection import get_session, get_readonly_session
from app.infrastructure.database.models import EventBroadcasterORM, BufferedEventORM, EventSubscriberORM

logger = logging.getLogger(__name__)


class SQLiteEventBuffer:
    """SQLite版本的事件缓冲实现 - 数据库持久化缓冲"""
    
    def __init__(self, agent_id: str, max_size: int = EventBuffer.DEFAULT_MAX_SIZE, engine: AsyncEngine = None):
        self.agent_id = agent_id
        self.max_size = max_size
        self.engine = engine
        self._current_sequence: int = 0
        # 内存缓存，用于快速访问最近的事件
        self._memory_cache: List[AgentEvent] = []

    def _create_event_from_data(self, event_type: str, event_data: dict) -> Optional[AgentEvent]:
        """根据事件类型和数据创建具体的事件对象"""
        try:
            if event_type == "message":
                return MessageEvent(**event_data)
            elif event_type == "error":
                return ErrorEvent(**event_data)
            elif event_type == "pause":
                return PauseEvent(**event_data)
            elif event_type == "tool_calling":
                return ToolCallingEvent(**event_data)
            elif event_type == "tool_called":
                return ToolCalledEvent(**event_data)
            elif event_type == "report":
                return ReportEvent(**event_data)
            elif event_type == "user_input":
                return UserInputEvent(**event_data)
            elif event_type == "done":
                return DoneEvent(**event_data)
            elif event_type == "plan_created":
                return PlanCreatedEvent(**event_data)
            elif event_type == "plan_updated":
                return PlanUpdatedEvent(**event_data)
            elif event_type == "plan_completed":
                return PlanCompletedEvent(**event_data)
            elif event_type == "step_started":
                return StepStartedEvent(**event_data)
            elif event_type == "step_completed":
                return StepCompletedEvent(**event_data)
            elif event_type == "step_failed":
                return StepFailedEvent(**event_data)
            else:
                # 对于未知类型，创建基础AgentEvent
                return AgentEvent(type=event_type)
        except Exception as e:
            logger.warning(f"Failed to create event from data: {event_type}, {event_data}, error: {str(e)}")
            return None

    async def _load_events_from_db(self) -> None:
        """从数据库加载事件到内存缓存"""
        logger.debug(f"[SQLiteEventBuffer] _load_events_from_db 开始 - agent_id: {self.agent_id}")
        
        if not self.engine:
            logger.debug(f"[SQLiteEventBuffer] 没有数据库引擎，跳过加载 - agent_id: {self.agent_id}")
            return
            
        try:
            logger.debug(f"[SQLiteEventBuffer] 创建数据库会话 - agent_id: {self.agent_id}")
            async with get_readonly_session(self.engine) as session:
                logger.debug(f"[SQLiteEventBuffer] 数据库会话已创建，开始查询事件 - agent_id: {self.agent_id}")
                
                # 获取最新的事件，按序号排序
                stmt = select(BufferedEventORM).where(
                    BufferedEventORM.agent_id == self.agent_id
                ).order_by(BufferedEventORM.sequence.desc()).limit(self.max_size)
                
                logger.debug(f"[SQLiteEventBuffer] 执行查询语句 - agent_id: {self.agent_id}, max_size: {self.max_size}")
                result = await session.execute(stmt)
                buffered_events = result.scalars().all()
                
                logger.debug(f"[SQLiteEventBuffer] 查询到 {len(buffered_events)} 个事件 - agent_id: {self.agent_id}")
                
                # 按序号正序排列
                buffered_events = sorted(buffered_events, key=lambda x: x.sequence)
                
                # 转换为领域事件对象
                self._memory_cache = []
                for buffered_event_orm in buffered_events:
                    logger.debug(f"[SQLiteEventBuffer] 转换事件 - agent_id: {self.agent_id}, sequence: {buffered_event_orm.sequence}, type: {buffered_event_orm.event_type}")
                    event = self._create_event_from_data(
                        buffered_event_orm.event_type, 
                        buffered_event_orm.event_data
                    )
                    if event:
                        self._memory_cache.append(event)
                    else:
                        logger.warning(f"[SQLiteEventBuffer] 事件转换失败 - agent_id: {self.agent_id}, sequence: {buffered_event_orm.sequence}")
                
                # 更新当前序号
                if buffered_events:
                    self._current_sequence = max(event.sequence for event in buffered_events)
                    logger.debug(f"[SQLiteEventBuffer] 更新当前序号 - agent_id: {self.agent_id}, current_sequence: {self._current_sequence}")
                else:
                    logger.debug(f"[SQLiteEventBuffer] 没有事件，保持当前序号 - agent_id: {self.agent_id}, current_sequence: {self._current_sequence}")
                    
                logger.debug(f"[SQLiteEventBuffer] _load_events_from_db 完成 - agent_id: {self.agent_id}, 加载了 {len(self._memory_cache)} 个事件")
                
        except Exception as e:
            logger.error(f"[SQLiteEventBuffer] _load_events_from_db 异常 - agent_id: {self.agent_id}, 错误: {str(e)}", exc_info=True)
            raise

    # 同步接口（用于向后兼容）
    def add_event(self, event: AgentEvent) -> int:
        """添加事件到缓冲区，返回序号（同步版本，仅更新内存缓存）"""
        if not self.engine:
            # 如果没有数据库引擎，回退到内存模式
            return self._add_event_memory_only(event)
        
        # 对于有数据库引擎的情况，只更新内存缓存，数据库操作需要调用异步版本
        self._current_sequence += 1
        
        if len(self._memory_cache) >= self.max_size:
            self._memory_cache.pop(0)
        
        self._memory_cache.append(event)
        logger.debug(f"Added event to memory cache for agent {self.agent_id}, sequence: {self._current_sequence}")
        return self._current_sequence

    async def add_event_async(self, event: AgentEvent) -> int:
        """添加事件到缓冲区，同时保存到数据库（异步版本）"""
        logger.debug(f"[SQLiteEventBuffer] add_event_async 开始 - agent_id: {self.agent_id}, event_type: {event.type}")
        
        if not self.engine:
            logger.debug(f"[SQLiteEventBuffer] 没有数据库引擎，使用内存模式 - agent_id: {self.agent_id}")
            # 如果没有数据库引擎，回退到内存模式
            return self._add_event_memory_only(event)
        
        self._current_sequence += 1
        sequence = self._current_sequence
        logger.debug(f"[SQLiteEventBuffer] 分配序号 - agent_id: {self.agent_id}, sequence: {sequence}")
        
        try:
            logger.debug(f"[SQLiteEventBuffer] 创建数据库会话 - agent_id: {self.agent_id}")
            async with get_session(self.engine) as session:
                logger.debug(f"[SQLiteEventBuffer] 数据库会话已创建 - agent_id: {self.agent_id}")
                
                try:
                    # 1. 保存事件到数据库
                    event_id = str(uuid.uuid4())
                    logger.debug(f"[SQLiteEventBuffer] 创建BufferedEventORM - agent_id: {self.agent_id}, event_id: {event_id}, sequence: {sequence}")
                    
                    buffered_event_orm = BufferedEventORM(
                        id=event_id,
                        agent_id=self.agent_id,
                        sequence=sequence,
                        event_type=event.type,
                        event_data=event.model_dump(),
                        timestamp=datetime.now()
                    )
                    session.add(buffered_event_orm)
                    logger.debug(f"[SQLiteEventBuffer] BufferedEventORM已添加到会话 - agent_id: {self.agent_id}")
                    
                    # 2. 如果缓冲区满了，删除最老的事件
                    event_count = await self._get_event_count(session)
                    logger.debug(f"[SQLiteEventBuffer] 当前事件数量: {event_count}, 最大容量: {self.max_size} - agent_id: {self.agent_id}")
                    
                    if event_count >= self.max_size:
                        logger.debug(f"[SQLiteEventBuffer] 缓冲区已满，删除最老事件 - agent_id: {self.agent_id}")
                        await self._remove_oldest_event(session)
                        logger.debug(f"[SQLiteEventBuffer] 最老事件已删除 - agent_id: {self.agent_id}")
                    
                    logger.debug(f"[SQLiteEventBuffer] 提交数据库事务 - agent_id: {self.agent_id}")
                    await session.commit()
                    logger.debug(f"[SQLiteEventBuffer] 数据库事务已提交 - agent_id: {self.agent_id}")
                    
                    # 3. 更新内存缓存
                    if len(self._memory_cache) >= self.max_size:
                        removed_event = self._memory_cache.pop(0)
                        logger.debug(f"[SQLiteEventBuffer] 从内存缓存移除最老事件 - agent_id: {self.agent_id}, removed_type: {removed_event.type}")
                    
                    self._memory_cache.append(event)
                    logger.debug(f"[SQLiteEventBuffer] 事件已添加到内存缓存 - agent_id: {self.agent_id}, cache_size: {len(self._memory_cache)}")
                    
                    logger.debug(f"[SQLiteEventBuffer] add_event_async 成功完成 - agent_id: {self.agent_id}, sequence: {sequence}")
                    return sequence
                    
                except Exception as e:
                    logger.error(f"[SQLiteEventBuffer] 数据库操作异常，回滚事务 - agent_id: {self.agent_id}, 错误: {str(e)}", exc_info=True)
                    await session.rollback()
                    raise
                    
        except Exception as e:
            logger.error(f"[SQLiteEventBuffer] add_event_async 失败 - agent_id: {self.agent_id}, 错误: {str(e)}", exc_info=True)
            raise

    def _add_event_memory_only(self, event: AgentEvent) -> int:
        """仅内存模式添加事件（回退方案）"""
        self._current_sequence += 1
        
        if len(self._memory_cache) >= self.max_size:
            self._memory_cache.pop(0)
        
        self._memory_cache.append(event)
        return self._current_sequence

    async def _get_event_count(self, session: AsyncSession) -> int:
        """获取当前agent的事件数量"""
        logger.debug(f"[SQLiteEventBuffer] _get_event_count 开始 - agent_id: {self.agent_id}")
        
        try:
            stmt = select(func.count(BufferedEventORM.id)).where(
                BufferedEventORM.agent_id == self.agent_id
            )
            logger.debug(f"[SQLiteEventBuffer] 执行计数查询 - agent_id: {self.agent_id}")
            result = await session.execute(stmt)
            count = result.scalar() or 0
            logger.debug(f"[SQLiteEventBuffer] _get_event_count 完成 - agent_id: {self.agent_id}, count: {count}")
            return count
        except Exception as e:
            logger.error(f"[SQLiteEventBuffer] _get_event_count 异常 - agent_id: {self.agent_id}, 错误: {str(e)}", exc_info=True)
            raise

    async def _remove_oldest_event(self, session: AsyncSession) -> None:
        """删除最老的事件"""
        logger.debug(f"[SQLiteEventBuffer] _remove_oldest_event 开始 - agent_id: {self.agent_id}")
        
        try:
            # 获取最小序号的事件
            stmt = select(BufferedEventORM.sequence).where(
                BufferedEventORM.agent_id == self.agent_id
            ).order_by(BufferedEventORM.sequence.asc()).limit(1)
            
            logger.debug(f"[SQLiteEventBuffer] 查询最老事件序号 - agent_id: {self.agent_id}")
            result = await session.execute(stmt)
            oldest_sequence = result.scalar()
            
            if oldest_sequence is not None:
                logger.debug(f"[SQLiteEventBuffer] 找到最老事件序号: {oldest_sequence} - agent_id: {self.agent_id}")
                # 删除最老的事件
                delete_stmt = delete(BufferedEventORM).where(
                    BufferedEventORM.agent_id == self.agent_id,
                    BufferedEventORM.sequence == oldest_sequence
                )
                result = await session.execute(delete_stmt)
                deleted_count = result.rowcount
                logger.debug(f"[SQLiteEventBuffer] _remove_oldest_event 完成 - agent_id: {self.agent_id}, deleted_count: {deleted_count}")
            else:
                logger.warning(f"[SQLiteEventBuffer] 没有找到最老事件 - agent_id: {self.agent_id}")
                
        except Exception as e:
            logger.error(f"[SQLiteEventBuffer] _remove_oldest_event 异常 - agent_id: {self.agent_id}, 错误: {str(e)}", exc_info=True)
            raise

    # 同步接口（用于向后兼容）
    def get_events_from_sequence(self, from_sequence: int) -> List[AgentEvent]:
        """获取指定序号之后的事件（同步版本，仅从内存缓存获取）"""
        return self._get_events_from_sequence_memory(from_sequence)

    async def get_events_from_sequence_async(self, from_sequence: int) -> List[AgentEvent]:
        """获取指定序号之后的事件（异步版本，从数据库获取）"""
        if not self.engine:
            # 如果没有数据库引擎，使用内存缓存
            return self._get_events_from_sequence_memory(from_sequence)
        
        async with get_readonly_session(self.engine) as session:
            # 从数据库获取事件
            stmt = select(BufferedEventORM).where(
                BufferedEventORM.agent_id == self.agent_id,
                BufferedEventORM.sequence >= from_sequence
            ).order_by(BufferedEventORM.sequence.asc())
            
            result = await session.execute(stmt)
            buffered_events = result.scalars().all()
            
            # 转换为领域事件对象
            events = []
            for buffered_event_orm in buffered_events:
                event = self._create_event_from_data(
                    buffered_event_orm.event_type,
                    buffered_event_orm.event_data
                )
                if event:
                    events.append(event)
            
            return events

    def _get_events_from_sequence_memory(self, from_sequence: int) -> List[AgentEvent]:
        """从内存缓存获取指定序号之后的事件（回退方案）"""
        if from_sequence <= 0:
            return self._memory_cache.copy()
        
        # 计算起始位置
        start_index = max(0, from_sequence - (self._current_sequence - len(self._memory_cache) + 1))
        return self._memory_cache[start_index:]

    # 同步接口（用于向后兼容）
    def has_done_event_as_last(self) -> bool:
        """检查最后一个事件是否是DoneEvent（同步版本，仅检查内存缓存）"""
        if not self._memory_cache:
            return False
        return isinstance(self._memory_cache[-1], DoneEvent)

    async def has_done_event_as_last_async(self) -> bool:
        """检查最后一个事件是否是DoneEvent（异步版本，检查数据库）"""
        if not self.engine:
            # 如果没有数据库引擎，检查内存缓存
            if not self._memory_cache:
                return False
            return isinstance(self._memory_cache[-1], DoneEvent)
        
        async with get_readonly_session(self.engine) as session:
            # 获取最新的事件
            stmt = select(BufferedEventORM).where(
                BufferedEventORM.agent_id == self.agent_id
            ).order_by(BufferedEventORM.sequence.desc()).limit(1)
            
            result = await session.execute(stmt)
            latest_event_orm = result.scalar_one_or_none()
            
            if not latest_event_orm:
                return False
            
            # 检查是否是DoneEvent
            return latest_event_orm.event_type == "done"

    async def clear_async(self) -> None:
        """清空缓冲区（异步版本，清空数据库和内存缓存）"""
        if not self.engine:
            # 如果没有数据库引擎，只清空内存缓存
            self._memory_cache.clear()
            return
        
        async with get_session(self.engine) as session:
            try:
                # 删除数据库中的所有事件
                stmt = delete(BufferedEventORM).where(
                    BufferedEventORM.agent_id == self.agent_id
                )
                await session.execute(stmt)
                await session.commit()
                
                # 清空内存缓存
                self._memory_cache.clear()
                
                logger.debug(f"Cleared buffer for agent {self.agent_id}")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to clear buffer for agent {self.agent_id}: {str(e)}")
                raise

    def clear(self) -> None:
        """清空缓冲区（同步版本，仅清空内存缓存）"""
        self._memory_cache.clear()
        logger.debug(f"Cleared memory cache for agent {self.agent_id}")

    @property
    def current_sequence(self) -> int:
        """获取当前序号"""
        return self._current_sequence

    @property
    def events(self) -> List[AgentEvent]:
        """获取内存缓存中的事件（用于兼容性）"""
        return self._memory_cache.copy()

    async def initialize(self) -> None:
        """初始化缓冲区，从数据库加载事件"""
        logger.debug(f"[SQLiteEventBuffer] initialize 开始 - agent_id: {self.agent_id}")
        
        if self.engine:
            logger.debug(f"[SQLiteEventBuffer] 有数据库引擎，开始加载事件 - agent_id: {self.agent_id}")
            await self._load_events_from_db()
            logger.debug(f"[SQLiteEventBuffer] initialize 完成 - agent_id: {self.agent_id}, 内存缓存大小: {len(self._memory_cache)}")
        else:
            logger.debug(f"[SQLiteEventBuffer] 没有数据库引擎，跳过初始化 - agent_id: {self.agent_id}")


class SQLiteEventBroadcastRepository(EventBroadcastRepository):
    """SQLite版本的事件广播仓储"""

    def __init__(self, engine: AsyncEngine):
        """初始化事件广播仓储
        
        Args:
            engine: 数据库引擎
        """
        self.engine = engine

    def _create_broadcaster(self, agent_id: str) -> AgentEventBroadcaster:
        """创建新的广播器，使用SQLite版本的事件缓冲"""
        event_buffer = SQLiteEventBuffer(agent_id, engine=self.engine)
        return AgentEventBroadcaster(
            agent_id=agent_id,
            event_buffer=event_buffer
        )

    async def _orm_to_domain_broadcaster(self, broadcaster_orm: EventBroadcasterORM) -> AgentEventBroadcaster:
        """将广播器ORM模型转换为领域模型"""
        logger.debug(f"[SQLiteEventBroadcastRepository] _orm_to_domain_broadcaster 开始 - agent_id: {broadcaster_orm.agent_id}")
        
        try:
            # 创建事件缓冲区
            logger.debug(f"[SQLiteEventBroadcastRepository] 创建SQLiteEventBuffer - agent_id: {broadcaster_orm.agent_id}, max_size: {broadcaster_orm.max_buffer_size}")
            event_buffer = SQLiteEventBuffer(
                agent_id=broadcaster_orm.agent_id,
                max_size=broadcaster_orm.max_buffer_size,
                engine=self.engine
            )
            event_buffer._current_sequence = broadcaster_orm.current_sequence
            logger.debug(f"[SQLiteEventBroadcastRepository] 设置当前序号 - agent_id: {broadcaster_orm.agent_id}, current_sequence: {broadcaster_orm.current_sequence}")
            
            # 初始化缓冲区（从数据库加载事件）
            logger.debug(f"[SQLiteEventBroadcastRepository] 初始化事件缓冲区 - agent_id: {broadcaster_orm.agent_id}")
            await event_buffer.initialize()
            logger.debug(f"[SQLiteEventBroadcastRepository] 事件缓冲区初始化完成 - agent_id: {broadcaster_orm.agent_id}")
            
            broadcaster = AgentEventBroadcaster(
                agent_id=broadcaster_orm.agent_id,
                subscribers={},  # 订阅者不持久化，每次重启都是新的
                event_buffer=event_buffer
            )
            
            logger.debug(f"[SQLiteEventBroadcastRepository] _orm_to_domain_broadcaster 完成 - agent_id: {broadcaster_orm.agent_id}")
            return broadcaster
            
        except Exception as e:
            logger.error(f"[SQLiteEventBroadcastRepository] _orm_to_domain_broadcaster 异常 - agent_id: {broadcaster_orm.agent_id}, 错误: {str(e)}", exc_info=True)
            raise

    def _domain_to_orm_broadcaster(self, broadcaster: AgentEventBroadcaster) -> EventBroadcasterORM:
        """将广播器领域模型转换为ORM模型"""
        return EventBroadcasterORM(
            agent_id=broadcaster.agent_id,
            current_sequence=broadcaster.event_buffer.current_sequence,
            max_buffer_size=broadcaster.event_buffer.max_size,
            updated_at=datetime.now()
        )

    async def save_broadcaster(self, broadcaster: AgentEventBroadcaster) -> None:
        """保存广播器。假定调用者已处理并发和锁定。"""
        async with get_session(self.engine) as session:
            try:
                # 检查广播器是否已存在
                stmt = select(EventBroadcasterORM).where(EventBroadcasterORM.agent_id == broadcaster.agent_id)
                result = await session.execute(stmt)
                existing_broadcaster_orm = result.scalar_one_or_none()
                
                if existing_broadcaster_orm:
                    # 更新现有广播器
                    existing_broadcaster_orm.current_sequence = broadcaster.event_buffer.current_sequence
                    existing_broadcaster_orm.max_buffer_size = broadcaster.event_buffer.max_size
                    existing_broadcaster_orm.updated_at = datetime.now()
                    logger.debug(f"保存广播器时发现已存在，执行更新: {broadcaster.agent_id}")
                else:
                    # 创建新广播器
                    broadcaster_orm = self._domain_to_orm_broadcaster(broadcaster)
                    session.add(broadcaster_orm)
                    logger.debug(f"保存新的广播器: {broadcaster.agent_id}")
                
                await session.commit()
                
            except IntegrityError as e:
                await session.rollback()
                logger.error(f"保存广播器时发生IntegrityError: {broadcaster.agent_id}, 错误: {str(e)}")
                raise
            except Exception as e:
                await session.rollback()
                logger.error(f"保存广播器失败: {broadcaster.agent_id}, 错误: {str(e)}")
                raise

    async def create_broadcaster_if_not_exists(self, agent_id: str) -> None:
        """
        原子性地创建新的广播器数据库条目（如果尚不存在）。
        使用 SQLite 的 INSERT ... ON CONFLICT DO NOTHING。
        """
        logger.debug(f"[SQLiteEventBroadcastRepository] create_broadcaster_if_not_exists 开始 - agent_id: {agent_id}")
        
        broadcaster_orm_values = {
            "agent_id": agent_id,
            "current_sequence": 0,
            "max_buffer_size": EventBuffer.DEFAULT_MAX_SIZE, 
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        logger.debug(f"[SQLiteEventBroadcastRepository] 准备插入广播器数据 - agent_id: {agent_id}, values: {broadcaster_orm_values}")
        
        # 构造 INSERT ... ON CONFLICT DO NOTHING 语句
        stmt = sqlite_insert(EventBroadcasterORM).values(broadcaster_orm_values)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=['agent_id']
        )
        
        logger.debug(f"[SQLiteEventBroadcastRepository] SQL语句已构造 - agent_id: {agent_id}")

        try:
            logger.debug(f"[SQLiteEventBroadcastRepository] 创建数据库会话 - agent_id: {agent_id}")
            async with get_session(self.engine) as session:
                logger.debug(f"[SQLiteEventBroadcastRepository] 数据库会话已创建 - agent_id: {agent_id}")
                
                try:
                    logger.debug(f"[SQLiteEventBroadcastRepository] 执行INSERT ... ON CONFLICT DO NOTHING - agent_id: {agent_id}")
                    result = await session.execute(stmt)
                    logger.debug(f"[SQLiteEventBroadcastRepository] INSERT执行完成 - agent_id: {agent_id}, rowcount: {result.rowcount}")
                    
                    logger.debug(f"[SQLiteEventBroadcastRepository] 提交事务 - agent_id: {agent_id}")
                    await session.commit()
                    logger.debug(f"[SQLiteEventBroadcastRepository] 事务已提交 - agent_id: {agent_id}")
                    
                    # 验证插入结果
                    logger.debug(f"[SQLiteEventBroadcastRepository] 验证插入结果 - agent_id: {agent_id}")
                    verify_stmt = select(EventBroadcasterORM).where(EventBroadcasterORM.agent_id == agent_id)
                    verify_result = await session.execute(verify_stmt)
                    verify_broadcaster = verify_result.scalar_one_or_none()
                    
                    if verify_broadcaster:
                        logger.debug(f"[SQLiteEventBroadcastRepository] 验证成功：广播器已存在 - agent_id: {agent_id}, current_sequence: {verify_broadcaster.current_sequence}")
                    else:
                        logger.error(f"[SQLiteEventBroadcastRepository] 验证失败：广播器不存在 - agent_id: {agent_id}")
                    
                    logger.debug(f"[SQLiteEventBroadcastRepository] create_broadcaster_if_not_exists 成功完成 - agent_id: {agent_id}")
                    
                except Exception as e:
                    logger.error(f"[SQLiteEventBroadcastRepository] 数据库操作异常，回滚事务 - agent_id: {agent_id}, 错误: {str(e)}", exc_info=True)
                    await session.rollback()
                    raise
                    
        except Exception as e:
            logger.error(f"[SQLiteEventBroadcastRepository] create_broadcaster_if_not_exists 失败 - agent_id: {agent_id}, 错误: {str(e)}", exc_info=True)
            raise

    async def get_broadcaster(self, agent_id: str) -> Optional[AgentEventBroadcaster]:
        """获取广播器"""
        logger.debug(f"[SQLiteEventBroadcastRepository] get_broadcaster 开始 - agent_id: {agent_id}")
        
        # 先获取ORM对象
        broadcaster_orm = None
        try:
            logger.debug(f"[SQLiteEventBroadcastRepository] 创建数据库会话 - agent_id: {agent_id}")
            async with get_readonly_session(self.engine) as session:
                logger.debug(f"[SQLiteEventBroadcastRepository] 数据库会话已创建，查询广播器 - agent_id: {agent_id}")
                stmt = select(EventBroadcasterORM).where(EventBroadcasterORM.agent_id == agent_id)
                result = await session.execute(stmt)
                broadcaster_orm = result.scalar_one_or_none()
                
                if broadcaster_orm:
                    logger.debug(f"[SQLiteEventBroadcastRepository] 找到广播器ORM - agent_id: {agent_id}, current_sequence: {broadcaster_orm.current_sequence}")
                else:
                    logger.debug(f"[SQLiteEventBroadcastRepository] 未找到广播器ORM - agent_id: {agent_id}")
                    
        except Exception as e:
            logger.error(f"[SQLiteEventBroadcastRepository] 查询广播器ORM异常 - agent_id: {agent_id}, 错误: {str(e)}", exc_info=True)
            raise
            
        # 在session外部进行转换，避免嵌套session问题
        if broadcaster_orm:
            logger.debug(f"[SQLiteEventBroadcastRepository] 开始转换ORM到领域模型 - agent_id: {agent_id}")
            try:
                broadcaster = await self._orm_to_domain_broadcaster(broadcaster_orm)
                logger.debug(f"[SQLiteEventBroadcastRepository] get_broadcaster 成功完成 - agent_id: {agent_id}")
                return broadcaster
            except Exception as e:
                logger.error(f"[SQLiteEventBroadcastRepository] 转换ORM到领域模型异常 - agent_id: {agent_id}, 错误: {str(e)}", exc_info=True)
                raise
        else:
            logger.debug(f"[SQLiteEventBroadcastRepository] get_broadcaster 返回None - agent_id: {agent_id}")
            return None

    async def update_broadcaster(self, broadcaster: AgentEventBroadcaster) -> bool:
        """更新广播器"""
        async with get_session(self.engine) as session:
            try:
                stmt = select(EventBroadcasterORM).where(EventBroadcasterORM.agent_id == broadcaster.agent_id)
                result = await session.execute(stmt)
                existing_broadcaster = result.scalar_one_or_none()
                
                if not existing_broadcaster:
                    return False
                
                # 更新广播器信息
                existing_broadcaster.current_sequence = broadcaster.event_buffer.current_sequence
                existing_broadcaster.max_buffer_size = broadcaster.event_buffer.max_size
                existing_broadcaster.updated_at = datetime.now()
                
                await session.commit()
                logger.debug(f"更新广播器: {broadcaster.agent_id}")
                return True
                
            except Exception as e:
                await session.rollback()
                logger.error(f"更新广播器失败: {broadcaster.agent_id}, 错误: {str(e)}")
                raise

    async def delete_broadcaster(self, agent_id: str) -> bool:
        """删除广播器"""
        async with get_session(self.engine) as session:
            try:
                # 先删除缓冲事件（由于外键约束，会自动级联删除）
                stmt_delete_events = delete(BufferedEventORM).where(BufferedEventORM.agent_id == agent_id)
                await session.execute(stmt_delete_events)
                
                # 再删除广播器
                stmt_delete_broadcaster = delete(EventBroadcasterORM).where(EventBroadcasterORM.agent_id == agent_id)
                result = await session.execute(stmt_delete_broadcaster)
                
                await session.commit()
                
                deleted_count = result.rowcount
                if deleted_count > 0:
                    logger.debug(f"删除广播器: {agent_id}")
                    return True
                return False
                
            except Exception as e:
                await session.rollback()
                logger.error(f"删除广播器失败: {agent_id}, 错误: {str(e)}")
                raise


class SQLiteEventStreamRepository(EventStreamRepository):
    """SQLite版本的事件流仓储 - 数据库持久化订阅者"""

    def __init__(self, broadcast_repository: SQLiteEventBroadcastRepository):
        self.broadcast_repository = broadcast_repository
        self.engine = broadcast_repository.engine
        logger.debug("SQLiteEventStreamRepository initialized with database-persisted subscribers")

    async def get_events_from_sequence(self, agent_id: str, from_sequence: int = 1) -> AsyncGenerator[AgentEvent, None]:
        """从指定序号开始获取事件流（包含历史事件和实时事件）"""
        logger.debug(f"Starting event stream for agent {agent_id} from sequence {from_sequence}")
        
        # 1. 首先检查是否有广播器，如果有的话检查是否已经有DoneEvent作为最后一个事件
        broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
        if broadcaster and await broadcaster.event_buffer.has_done_event_as_last_async():
            # 如果最后一个事件是DoneEvent，只获取历史事件然后结束
            logger.debug(f"Agent {agent_id} already has DoneEvent as last event, returning only buffered events")
            buffered_events = await self.get_buffered_events(agent_id, from_sequence)
            for event in buffered_events:
                yield event
            return
        
        # 2. 获取缓冲区中的历史事件
        buffered_events = await self.get_buffered_events(agent_id, from_sequence)
        current_sequence = from_sequence
        for event in buffered_events:
            yield event
            current_sequence += 1
        
        # 3. 创建订阅者并注册到数据库
        subscriber = EventSubscriber.create(agent_id)
        await self._register_subscriber_db(agent_id, subscriber)
        
        try:
            # 4. 轮询获取新事件（基于数据库的实时事件流）
            last_check_sequence = current_sequence - 1
            consecutive_empty_checks = 0
            max_consecutive_empty_checks = 10  # 最多连续10次空检查后增加轮询间隔
            
            while True:
                try:
                    # 更新订阅者活动时间
                    await self._update_subscriber_activity(subscriber.subscriber_id)
                    
                    # 从数据库获取新事件
                    new_events = await self.get_buffered_events(agent_id, last_check_sequence + 1)
                    
                    if new_events:
                        consecutive_empty_checks = 0
                        for event in new_events:
                            yield event
                            last_check_sequence += 1
                            
                            # 检查是否是DoneEvent，如果是则结束事件流
                            if isinstance(event, DoneEvent):
                                logger.debug(f"Received DoneEvent for agent {agent_id}, terminating event stream")
                                return
                    else:
                        consecutive_empty_checks += 1
                    
                    # 动态调整轮询间隔：如果连续多次没有新事件，增加轮询间隔
                    if consecutive_empty_checks < max_consecutive_empty_checks:
                        poll_interval = 1.0  # 1秒
                    else:
                        poll_interval = 5.0  # 5秒
                    
                    # 等待一段时间再次检查
                    await asyncio.sleep(poll_interval)
                    
                except asyncio.CancelledError:
                    logger.debug(f"Event stream for agent {agent_id} was cancelled")
                    raise
                except Exception as e:
                    logger.error(f"Error polling events for agent {agent_id}: {str(e)}")
                    # 发生错误时等待一段时间再重试
                    await asyncio.sleep(2.0)
                    
        except asyncio.CancelledError:
            logger.debug(f"Event stream for agent {agent_id} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in event stream for agent {agent_id}: {str(e)}")
            raise
        finally:
            # 5. 清理：注销订阅者
            await self._unregister_subscriber_db(subscriber.subscriber_id)

    async def _register_subscriber_db(self, agent_id: str, subscriber: EventSubscriber) -> None:
        """在数据库中注册订阅者"""
        logger.debug(f"[SQLiteEventStreamRepository] _register_subscriber_db 开始 - agent_id: {agent_id}, subscriber_id: {subscriber.subscriber_id}")
        
        try:
            async with get_session(self.engine) as session:
                logger.debug(f"[SQLiteEventStreamRepository] 数据库会话已创建 - subscriber_id: {subscriber.subscriber_id}")
                
                try:
                    subscriber_orm = EventSubscriberORM(
                        subscriber_id=subscriber.subscriber_id,
                        agent_id=agent_id,
                        created_at=subscriber.created_at,
                        last_activity=subscriber.last_activity,
                        is_active="true",
                        heartbeat_timeout_seconds=300
                    )
                    session.add(subscriber_orm)
                    logger.debug(f"[SQLiteEventStreamRepository] EventSubscriberORM已添加到会话 - subscriber_id: {subscriber.subscriber_id}")
                    
                    await session.commit()
                    logger.debug(f"[SQLiteEventStreamRepository] _register_subscriber_db 成功完成 - subscriber_id: {subscriber.subscriber_id}")
                    
                except Exception as e:
                    logger.error(f"[SQLiteEventStreamRepository] 数据库操作异常，回滚事务 - subscriber_id: {subscriber.subscriber_id}, 错误: {str(e)}", exc_info=True)
                    await session.rollback()
                    raise
                    
        except Exception as e:
            logger.error(f"[SQLiteEventStreamRepository] _register_subscriber_db 失败 - subscriber_id: {subscriber.subscriber_id}, 错误: {str(e)}", exc_info=True)
            raise

    async def _unregister_subscriber_db(self, subscriber_id: str) -> None:
        """从数据库中注销订阅者"""
        async with get_session(self.engine) as session:
            try:
                stmt = delete(EventSubscriberORM).where(EventSubscriberORM.subscriber_id == subscriber_id)
                await session.execute(stmt)
                await session.commit()
                logger.debug(f"Unregistered subscriber {subscriber_id} from database")
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to unregister subscriber {subscriber_id}: {str(e)}")
                raise

    async def _update_subscriber_activity(self, subscriber_id: str) -> None:
        """更新订阅者活动时间"""
        logger.debug(f"[SQLiteEventStreamRepository] _update_subscriber_activity 开始 - subscriber_id: {subscriber_id}")
        
        try:
            async with get_session(self.engine) as session:
                logger.debug(f"[SQLiteEventStreamRepository] 数据库会话已创建 - subscriber_id: {subscriber_id}")
                
                try:
                    stmt = select(EventSubscriberORM).where(EventSubscriberORM.subscriber_id == subscriber_id)
                    result = await session.execute(stmt)
                    subscriber_orm = result.scalar_one_or_none()
                    
                    if subscriber_orm:
                        old_activity = subscriber_orm.last_activity
                        subscriber_orm.last_activity = datetime.now()
                        logger.debug(f"[SQLiteEventStreamRepository] 更新活动时间 - subscriber_id: {subscriber_id}, old: {old_activity}, new: {subscriber_orm.last_activity}")
                        await session.commit()
                        logger.debug(f"[SQLiteEventStreamRepository] _update_subscriber_activity 成功完成 - subscriber_id: {subscriber_id}")
                    else:
                        logger.warning(f"[SQLiteEventStreamRepository] 订阅者不存在 - subscriber_id: {subscriber_id}")
                        
                except Exception as e:
                    logger.error(f"[SQLiteEventStreamRepository] 数据库操作异常，回滚事务 - subscriber_id: {subscriber_id}, 错误: {str(e)}", exc_info=True)
                    await session.rollback()
                    raise
                    
        except Exception as e:
            logger.error(f"[SQLiteEventStreamRepository] _update_subscriber_activity 失败 - subscriber_id: {subscriber_id}, 错误: {str(e)}", exc_info=True)

    async def get_buffered_events(self, agent_id: str, from_sequence: int = 1) -> List[AgentEvent]:
        """获取缓冲区中的事件"""
        broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
        if not broadcaster:
            return []
        
        return await broadcaster.event_buffer.get_events_from_sequence_async(from_sequence)

    async def notify_new_event(self, agent_id: str, event: AgentEvent) -> None:
        """通知数据库中的活跃订阅者新事件（基于轮询的实现）"""
        async with get_session(self.engine) as session:
            try:
                # 清理过期的订阅者
                current_time = datetime.now()
                
                # 获取该agent的所有活跃订阅者
                stmt = select(EventSubscriberORM).where(
                    EventSubscriberORM.agent_id == agent_id,
                    EventSubscriberORM.is_active == "true"
                )
                result = await session.execute(stmt)
                active_subscribers = result.scalars().all()
                
                # 检查并清理过期的订阅者
                inactive_subscriber_ids = []
                
                for subscriber_orm in active_subscribers:
                    # 检查是否超时（默认5分钟）
                    timeout_delta = timedelta(seconds=subscriber_orm.heartbeat_timeout_seconds)
                    if current_time - subscriber_orm.last_activity > timeout_delta:
                        inactive_subscriber_ids.append(subscriber_orm.subscriber_id)
                        subscriber_orm.is_active = "false"
                        logger.debug(f"Marking subscriber {subscriber_orm.subscriber_id} as inactive due to timeout")
                
                # 提交不活跃状态更新
                if inactive_subscriber_ids:
                    await session.commit()
                
                # 记录活跃订阅者数量（在轮询模式下，订阅者会自己获取新事件）
                active_count = len([s for s in active_subscribers if s.subscriber_id not in inactive_subscriber_ids])
                logger.debug(f"Event {event.type} available for {active_count} active subscribers of agent {agent_id}")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to process event notification for agent {agent_id}: {str(e)}")
                raise

    async def cleanup_agent_stream(self, agent_id: str) -> None:
        """清理agent的事件流"""
        async with get_session(self.engine) as session:
            try:
                # 删除该agent的所有订阅者
                stmt = delete(EventSubscriberORM).where(EventSubscriberORM.agent_id == agent_id)
                result = await session.execute(stmt)
                await session.commit()
                
                deleted_count = result.rowcount
                logger.debug(f"Cleaned up {deleted_count} subscribers for agent {agent_id}")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to cleanup agent stream for {agent_id}: {str(e)}")
                raise

    async def get_active_subscribers(self, agent_id: str) -> List[EventSubscriber]:
        """获取指定agent的活跃订阅者"""
        async with get_readonly_session(self.engine) as session:
            stmt = select(EventSubscriberORM).where(
                EventSubscriberORM.agent_id == agent_id,
                EventSubscriberORM.is_active == "true"
            )
            result = await session.execute(stmt)
            subscriber_orms = result.scalars().all()
            
            # 转换为领域模型
            subscribers = []
            for subscriber_orm in subscriber_orms:
                # 注意：这里创建的EventSubscriber没有event_queue，因为队列不能持久化
                # 实际使用时需要重新创建队列或使用其他机制
                subscriber = EventSubscriber(
                    subscriber_id=subscriber_orm.subscriber_id,
                    agent_id=subscriber_orm.agent_id,
                    event_queue=asyncio.Queue(maxsize=100),  # 重新创建队列
                    created_at=subscriber_orm.created_at,
                    last_activity=subscriber_orm.last_activity,
                    is_active=subscriber_orm.is_active == "true"
                )
                subscribers.append(subscriber)
            
            return subscribers

    async def cleanup_expired_subscribers(self) -> None:
        """清理过期的订阅者"""
        async with get_session(self.engine) as session:
            try:
                current_time = datetime.now()
                
                # 查找所有活跃但可能过期的订阅者
                stmt = select(EventSubscriberORM).where(EventSubscriberORM.is_active == "true")
                result = await session.execute(stmt)
                active_subscribers = result.scalars().all()
                
                expired_count = 0
                for subscriber_orm in active_subscribers:
                    timeout_delta = timedelta(seconds=subscriber_orm.heartbeat_timeout_seconds)
                    if current_time - subscriber_orm.last_activity > timeout_delta:
                        subscriber_orm.is_active = "false"
                        expired_count += 1
                
                if expired_count > 0:
                    await session.commit()
                    logger.debug(f"Marked {expired_count} subscribers as expired")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to cleanup expired subscribers: {str(e)}")
                raise


class SQLiteEventSubscriptionManager:
    """SQLite版本的事件订阅管理器 - 数据库持久化订阅者"""

    def __init__(self, engine: AsyncEngine):
        """初始化事件订阅管理器
        
        Args:
            engine: 数据库引擎
        """
        self.broadcast_repository = SQLiteEventBroadcastRepository(engine)
        self.stream_repository = SQLiteEventStreamRepository(self.broadcast_repository)
        self._agent_locks = collections.defaultdict(asyncio.Lock) # 恢复锁
        self.engine = engine
        logger.debug("SQLiteEventSubscriptionManager initialized with database-persisted subscribers")

    async def notify_event(self, agent_id: str, event: AgentEvent) -> None:
        """通知新事件 - 通过流仓储的数据库机制分发，并确保操作的原子性。"""
        logger.debug(f"[SQLiteEventSubscriptionManager] notify_event 开始 - agent_id: {agent_id}, event_type: {event.type}")
        
        try:
            logger.debug(f"[SQLiteEventSubscriptionManager] 尝试获取agent锁 - agent_id: {agent_id}")
            async with self._agent_locks[agent_id]:
                logger.debug(f"[SQLiteEventSubscriptionManager] 成功获得agent锁 - agent_id: {agent_id}")
                
                # 1. 获取或创建广播器 (在锁的保护下)
                #    这一步会确保 broadcaster 对象是最新的，并且数据库条目存在。
                logger.debug(f"[SQLiteEventSubscriptionManager] 步骤1：开始获取或创建广播器 - agent_id: {agent_id}")
                try:
                    broadcaster = await self.get_or_create_broadcaster_nolock_internal(agent_id)
                    logger.debug(f"[SQLiteEventSubscriptionManager] 步骤1成功：广播器已获取 - agent_id: {agent_id}, current_sequence: {broadcaster.event_buffer.current_sequence}")
                except Exception as e:
                    logger.error(f"[SQLiteEventSubscriptionManager] 步骤1失败：获取或创建广播器异常 - agent_id: {agent_id}, 错误: {str(e)}", exc_info=True)
                    raise
                
                # 2. 添加事件到缓冲区（序号由缓冲区内部管理，使用异步版本进行数据库持久化）
                logger.debug(f"[SQLiteEventSubscriptionManager] 步骤2：开始添加事件到缓冲区 - agent_id: {agent_id}, event_type: {event.type}")
                try:
                    sequence = await broadcaster.event_buffer.add_event_async(event)
                    logger.debug(f"[SQLiteEventSubscriptionManager] 步骤2成功：事件已添加到缓冲区 - agent_id: {agent_id}, sequence: {sequence}")
                except Exception as e:
                    logger.error(f"[SQLiteEventSubscriptionManager] 步骤2失败：添加事件到缓冲区异常 - agent_id: {agent_id}, 错误: {str(e)}", exc_info=True)
                    raise
                
                # 3. 更新广播器到数据库
                logger.debug(f"[SQLiteEventSubscriptionManager] 步骤3：开始更新广播器到数据库 - agent_id: {agent_id}")
                try:
                    await self.broadcast_repository.update_broadcaster(broadcaster)
                    logger.debug(f"[SQLiteEventSubscriptionManager] 步骤3成功：广播器已更新到数据库 - agent_id: {agent_id}")
                except Exception as e:
                    logger.error(f"[SQLiteEventSubscriptionManager] 步骤3失败：更新广播器到数据库异常 - agent_id: {agent_id}, 错误: {str(e)}", exc_info=True)
                    raise
                
                # 4. 通知数据库中的订阅者 (由 stream_repository 处理)
                logger.debug(f"[SQLiteEventSubscriptionManager] 步骤4：开始通知订阅者 - agent_id: {agent_id}")
                try:
                    await self.stream_repository.notify_new_event(agent_id, event)
                    logger.debug(f"[SQLiteEventSubscriptionManager] 步骤4成功：订阅者已通知 - agent_id: {agent_id}")
                except Exception as e:
                    logger.error(f"[SQLiteEventSubscriptionManager] 步骤4失败：通知订阅者异常 - agent_id: {agent_id}, 错误: {str(e)}", exc_info=True)
                    raise
                
                logger.debug(f"[SQLiteEventSubscriptionManager] notify_event 成功完成 - agent_id: {agent_id}, sequence: {sequence}")
                
        except Exception as e:
            logger.error(f"[SQLiteEventSubscriptionManager] notify_event 失败 - agent_id: {agent_id}, event_type: {event.type}, 错误: {str(e)}", exc_info=True)
            raise

    async def cleanup_agent(self, agent_id: str) -> None:
        """清理agent相关的所有订阅资源"""
        # 清理流（包括所有订阅者）
        await self.stream_repository.cleanup_agent_stream(agent_id)
        
        # 清理广播器（包括数据库中的历史数据）
        await self.broadcast_repository.delete_broadcaster(agent_id)
    
    # 以下方法用于测试和调试
    async def get_or_create_broadcaster(self, agent_id: str) -> AgentEventBroadcaster:
        """获取或创建广播器 - 使用原子化的数据库操作和应用层锁。"""
        async with self._agent_locks[agent_id]: # 恢复锁的使用
            return await self.get_or_create_broadcaster_nolock_internal(agent_id)

    async def get_or_create_broadcaster_nolock_internal(self, agent_id: str) -> AgentEventBroadcaster:
        """获取或创建广播器的内部无锁版本，假定调用者已获取锁。"""
        logger.debug(f"[SQLiteEventSubscriptionManager] get_or_create_broadcaster_nolock_internal 开始 - agent_id: {agent_id}")
        
        # 1. 首先尝试获取，这通常会成功，除非是首次为 agent_id 创建
        logger.debug(f"[SQLiteEventSubscriptionManager] 步骤1：尝试获取现有广播器 - agent_id: {agent_id}")
        try:
            broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
            if broadcaster:
                logger.debug(f"[SQLiteEventSubscriptionManager] 步骤1成功：找到现有广播器 - agent_id: {agent_id}, current_sequence: {broadcaster.event_buffer.current_sequence}")
                return broadcaster
            else:
                logger.debug(f"[SQLiteEventSubscriptionManager] 步骤1结果：未找到现有广播器 - agent_id: {agent_id}")
        except Exception as e:
            logger.error(f"[SQLiteEventSubscriptionManager] 步骤1异常：获取现有广播器失败 - agent_id: {agent_id}, 错误: {str(e)}", exc_info=True)
            # 继续执行创建流程
        
        logger.debug(f"[SQLiteEventSubscriptionManager] 步骤2：需要创建新广播器 - agent_id: {agent_id}")
        
        # 2. 如果获取不到，调用原子化的创建方法来确保数据库记录存在
        logger.debug(f"[SQLiteEventSubscriptionManager] 步骤2.1：调用create_broadcaster_if_not_exists - agent_id: {agent_id}")
        try:
            await self.broadcast_repository.create_broadcaster_if_not_exists(agent_id)
            logger.debug(f"[SQLiteEventSubscriptionManager] 步骤2.1成功：create_broadcaster_if_not_exists 完成 - agent_id: {agent_id}")
        except Exception as e:
            logger.error(f"[SQLiteEventSubscriptionManager] 步骤2.1异常：create_broadcaster_if_not_exists 失败 - agent_id: {agent_id}, 错误: {str(e)}", exc_info=True)
            raise
        
        # 3. 再次获取广播器
        logger.debug(f"[SQLiteEventSubscriptionManager] 步骤3：再次尝试获取广播器 - agent_id: {agent_id}")
        try:
            broadcaster = await self.broadcast_repository.get_broadcaster(agent_id)
            if not broadcaster:
                logger.error(f"[SQLiteEventSubscriptionManager] 步骤3失败：创建并尝试获取广播器后仍然失败 - agent_id: {agent_id}")
                
                # 额外的调试信息：检查数据库状态
                logger.debug(f"[SQLiteEventSubscriptionManager] 调试：检查数据库中的广播器记录 - agent_id: {agent_id}")
                try:
                    async with get_readonly_session(self.engine) as session:
                        debug_stmt = select(EventBroadcasterORM).where(EventBroadcasterORM.agent_id == agent_id)
                        debug_result = await session.execute(debug_stmt)
                        debug_broadcaster = debug_result.scalar_one_or_none()
                        
                        if debug_broadcaster:
                            logger.debug(f"[SQLiteEventSubscriptionManager] 调试：数据库中存在广播器记录 - agent_id: {agent_id}, current_sequence: {debug_broadcaster.current_sequence}")
                        else:
                            logger.error(f"[SQLiteEventSubscriptionManager] 调试：数据库中不存在广播器记录 - agent_id: {agent_id}")
                except Exception as debug_e:
                    logger.error(f"[SQLiteEventSubscriptionManager] 调试查询失败 - agent_id: {agent_id}, 错误: {str(debug_e)}", exc_info=True)
                
                raise RuntimeError(f"Failed to get broadcaster for {agent_id} after ensuring it exists in DB.")
            else:
                logger.debug(f"[SQLiteEventSubscriptionManager] 步骤3成功：获取到广播器 - agent_id: {agent_id}, current_sequence: {broadcaster.event_buffer.current_sequence}")
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"[SQLiteEventSubscriptionManager] 步骤3异常：再次获取广播器失败 - agent_id: {agent_id}, 错误: {str(e)}", exc_info=True)
            raise
        
        logger.debug(f"[SQLiteEventSubscriptionManager] get_or_create_broadcaster_nolock_internal 成功完成 - agent_id: {agent_id}, current_sequence: {broadcaster.event_buffer.current_sequence}")
        return broadcaster
    
    async def broadcast_event(self, agent_id: str, event: AgentEvent) -> None:
        """广播事件"""
        await self.notify_event(agent_id, event)
    
    async def get_buffered_events(self, agent_id: str, from_sequence: int = 1) -> List[AgentEvent]:
        """获取缓冲事件"""
        return await self.stream_repository.get_buffered_events(agent_id, from_sequence)
    
    async def create_subscription(self, subscription: EventSubscriber) -> None:
        """创建订阅"""
        async with get_session(self.engine) as session:
            try:
                subscriber_orm = EventSubscriberORM(
                    subscriber_id=subscription.subscriber_id,
                    agent_id=subscription.agent_id,
                    created_at=subscription.created_at,
                    last_activity=subscription.last_activity,
                    is_active="true" if subscription.is_active else "false",
                    heartbeat_timeout_seconds=300
                )
                session.add(subscriber_orm)
                await session.commit()
                logger.debug(f"Created subscription {subscription.subscriber_id} for agent {subscription.agent_id}")
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to create subscription {subscription.subscriber_id}: {str(e)}")
                raise
    
    async def get_subscription(self, subscription_id: str) -> Optional[EventSubscriber]:
        """获取订阅"""
        async with get_readonly_session(self.engine) as session:
            stmt = select(EventSubscriberORM).where(EventSubscriberORM.subscriber_id == subscription_id)
            result = await session.execute(stmt)
            subscriber_orm = result.scalar_one_or_none()
            
            if subscriber_orm:
                return EventSubscriber(
                    subscriber_id=subscriber_orm.subscriber_id,
                    agent_id=subscriber_orm.agent_id,
                    event_queue=asyncio.Queue(maxsize=100),  # 重新创建队列
                    created_at=subscriber_orm.created_at,
                    last_activity=subscriber_orm.last_activity,
                    is_active=subscriber_orm.is_active == "true"
                )
            return None
    
    async def update_subscription_heartbeat(self, subscription_id: str, heartbeat: datetime) -> None:
        """更新订阅心跳"""
        async with get_session(self.engine) as session:
            try:
                stmt = select(EventSubscriberORM).where(EventSubscriberORM.subscriber_id == subscription_id)
                result = await session.execute(stmt)
                subscriber_orm = result.scalar_one_or_none()
                
                if subscriber_orm:
                    subscriber_orm.last_activity = heartbeat
                    await session.commit()
                    logger.debug(f"Updated heartbeat for subscription {subscription_id}")
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update heartbeat for subscription {subscription_id}: {str(e)}")
                raise
    
    async def delete_subscription(self, subscription_id: str) -> None:
        """删除订阅"""
        async with get_session(self.engine) as session:
            try:
                stmt = delete(EventSubscriberORM).where(EventSubscriberORM.subscriber_id == subscription_id)
                result = await session.execute(stmt)
                await session.commit()
                
                if result.rowcount > 0:
                    logger.debug(f"Deleted subscription {subscription_id}")
                else:
                    logger.warning(f"Subscription {subscription_id} not found for deletion")
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to delete subscription {subscription_id}: {str(e)}")
                raise
    
    async def get_active_subscriptions(self, agent_id: str) -> List[EventSubscriber]:
        """获取活跃订阅"""
        return await self.stream_repository.get_active_subscribers(agent_id)
    
    async def cleanup_expired_subscriptions(self) -> None:
        """清理过期订阅"""
        await self.stream_repository.cleanup_expired_subscribers()
    
    async def get_subscription_count(self, agent_id: str) -> int:
        """获取订阅数量"""
        async with get_readonly_session(self.engine) as session:
            stmt = select(func.count(EventSubscriberORM.subscriber_id)).where(
                EventSubscriberORM.agent_id == agent_id,
                EventSubscriberORM.is_active == "true"
            )
            result = await session.execute(stmt)
            return result.scalar() or 0
    
    async def _update_broadcaster_buffer_size(self, agent_id: str, buffer_size: int) -> None:
        """更新广播器缓冲区大小（测试辅助方法）"""
        broadcaster = await self.get_or_create_broadcaster(agent_id)
        broadcaster.event_buffer.max_size = buffer_size
        await self.broadcast_repository.update_broadcaster(broadcaster) 