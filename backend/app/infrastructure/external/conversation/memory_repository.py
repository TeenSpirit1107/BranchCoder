"""对话仓储内存实现"""

import logging
from datetime import datetime
from typing import Optional, List

from app.domain.external.conversation_repository import ConversationRepository
from app.domain.models.conversation import ConversationHistory, ConversationEvent
from app.infrastructure.external.user.memory_repository import conversation_data_store

logger = logging.getLogger(__name__)

class MemoryConversationRepository(ConversationRepository):
    """对话仓储内存实现"""
    
    async def save_history(self, history: ConversationHistory) -> None:
        """保存会话历史"""
        conversation_data_store.histories[history.agent_id] = history
        
        # 更新用户会话索引
        if history.user_id not in conversation_data_store.user_histories_index:
            conversation_data_store.user_histories_index[history.user_id] = []
            
        if history.agent_id not in conversation_data_store.user_histories_index[history.user_id]:
            conversation_data_store.user_histories_index[history.user_id].append(history.agent_id)
            
        logger.debug(f"保存会话历史: {history.agent_id}, 用户: {history.user_id}")
    
    async def get_history(self, agent_id: str) -> Optional[ConversationHistory]:
        """获取会话历史"""
        return conversation_data_store.histories.get(agent_id)
    
    async def add_event(self, agent_id: str, event_type: str, event_data: dict) -> ConversationEvent:
        """添加事件到会话历史"""
        # 获取会话历史
        history = await self.get_history(agent_id)
        if not history:
            logger.error(f"未找到会话历史: {agent_id}")
            raise ValueError(f"会话历史不存在: {agent_id}")
        
        # 确保事件表中有该agent_id的条目
        if agent_id not in conversation_data_store.events:
            conversation_data_store.events[agent_id] = {}
        
        # 计算事件序号
        next_sequence = max(conversation_data_store.events[agent_id].keys(), default=0) + 1
        
        # 创建事件
        event = ConversationEvent(
            id=f"{agent_id}_{next_sequence}",
            agent_id=agent_id,
            event_type=event_type,
            event_data=event_data,
            sequence=next_sequence,
            timestamp=datetime.now()
        )
        
        # 保存事件到事件表
        conversation_data_store.events[agent_id][next_sequence] = event
        
        # 将事件添加到会话历史的events列表中
        history.events.append(event)
        
        # 更新会话历史的最后更新时间
        history.updated_at = datetime.now()
        await self.save_history(history)
        
        logger.debug(f"添加事件: {event.id}, 类型: {event_type}, 序号: {next_sequence}")
        return event
    
    async def get_events_from_sequence(self, agent_id: str, from_sequence: int = 1) -> List[ConversationEvent]:
        """获取从指定序号开始的事件"""
        if agent_id not in conversation_data_store.events:
            return []
        
        events = conversation_data_store.events[agent_id]
        return [events[seq] for seq in sorted(events.keys()) if seq >= from_sequence]
    
    async def delete_history(self, agent_id: str) -> bool:
        """删除会话历史"""
        # 获取会话历史
        history = conversation_data_store.histories.pop(agent_id, None)
        if not history:
            logger.warning(f"未找到要删除的会话历史: {agent_id}")
            return False
        
        # 从用户会话索引中移除
        if history.user_id in conversation_data_store.user_histories_index:
            if agent_id in conversation_data_store.user_histories_index[history.user_id]:
                conversation_data_store.user_histories_index[history.user_id].remove(agent_id)
        
        # 删除事件
        conversation_data_store.events.pop(agent_id, None)
        
        logger.info(f"删除会话历史: {agent_id}, 用户: {history.user_id}")
        return True
    
    async def list_histories(self, user_id: str, limit: int = 50, offset: int = 0) -> List[ConversationHistory]:
        """列出会话历史（支持按用户过滤）"""
        result = []
        
        # 获取用户关联的所有agent_id
        agent_ids = conversation_data_store.user_histories_index.get(user_id, [])
        
        # 计算分页
        end_idx = min(offset + limit, len(agent_ids))
        paged_agent_ids = agent_ids[offset:end_idx]
        
        # 获取对应的会话历史
        for agent_id in paged_agent_ids:
            history = conversation_data_store.histories.get(agent_id)
            if history:
                result.append(history)
        
        # 按更新时间排序（最新的在前）
        result.sort(key=lambda h: h.updated_at, reverse=True)
        
        return result 