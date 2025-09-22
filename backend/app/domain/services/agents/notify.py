from typing import AsyncGenerator, Optional
from datetime import datetime
from app.domain.models.plan import Plan, Step, ExecutionStatus
from app.domain.services.agents.base import BaseAgent
from app.domain.models.memory import Memory
from app.domain.external.llm import LLM
from app.domain.services.prompts.notify import (
    NOTIFY_SYSTEM_PROMPT, 
    NOTIFY_PROMPT
)
from app.domain.models.event import (
    AgentEvent,
    MessageEvent,
    ErrorEvent
)
from app.domain.services.tools.message import MessageNotifyUserTool


class NotifyAgent(BaseAgent):
    """
    Notify agent class, defining the basic behavior of notification
    专门用于通知用户任务进展的代理，只能调用message_notify_user工具
    """

    system_prompt: str = NOTIFY_SYSTEM_PROMPT.format(cur_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def __init__(
        self,
        memory: Memory,
        llm: LLM,
    ):
        # 只初始化MessageTool，限制只能使用message_notify_user工具
        super().__init__(memory, llm, [MessageNotifyUserTool()])
        self.max_iterations = 1
    
    async def notify_step_progress(self, plan: Plan, step: Step, status: str) -> AsyncGenerator[AgentEvent, None]:
        """
        通知用户步骤进展
        
        Args:
            plan: 当前执行的计划
            step: 当前执行的步骤
            status: 步骤状态描述
            
        Yields:
            AgentEvent: 代理事件流
        """
        message = NOTIFY_PROMPT.format(
            goal=plan.goal, 
            step=step.description,
            status=status
        )
        
        async for event in self.execute(message):
            if isinstance(event, ErrorEvent):
                # 如果通知失败，记录错误但不中断主流程
                self.logger.error(f"Notification failed: {event.error}")
            yield event
    
    async def notify_plan_progress(self, plan: Plan, message: str) -> AsyncGenerator[AgentEvent, None]:
        """
        通知用户计划整体进展
        
        Args:
            plan: 当前执行的计划
            message: 自定义通知消息
            
        Yields:
            AgentEvent: 代理事件流
        """
        notify_message = f"""
你正在为以下计划提供通知服务：

计划目标：
{plan.goal}

计划标题：
{plan.title}

通知内容：
{message}

请向用户发送适当的通知消息，说明当前计划的整体进展情况。
"""
        
        async for event in self.execute(notify_message):
            if isinstance(event, ErrorEvent):
                # 如果通知失败，记录错误但不中断主流程
                self.logger.error(f"Plan notification failed: {event.error}")
            yield event

    async def notify_received_message(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        """
        通知用户收到消息
        """
        notify_message = f"""回复用户你已经收到消息，并且尽快开始分析。
        
        用户请求：
        {message}
        """

        async for event in self.execute(notify_message):
            if isinstance(event, ErrorEvent):
                # 如果通知失败，记录错误但不中断主流程
                self.logger.error(f"Received message notification failed: {event.error}")
            yield event

    
    async def notify_custom_message(self, custom_message: str) -> AsyncGenerator[AgentEvent, None]:
        """
        发送自定义通知消息
        
        Args:
            custom_message: 自定义通知内容
            
        Yields:
            AgentEvent: 代理事件流
        """
        notify_message = f"""
请向用户发送以下通知消息：

{custom_message}

确保消息简洁明了，使用用户友好的语言。
"""
        
        async for event in self.execute(notify_message):
            if isinstance(event, ErrorEvent):
                # 如果通知失败，记录错误但不中断主流程
                self.logger.error(f"Custom notification failed: {event.error}")
            yield event
