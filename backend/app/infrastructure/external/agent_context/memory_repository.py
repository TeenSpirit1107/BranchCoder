"""Agent上下文仓储内存实现"""

import logging
from datetime import datetime
from typing import Optional, List

from app.domain.models.agent_context import AgentContext
from app.infrastructure.external.user.memory_repository import agent_context_data_store

logger = logging.getLogger(__name__)

class MemoryAgentContextRepository:
    """Agent上下文仓储内存实现"""
    
    async def save_context(self, context: AgentContext) -> None:
        """保存Agent上下文"""
        agent_id = context.agent_id
        user_id = context.agent.user_id
        status = context.status
        sandbox_id = context.sandbox_id
        
        # 保存上下文
        agent_context_data_store.contexts[agent_id] = context
        
        # 更新用户Agent索引
        if user_id:
            if user_id not in agent_context_data_store.user_agents_index:
                agent_context_data_store.user_agents_index[user_id] = []
            if agent_id not in agent_context_data_store.user_agents_index[user_id]:
                agent_context_data_store.user_agents_index[user_id].append(agent_id)
        
        # 更新状态索引
        if status not in agent_context_data_store.status_index:
            agent_context_data_store.status_index[status] = []
        if agent_id not in agent_context_data_store.status_index[status]:
            agent_context_data_store.status_index[status].append(agent_id)
        
        # 更新沙盒索引
        if sandbox_id:
            agent_context_data_store.sandbox_index[sandbox_id] = agent_id
        
        logger.debug(f"保存Agent上下文: {agent_id}, 用户: {user_id}, 状态: {status}")
    
    async def get_context(self, agent_id: str) -> Optional[AgentContext]:
        """通过agent_id获取Agent上下文"""
        return agent_context_data_store.contexts.get(agent_id)
    
    async def update_context(self, context: AgentContext) -> None:
        """更新Agent上下文"""
        agent_id = context.agent_id
        old_context = agent_context_data_store.contexts.get(agent_id)
        
        if not old_context:
            logger.warning(f"尝试更新不存在的Agent上下文: {agent_id}")
            return
        
        # 如果状态发生变化，需要更新状态索引
        if old_context.status != context.status:
            # 从旧状态索引中移除
            if old_context.status in agent_context_data_store.status_index:
                if agent_id in agent_context_data_store.status_index[old_context.status]:
                    agent_context_data_store.status_index[old_context.status].remove(agent_id)
            
            # 添加到新状态索引
            if context.status not in agent_context_data_store.status_index:
                agent_context_data_store.status_index[context.status] = []
            if agent_id not in agent_context_data_store.status_index[context.status]:
                agent_context_data_store.status_index[context.status].append(agent_id)
        
        # 如果沙盒ID发生变化，需要更新沙盒索引
        if old_context.sandbox_id != context.sandbox_id:
            # 移除旧的沙盒索引
            if old_context.sandbox_id and old_context.sandbox_id in agent_context_data_store.sandbox_index:
                del agent_context_data_store.sandbox_index[old_context.sandbox_id]
            
            # 添加新的沙盒索引
            if context.sandbox_id:
                agent_context_data_store.sandbox_index[context.sandbox_id] = agent_id
        
        # 更新上下文
        context.updated_at = datetime.now()
        agent_context_data_store.contexts[agent_id] = context
        
        logger.debug(f"更新Agent上下文: {agent_id}")
    
    async def delete_context(self, agent_id: str) -> bool:
        """删除Agent上下文"""
        context = agent_context_data_store.contexts.pop(agent_id, None)
        if not context:
            logger.warning(f"未找到要删除的Agent上下文: {agent_id}")
            return False
        
        user_id = context.agent.user_id
        status = context.status
        sandbox_id = context.sandbox_id
        
        # 从用户Agent索引中移除
        if user_id and user_id in agent_context_data_store.user_agents_index:
            if agent_id in agent_context_data_store.user_agents_index[user_id]:
                agent_context_data_store.user_agents_index[user_id].remove(agent_id)
        
        # 从状态索引中移除
        if status in agent_context_data_store.status_index:
            if agent_id in agent_context_data_store.status_index[status]:
                agent_context_data_store.status_index[status].remove(agent_id)
        
        # 从沙盒索引中移除
        if sandbox_id and sandbox_id in agent_context_data_store.sandbox_index:
            del agent_context_data_store.sandbox_index[sandbox_id]
        
        logger.info(f"删除Agent上下文: {agent_id}, 用户: {user_id}")
        return True
    
    async def list_contexts(self, user_id: Optional[str] = None, status: Optional[str] = None, 
                           limit: int = 50, offset: int = 0) -> List[AgentContext]:
        """列出Agent上下文（支持按用户和状态过滤）"""
        result = []
        
        # 根据过滤条件获取agent_id列表
        if user_id and status:
            # 同时按用户和状态过滤
            user_agents = set(agent_context_data_store.user_agents_index.get(user_id, []))
            status_agents = set(agent_context_data_store.status_index.get(status, []))
            agent_ids = list(user_agents.intersection(status_agents))
        elif user_id:
            # 只按用户过滤
            agent_ids = agent_context_data_store.user_agents_index.get(user_id, [])
        elif status:
            # 只按状态过滤
            agent_ids = agent_context_data_store.status_index.get(status, [])
        else:
            # 不过滤，获取所有
            agent_ids = list(agent_context_data_store.contexts.keys())
        
        # 计算分页
        end_idx = min(offset + limit, len(agent_ids))
        paged_agent_ids = agent_ids[offset:end_idx]
        
        # 获取对应的上下文
        for agent_id in paged_agent_ids:
            context = agent_context_data_store.contexts.get(agent_id)
            if context:
                result.append(context)
        
        # 按更新时间排序（最新的在前）
        result.sort(key=lambda c: c.updated_at, reverse=True)
        
        return result
    
    async def get_contexts_by_user(self, user_id: str) -> List[AgentContext]:
        """获取指定用户的所有Agent上下文"""
        agent_ids = agent_context_data_store.user_agents_index.get(user_id, [])
        result = []
        
        for agent_id in agent_ids:
            context = agent_context_data_store.contexts.get(agent_id)
            if context:
                result.append(context)
        
        # 按更新时间排序（最新的在前）
        result.sort(key=lambda c: c.updated_at, reverse=True)
        
        return result
    
    async def get_contexts_by_status(self, status: str) -> List[AgentContext]:
        """获取指定状态的所有Agent上下文"""
        agent_ids = agent_context_data_store.status_index.get(status, [])
        result = []
        
        for agent_id in agent_ids:
            context = agent_context_data_store.contexts.get(agent_id)
            if context:
                result.append(context)
        
        # 按更新时间排序（最新的在前）
        result.sort(key=lambda c: c.updated_at, reverse=True)
        
        return result
    
    async def update_status(self, agent_id: str, status: str) -> bool:
        """更新Agent状态"""
        context = agent_context_data_store.contexts.get(agent_id)
        if not context:
            logger.warning(f"未找到Agent上下文: {agent_id}")
            return False
        
        old_status = context.status
        context.update_status(status)
        
        # 更新状态索引
        if old_status != status:
            # 从旧状态索引中移除
            if old_status in agent_context_data_store.status_index:
                if agent_id in agent_context_data_store.status_index[old_status]:
                    agent_context_data_store.status_index[old_status].remove(agent_id)
            
            # 添加到新状态索引
            if status not in agent_context_data_store.status_index:
                agent_context_data_store.status_index[status] = []
            if agent_id not in agent_context_data_store.status_index[status]:
                agent_context_data_store.status_index[status].append(agent_id)
        
        logger.debug(f"更新Agent状态: {agent_id}, {old_status} -> {status}")
        return True
    
    async def update_last_message(self, agent_id: str, message: str, timestamp: Optional[int] = None) -> bool:
        """更新最后消息"""
        context = agent_context_data_store.contexts.get(agent_id)
        if not context:
            logger.warning(f"未找到Agent上下文: {agent_id}")
            return False
        
        context.update_last_message(message, timestamp)
        logger.debug(f"更新Agent最后消息: {agent_id}")
        return True
    
    async def set_sandbox_id(self, agent_id: str, sandbox_id: str) -> bool:
        """设置沙盒ID"""
        context = agent_context_data_store.contexts.get(agent_id)
        if not context:
            logger.warning(f"未找到Agent上下文: {agent_id}")
            return False
        
        old_sandbox_id = context.sandbox_id
        context.set_sandbox_id(sandbox_id)
        
        # 更新沙盒索引
        if old_sandbox_id and old_sandbox_id in agent_context_data_store.sandbox_index:
            del agent_context_data_store.sandbox_index[old_sandbox_id]
        
        agent_context_data_store.sandbox_index[sandbox_id] = agent_id
        
        logger.debug(f"设置Agent沙盒ID: {agent_id}, {sandbox_id}")
        return True
    
    async def context_exists(self, agent_id: str) -> bool:
        """检查Agent上下文是否存在"""
        return agent_id in agent_context_data_store.contexts 