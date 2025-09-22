import logging
from datetime import datetime

from typing import Optional, List, AsyncGenerator
from app.domain.external.conversation_repository import ConversationRepository
from app.domain.models.conversation import ConversationHistory, ConversationEvent
from app.domain.models.event import AgentEvent
# 导入所有AgentEvent类
from app.domain.models.event import (
    MessageEvent, ToolCallingEvent, ToolCalledEvent,
    PlanCreatedEvent, PlanUpdatedEvent, PlanCompletedEvent,
    StepStartedEvent, StepCompletedEvent, StepFailedEvent,
    ErrorEvent, DoneEvent
)


logger = logging.getLogger(__name__)

class ConversationService:
    """会话领域服务"""
    
    def __init__(self, conversation_repository: ConversationRepository):
        self.conversation_repository = conversation_repository
        logger.info("ConversationService initialized")
    
    async def create_conversation(self, agent_id: str, user_id: Optional[str] = None, flow_id: str = "plan_act") -> ConversationHistory:
        """创建新会话"""
        history = ConversationHistory(
            agent_id=agent_id,
            user_id=user_id,
            flow_id=flow_id
        )
        await self.conversation_repository.save_history(history)
        logger.info(f"Created new conversation for agent {agent_id}, user {user_id}, flow {flow_id}")
        return history
    
    async def record_event(self, agent_id: str, event: AgentEvent) -> ConversationEvent:
        """记录事件到会话历史"""
        # 直接存储事件类名和完整的事件数据
        event_data = {
            "event_class": event.__class__.__name__,
            **event.model_dump()
        }
        
        # 使用事件类名作为event_type
        event_type = event.__class__.__name__
        
        # 添加事件到仓储
        conversation_event = await self.conversation_repository.add_event(
            agent_id=agent_id,
            event_type=event_type,
            event_data=event_data
        )
        
        logger.debug(f"Recorded event {event_type} for agent {agent_id}")
        return conversation_event
    
    async def delete_conversation(self, agent_id: str) -> bool:
        """删除会话历史"""
        result = await self.conversation_repository.delete_history(agent_id)
        if result:
            logger.info(f"Deleted conversation history for agent {agent_id}")
        return result
    
    async def list_conversations(self, user_id: str, limit: int = 50, offset: int = 0) -> List[ConversationHistory]:
        """列出会话历史"""
        return await self.conversation_repository.list_histories(user_id, limit, offset)
    
    async def update_title(self, agent_id: str, title: str) -> bool:
        """更新会话标题"""
        history = await self.conversation_repository.get_history(agent_id)
        if not history:
            logger.warning(f"Cannot update title for non-existent conversation: {agent_id}")
            return False
        
        if history.title:
            return False
        history.title = title
        history.updated_at = datetime.now()
        await self.conversation_repository.save_history(history)
        logger.info(f"Updated title for conversation {agent_id}: {title}")
        return True
    
    def _rebuild_agent_event(self, conversation_event: ConversationEvent) -> Optional[AgentEvent]:
        """从ConversationEvent重建AgentEvent对象"""
        try:
            event_class_name = conversation_event.event_data.get("event_class")
            if not event_class_name:
                logger.warning(f"No event_class found in conversation event {conversation_event.id}")
                return None
            
            # 获取事件类
            event_classes = {
                "MessageEvent": MessageEvent,
                "ToolCallingEvent": ToolCallingEvent,
                "ToolCalledEvent": ToolCalledEvent,
                "PlanCreatedEvent": PlanCreatedEvent,
                "PlanUpdatedEvent": PlanUpdatedEvent,
                "PlanCompletedEvent": PlanCompletedEvent,
                "StepStartedEvent": StepStartedEvent,
                "StepCompletedEvent": StepCompletedEvent,
                "StepFailedEvent": StepFailedEvent,
                "ErrorEvent": ErrorEvent,
                "DoneEvent": DoneEvent
            }
            
            event_class = event_classes.get(event_class_name)
            if not event_class:
                logger.warning(f"Unknown event class: {event_class_name}")
                return None
            
            # 从存储的数据中移除event_class字段，剩下的就是原始事件数据
            event_data = conversation_event.event_data.copy()
            event_data.pop("event_class", None)
            
            # 重建AgentEvent对象
            agent_event = event_class(**event_data)
            logger.debug(f"Successfully rebuilt {event_class_name} from conversation event")
            return agent_event
            
        except Exception as e:
            logger.error(f"Error rebuilding AgentEvent from conversation event {conversation_event.id}: {str(e)}")
            return None 