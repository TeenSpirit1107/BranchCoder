"""Agent上下文仓储SQLite实现"""

import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, delete, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.models.agent import Agent
from app.domain.models.agent_context import AgentContext
from app.domain.models.memory import Memory
from app.infrastructure.database.connection import get_session, get_readonly_session
from app.infrastructure.database.models import AgentContextORM

logger = logging.getLogger(__name__)

class SQLiteAgentContextRepository:
    """Agent上下文仓储SQLite实现"""

    def __init__(self, engine: AsyncEngine):
        """初始化Agent上下文仓储
        
        Args:
            engine: 数据库引擎
        """
        self.engine = engine
    
    def _orm_to_domain(self, context_orm: AgentContextORM) -> AgentContext:
        """将ORM模型转换为领域模型"""
        # 反序列化Agent数据
        agent_data = context_orm.agent_data
        agent = Agent(
            id=agent_data.get("id"),
            planner_memory=Memory.from_dict(agent_data.get("planner_memory", {})),
            execution_memory=Memory.from_dict(agent_data.get("execution_memory", {})),
            model_name=agent_data.get("model_name"),
            temperature=agent_data.get("temperature", 0.7),
            max_tokens=agent_data.get("max_tokens"),
            user_id=agent_data.get("user_id"),
            environment=agent_data.get("environment")
        )
        
        return AgentContext(
            agent_id=context_orm.agent_id,
            agent=agent,
            flow_id=context_orm.flow_id,
            sandbox_id=context_orm.sandbox_id,
            status=context_orm.status,
            last_message=context_orm.last_message,
            last_message_time=context_orm.last_message_time,
            created_at=context_orm.created_at,
            updated_at=context_orm.updated_at,
            meta_data=context_orm.meta_data or {}
        )
    
    def _domain_to_orm(self, context: AgentContext) -> AgentContextORM:
        """将领域模型转换为ORM模型"""
        # 序列化Agent数据
        agent_data = {
            "id": context.agent.id,
            "planner_memory": context.agent.planner_memory.to_dict(),
            "execution_memory": context.agent.execution_memory.to_dict(),
            "model_name": context.agent.model_name,
            "temperature": context.agent.temperature,
            "max_tokens": context.agent.max_tokens,
            "user_id": context.agent.user_id,
            "environment": context.agent.environment.to_dict() if context.agent.environment else None
        }
        
        return AgentContextORM(
            agent_id=context.agent_id,
            user_id=context.agent.user_id,
            flow_id=context.flow_id,
            sandbox_id=context.sandbox_id,
            status=context.status,
            last_message=context.last_message,
            last_message_time=context.last_message_time,
            created_at=context.created_at,
            updated_at=context.updated_at,
            meta_data=context.meta_data,
            agent_data=agent_data
        )
    
    async def save_context(self, context: AgentContext) -> None:
        """保存Agent上下文"""
        async with get_session(self.engine) as session:
            try:
                context_orm = self._domain_to_orm(context)
                session.add(context_orm)
                await session.commit()
                logger.debug(f"保存Agent上下文: {context.agent_id}, 用户: {context.agent.user_id}")
            except IntegrityError as e:
                await session.rollback()
                logger.error(f"保存Agent上下文失败，可能已存在: {context.agent_id}, 错误: {str(e)}")
                raise ValueError(f"Agent上下文已存在: {context.agent_id}")
            except Exception as e:
                await session.rollback()
                logger.error(f"保存Agent上下文时发生错误: {str(e)}")
                raise
    
    async def get_context(self, agent_id: str) -> Optional[AgentContext]:
        """通过agent_id获取Agent上下文"""
        async with get_readonly_session(self.engine) as session:
            try:
                stmt = select(AgentContextORM).where(AgentContextORM.agent_id == agent_id)
                result = await session.execute(stmt)
                context_orm = result.scalar_one_or_none()
                
                if context_orm:
                    return self._orm_to_domain(context_orm)
                return None
            except Exception as e:
                logger.error(f"获取Agent上下文时发生错误: {str(e)}")
                raise
    
    async def update_context(self, context: AgentContext) -> None:
        """更新Agent上下文"""
        async with get_session(self.engine) as session:
            try:
                # 查找现有记录
                stmt = select(AgentContextORM).where(AgentContextORM.agent_id == context.agent_id)
                result = await session.execute(stmt)
                existing_orm = result.scalar_one_or_none()
                
                if not existing_orm:
                    logger.warning(f"尝试更新不存在的Agent上下文: {context.agent_id}")
                    return
                
                # 更新字段
                context.updated_at = datetime.now()
                updated_orm = self._domain_to_orm(context)
                
                existing_orm.user_id = updated_orm.user_id
                existing_orm.flow_id = updated_orm.flow_id
                existing_orm.sandbox_id = updated_orm.sandbox_id
                existing_orm.status = updated_orm.status
                existing_orm.last_message = updated_orm.last_message
                existing_orm.last_message_time = updated_orm.last_message_time
                existing_orm.updated_at = updated_orm.updated_at
                existing_orm.meta_data = updated_orm.meta_data
                existing_orm.agent_data = updated_orm.agent_data
                
                await session.commit()
                logger.debug(f"更新Agent上下文: {context.agent_id}")
            except Exception as e:
                await session.rollback()
                logger.error(f"更新Agent上下文时发生错误: {str(e)}")
                raise
    
    async def delete_context(self, agent_id: str) -> bool:
        """删除Agent上下文"""
        async with get_session(self.engine) as session:
            try:
                stmt = delete(AgentContextORM).where(AgentContextORM.agent_id == agent_id)
                result = await session.execute(stmt)
                await session.commit()
                
                deleted_count = result.rowcount
                if deleted_count > 0:
                    logger.debug(f"删除Agent上下文: {agent_id}")
                    return True
                else:
                    logger.warning(f"未找到要删除的Agent上下文: {agent_id}")
                    return False
            except Exception as e:
                await session.rollback()
                logger.error(f"删除Agent上下文时发生错误: {str(e)}")
                raise
    
    async def list_contexts(self, user_id: Optional[str] = None, status: Optional[str] = None, 
                           limit: int = 50, offset: int = 0) -> List[AgentContext]:
        """列出Agent上下文（支持按用户和状态过滤）"""
        async with get_readonly_session(self.engine) as session:
            try:
                stmt = select(AgentContextORM)
                
                # 添加过滤条件
                conditions = []
                if user_id:
                    conditions.append(AgentContextORM.user_id == user_id)
                if status:
                    conditions.append(AgentContextORM.status == status)
                
                if conditions:
                    stmt = stmt.where(and_(*conditions))
                
                # 添加排序和分页
                stmt = stmt.order_by(AgentContextORM.updated_at.desc()).offset(offset).limit(limit)
                
                result = await session.execute(stmt)
                context_orms = result.scalars().all()
                
                return [self._orm_to_domain(orm) for orm in context_orms]
            except Exception as e:
                logger.error(f"列出Agent上下文时发生错误: {str(e)}")
                raise
    
    async def get_contexts_by_user(self, user_id: str) -> List[AgentContext]:
        """获取指定用户的所有Agent上下文"""
        async with get_readonly_session(self.engine) as session:
            try:
                stmt = select(AgentContextORM).where(
                    AgentContextORM.user_id == user_id
                ).order_by(AgentContextORM.updated_at.desc())
                
                result = await session.execute(stmt)
                context_orms = result.scalars().all()
                
                return [self._orm_to_domain(orm) for orm in context_orms]
            except Exception as e:
                logger.error(f"获取用户Agent上下文时发生错误: {str(e)}")
                raise
    
    async def get_contexts_by_status(self, status: str) -> List[AgentContext]:
        """获取指定状态的所有Agent上下文"""
        async with get_readonly_session(self.engine) as session:
            try:
                stmt = select(AgentContextORM).where(
                    AgentContextORM.status == status
                ).order_by(AgentContextORM.updated_at.desc())
                
                result = await session.execute(stmt)
                context_orms = result.scalars().all()
                
                return [self._orm_to_domain(orm) for orm in context_orms]
            except Exception as e:
                logger.error(f"获取状态Agent上下文时发生错误: {str(e)}")
                raise
    
    async def update_status(self, agent_id: str, status: str) -> bool:
        """更新Agent状态"""
        async with get_session(self.engine) as session:
            try:
                stmt = select(AgentContextORM).where(AgentContextORM.agent_id == agent_id)
                result = await session.execute(stmt)
                context_orm = result.scalar_one_or_none()
                
                if not context_orm:
                    logger.warning(f"未找到Agent上下文: {agent_id}")
                    return False
                
                context_orm.status = status
                context_orm.updated_at = datetime.now()
                
                await session.commit()
                logger.debug(f"更新Agent状态: {agent_id}, {status}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"更新Agent状态时发生错误: {str(e)}")
                raise
    
    async def update_last_message(self, agent_id: str, message: str, timestamp: Optional[int] = None) -> bool:
        """更新最后消息"""
        async with get_session(self.engine) as session:
            try:
                stmt = select(AgentContextORM).where(AgentContextORM.agent_id == agent_id)
                result = await session.execute(stmt)
                context_orm = result.scalar_one_or_none()
                
                if not context_orm:
                    logger.warning(f"未找到Agent上下文: {agent_id}")
                    return False
                
                context_orm.last_message = message
                context_orm.last_message_time = timestamp
                context_orm.updated_at = datetime.now()
                
                await session.commit()
                logger.debug(f"更新Agent最后消息: {agent_id}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"更新Agent最后消息时发生错误: {str(e)}")
                raise
    
    async def set_sandbox_id(self, agent_id: str, sandbox_id: str) -> bool:
        """设置沙盒ID"""
        async with get_session(self.engine) as session:
            try:
                stmt = select(AgentContextORM).where(AgentContextORM.agent_id == agent_id)
                result = await session.execute(stmt)
                context_orm = result.scalar_one_or_none()
                
                if not context_orm:
                    logger.warning(f"未找到Agent上下文: {agent_id}")
                    return False
                
                context_orm.sandbox_id = sandbox_id
                context_orm.updated_at = datetime.now()
                
                await session.commit()
                logger.debug(f"设置Agent沙盒ID: {agent_id}, {sandbox_id}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"设置Agent沙盒ID时发生错误: {str(e)}")
                raise 
    
    async def context_exists(self, agent_id: str) -> bool:
        """检查Agent上下文是否存在"""
        async with get_readonly_session(self.engine) as session:
            try:
                stmt = select(AgentContextORM.agent_id).where(AgentContextORM.agent_id == agent_id)
                result = await session.execute(stmt)
                return result.scalar_one_or_none() is not None
            except Exception as e:
                logger.error(f"检查Agent上下文存在性时发生错误: {str(e)}")
                raise 