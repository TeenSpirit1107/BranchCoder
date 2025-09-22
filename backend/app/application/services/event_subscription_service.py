from typing import AsyncGenerator
import logging
from app.domain.models.event import AgentEvent
from app.domain.services.event_subscription_service import EventSubscriptionDomainService
from app.application.schemas.event_subscription import EventStreamRequest

logger = logging.getLogger(__name__)


class EventSubscriptionApplicationService:
    """事件订阅应用服务 - 纯发布订阅模式"""

    def __init__(self, event_subscription_domain_service: EventSubscriptionDomainService):
        self.domain_service = event_subscription_domain_service

    async def get_event_stream(self, request: EventStreamRequest) -> AsyncGenerator[AgentEvent, None]:
        """获取事件流用例"""
        logger.info(f"Starting event stream for agent {request.agent_id} from sequence {request.from_sequence}")
        
        async for event in self.domain_service.get_event_stream(
            agent_id=request.agent_id,
            from_sequence=request.from_sequence
        ):
            yield event

    async def broadcast_event(self, agent_id: str, event: AgentEvent) -> int:
        """广播事件用例"""
        return await self.domain_service.broadcast_event(agent_id, event)

    async def get_agent_subscription_count(self, agent_id: str) -> int:
        """获取Agent活跃订阅者数量用例"""
        return await self.domain_service.get_agent_subscription_count(agent_id)

    async def cleanup_agent_streams(self, agent_id: str) -> bool:
        """清理Agent事件流用例"""
        logger.info(f"Cleaning up streams for agent {agent_id}")
        return await self.domain_service.cleanup_agent_streams(agent_id)

    async def cleanup_inactive_subscribers(self, agent_id: str, timeout_minutes: int = 30) -> int:
        """清理不活跃订阅者用例"""
        logger.info(f"Cleaning up inactive subscribers for agent {agent_id} older than {timeout_minutes} minutes")
        return await self.domain_service.cleanup_inactive_subscribers(agent_id, timeout_minutes) 