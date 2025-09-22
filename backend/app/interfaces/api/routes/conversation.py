from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator, List, Optional
from sse_starlette.event import ServerSentEvent
import logging
from app.application.services.agent import AgentService
from app.application.schemas.request import ReplayConversationRequest
from app.application.schemas.response import APIResponse, ConversationHistoryResponse, ConversationListResponse
from app.domain.models.user import User
from app.application.services.user_context import get_required_user

__all__ = ["router"]

router = APIRouter(prefix="/conversations", tags=["conversations"])

agent_service = AgentService()
logger = logging.getLogger(__name__)

@router.delete("/agent/{agent_id}", response_model=APIResponse[bool])
async def delete_conversation_history(agent_id: str) -> APIResponse[bool]:
    """
    删除指定Agent的会话历史
    
    Args:
        agent_id: Agent ID
        
    Returns:
        删除结果
    """
    logger.info(f"Deleting conversation history for agent {agent_id}")
    
    try:
        result = await agent_service.delete_conversation_history(agent_id)
        if result:
            return APIResponse.success(data=True, msg="Conversation history deleted successfully")
        else:
            return APIResponse.error(code=404, msg=f"Conversation history not found for agent {agent_id}")
            
    except Exception as e:
        logger.error(f"Error deleting conversation history for agent {agent_id}: {str(e)}")
        return APIResponse.error(code=500, msg=f"Failed to delete conversation history: {str(e)}")

@router.get("/list", response_model=APIResponse[ConversationListResponse])
async def list_conversations(
    user: User = Depends(get_required_user),
    limit: int = 50,
    offset: int = 0
) -> APIResponse[ConversationListResponse]:
    """
    列出会话历史
    
    Args:
        user_id: 用户ID，用于过滤（可选）
        limit: 每页数量
        offset: 偏移量
        
    Returns:
        会话列表响应
    """
    logger.info(f"Listing conversations for user {user.id}")
    
    try:
        histories = await agent_service.list_conversations(user.id, limit, offset)
        
        # 转换为响应模型
        conversations = [
            ConversationHistoryResponse(
                agent_id=history.agent_id,
                user_id=history.user_id,
                flow_id=history.flow_id,
                title=history.title,
                created_at=history.created_at,
                updated_at=history.updated_at,
                events=[
                    {
                        "id": event.id,
                        "agent_id": event.agent_id,
                        "event_type": event.event_type,
                        "event_data": event.event_data,
                        "timestamp": event.timestamp,
                        "sequence": event.sequence
                    }
                    for event in history.events
                ],
                total_events=len(history.events)
            )
            for history in histories
        ]
        
        response = ConversationListResponse(
            conversations=conversations,
            total=len(conversations),
            limit=limit,
            offset=offset
        )
        
        return APIResponse.success(response)
        
    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}")
        return APIResponse.error(code=500, msg=f"Failed to list conversations: {str(e)}") 