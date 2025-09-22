"""会话仓储SQLite实现"""

import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
import uuid
import asyncio
import collections
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.exc import IntegrityError

from app.domain.models.conversation import ConversationHistory, ConversationEvent
from app.infrastructure.database.connection import get_session, get_readonly_session
from app.infrastructure.database.models import ConversationHistoryORM, ConversationEventORM

logger = logging.getLogger(__name__)

class SQLiteConversationRepository:
    """会话仓储SQLite实现 - 使用全局DatabaseManager"""

    def __init__(self, engine: AsyncEngine):
        """初始化会话仓储
        
        Args:
            engine: 可选的数据库引擎，如果不提供则使用默认引擎
        """
        self.engine = engine
        self._agent_locks = collections.defaultdict(asyncio.Lock)
    
    def _orm_to_domain_event(self, event_orm: ConversationEventORM) -> ConversationEvent:
        """将事件ORM模型转换为领域模型"""
        return ConversationEvent(
            id=event_orm.id,
            agent_id=event_orm.agent_id,
            event_type=event_orm.event_type,
            event_data=event_orm.event_data,
            timestamp=event_orm.timestamp,
            sequence=event_orm.sequence
        )
    
    def _domain_to_orm_event(self, event: ConversationEvent) -> ConversationEventORM:
        """将事件领域模型转换为ORM模型"""
        return ConversationEventORM(
            id=event.id,
            agent_id=event.agent_id,
            sequence=event.sequence,
            event_type=event.event_type,
            event_data=event.event_data,
            timestamp=event.timestamp
        )
    
    def _orm_to_domain_history(self, history_orm: ConversationHistoryORM) -> ConversationHistory:
        """将历史ORM模型转换为领域模型"""
        events = []
        if history_orm.events:
            events = [self._orm_to_domain_event(event_orm) for event_orm in history_orm.events]
            # 按序号排序
            events.sort(key=lambda e: e.sequence)
        
        return ConversationHistory(
            agent_id=history_orm.agent_id,
            user_id=history_orm.user_id,
            flow_id=history_orm.flow_id,
            title=history_orm.title,
            created_at=history_orm.created_at,
            updated_at=history_orm.updated_at,
            events=events
        )
    
    def _domain_to_orm_history(self, history: ConversationHistory) -> ConversationHistoryORM:
        """将历史领域模型转换为ORM模型"""
        return ConversationHistoryORM(
            agent_id=history.agent_id,
            user_id=history.user_id,
            flow_id=history.flow_id,
            title=history.title,
            created_at=history.created_at,
            updated_at=history.updated_at
        )
    
    async def save_history(self, history: ConversationHistory) -> None:
        """保存会话历史"""
        async with get_session(self.engine) as session:
            try:
                # 检查会话历史是否已存在
                stmt = select(ConversationHistoryORM).where(ConversationHistoryORM.agent_id == history.agent_id)
                result = await session.execute(stmt)
                existing_history = result.scalar_one_or_none()
                
                if existing_history:
                    # 更新现有会话历史
                    existing_history.user_id = history.user_id
                    existing_history.flow_id = history.flow_id
                    existing_history.title = history.title
                    existing_history.updated_at = history.updated_at
                else:
                    # 创建新会话历史
                    history_orm = self._domain_to_orm_history(history)
                    session.add(history_orm)
                
                await session.commit()
                logger.debug(f"保存会话历史: {history.agent_id}, 用户: {history.user_id}")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"保存会话历史失败: {history.agent_id}, 错误: {str(e)}")
                raise
    
    async def get_history(self, agent_id: str) -> Optional[ConversationHistory]:
        """获取会话历史"""
        async with get_readonly_session(self.engine) as session:
            stmt = select(ConversationHistoryORM).options(
                selectinload(ConversationHistoryORM.events)
            ).where(ConversationHistoryORM.agent_id == agent_id)
            result = await session.execute(stmt)
            history_orm = result.scalar_one_or_none()
            
            if history_orm:
                return self._orm_to_domain_history(history_orm)
            return None
    
    async def add_event(self, agent_id: str, event_type: str, event_data: dict) -> ConversationEvent:
        """添加事件到会话历史 - 使用重试机制处理并发"""
        max_retries = 10
        for attempt in range(max_retries):
            async with get_session(self.engine) as session:
                try:
                    async with self._agent_locks[agent_id]:
                        # 在事务中获取序号并插入
                        max_sequence_stmt = select(func.max(ConversationEventORM.sequence)).where(
                            ConversationEventORM.agent_id == agent_id
                        )
                        max_sequence_result = await session.execute(max_sequence_stmt)
                        current_max_sequence = max_sequence_result.scalar_one_or_none()
                        
                        next_sequence = (current_max_sequence or 0) + 1
                        
                        event = ConversationEvent(
                            id=str(uuid.uuid4()),
                            agent_id=agent_id,
                            event_type=event_type,
                            event_data=event_data,
                            timestamp=datetime.now(),
                            sequence=next_sequence
                        )
                        
                        event_orm = self._domain_to_orm_event(event)
                        session.add(event_orm)
                        
                        await session.commit()
                        return event
                    
                except IntegrityError as e:
                    await session.rollback()
                    logger.exception(f"添加事件失败: {agent_id}, 错误: {str(e)}")
                    if attempt < max_retries - 1:
                        # 短暂等待后重试
                        await asyncio.sleep(0.01 * (2 ** attempt))  # 指数退避
                        continue
                    else:
                        logger.error(f"添加事件失败，已达最大重试次数: {agent_id}")
                        raise
                except Exception as e:
                    await session.rollback()
                    logger.error(f"添加事件失败: {agent_id}, 错误: {str(e)}")
                    raise
    
    async def get_events_from_sequence(self, agent_id: str, from_sequence: int = 1) -> List[ConversationEvent]:
        """获取从指定序号开始的事件"""
        async with get_readonly_session(self.engine) as session:
            stmt = select(ConversationEventORM).where(
                ConversationEventORM.agent_id == agent_id,
                ConversationEventORM.sequence >= from_sequence
            ).order_by(ConversationEventORM.sequence)

            result = await session.execute(stmt)
            event_orms = result.scalars().all()
            
            return [self._orm_to_domain_event(event_orm) for event_orm in event_orms]
    
    async def delete_history(self, agent_id: str) -> bool:
        """删除会话历史"""
        async with get_session(self.engine) as session:
            try:
                # 先删除相关事件
                stmt_delete_events = delete(ConversationEventORM).where(ConversationEventORM.agent_id == agent_id)
                await session.execute(stmt_delete_events)
                
                # 再删除会话历史
                stmt_delete_history = delete(ConversationHistoryORM).where(ConversationHistoryORM.agent_id == agent_id)
                result = await session.execute(stmt_delete_history)
                
                await session.commit()
                
                deleted_count = result.rowcount
                if deleted_count > 0:
                    logger.debug(f"删除会话历史: {agent_id}")
                    return True
                else:
                    logger.warning(f"未找到要删除的会话历史: {agent_id}")
                    return False
                    
            except Exception as e:
                await session.rollback()
                logger.error(f"删除会话历史失败: {agent_id}, 错误: {str(e)}")
                raise
    
    async def list_histories(self, user_id: str, limit: int = 50, offset: int = 0) -> List[ConversationHistory]:
        """列出会话历史（支持按用户过滤）"""
        async with get_readonly_session(self.engine) as session:
            stmt = select(ConversationHistoryORM).where(ConversationHistoryORM.user_id == user_id)
            
            stmt = stmt.order_by(
                ConversationHistoryORM.updated_at.desc()
            ).limit(limit).offset(offset)
            
            result = await session.execute(stmt)
            history_orms = result.scalars().all()
            
            # 注意：这里不加载事件，只返回会话历史基本信息
            histories = []
            for history_orm in history_orms:
                history = ConversationHistory(
                    agent_id=history_orm.agent_id,
                    user_id=history_orm.user_id,
                    flow_id=history_orm.flow_id,
                    title=history_orm.title,
                    created_at=history_orm.created_at,
                    updated_at=history_orm.updated_at,
                    events=[]  # 不加载事件，提升性能
                )
                histories.append(history)
            
            return histories 