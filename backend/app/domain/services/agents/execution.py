from typing import AsyncGenerator, Optional
from datetime import datetime
from app.domain.models.plan import Plan, Step, ExecutionStatus
from app.domain.services.agents.base import BaseAgent
from app.domain.models.memory import Memory
from app.domain.external.llm import LLM, AudioLLM, ImageLLM, VideoLLM, ReasonLLM
from app.domain.external.sandbox import Sandbox
from app.domain.external.browser import Browser
from app.domain.external.search import SearchEngine
from app.domain.services.prompts.execution_no_tool import (
    EXECUTION_SYSTEM_PROMPT_NO_TOOL,
    EXECUTION_PROMPT,
    SUMMARIZE_STEP_PROMPT,
    FLUSH_MEMORY_PROMPT,
    PERSISTENT_RESULT_PROMPT,
    REPORT_RESULT_PROMPT,
)

from app.domain.services.prompts.prompt_manager import PromptManager

from app.domain.models.event import (
    AgentEvent,
    StepFailedEvent,
    StepCompletedEvent,
    MessageEvent,
    ErrorEvent,
    StepStartedEvent,
    PauseEvent,
    ReportEvent
)
from app.domain.services.tools.shell import ShellTool
from app.domain.services.tools.browser import BrowserTool
from app.domain.services.tools.search import SearchTool
from app.domain.services.tools.file import FileTool
from app.domain.services.tools.message import MessageDeliverArtifactTool
from app.domain.services.tools.audio import AudioTool
from app.domain.services.tools.image import ImageTool
from app.domain.services.tools.video import VideoTool
from app.domain.services.tools.reasoning import DeepReasoningTool
from app.domain.services.tools.mcp import McpTool
from app.infrastructure.logging import setup_agent_logger

class ExecutionAgent(BaseAgent):
    """
    Execution agent class, defining the basic behavior of execution
    """

    def __init__(
        self,
        memory: Memory,
        llm: LLM,
        audio_llm: AudioLLM,
        image_llm: ImageLLM,
        video_llm: VideoLLM,
        reason_llm: ReasonLLM,
        sandbox: Sandbox,
        browser: Browser,
        search_engine: Optional[SearchEngine] = None,
        type_value: str = "message"
    ):
        super().__init__(memory, llm, [   
            ShellTool(sandbox),
            BrowserTool(browser),
            FileTool(sandbox),
            MessageDeliverArtifactTool(),
            AudioTool(sandbox, audio_llm, llm),
            ImageTool(sandbox, image_llm),
            VideoTool(sandbox, video_llm),
            DeepReasoningTool(reason_llm),
            McpTool(
                sandbox,
                pre_install_servers=[
                    "mcp-server-site-search"
                ]
            )
        ])
        
        # Only add search tool when search_engine is not None
        if search_engine:
            self.tools.append(SearchTool(search_engine))
        self.system_prompt = PromptManager.insert_datetime(PromptManager.get_system_prompt_with_tools(self.tools, is_executor=True))
        self.execution_agent_logger = setup_agent_logger("execution_agent")

    @property
    def shell_tool(self) -> Optional[ShellTool]:
        """Get the shell tool from tools list"""
        for tool in self.tools:
            if isinstance(tool, ShellTool):
                return tool
        return None

    async def execute_step(self, plan: Plan, step: Step, message: str) -> AsyncGenerator[AgentEvent, None]:
        
        # update prompt
        try:
            self.system_prompt = await PromptManager.update_ls(self.system_prompt, self.shell_tool)
        except Exception as e:
            self.execution_agent_logger.error(f"更新系统提示词失败: {str(e)}")
            self.execution_agent_logger.error(f"错误类型: {type(e)}")
            import traceback
            self.execution_agent_logger.error(f"错误堆栈: {traceback.format_exc()}")
            # 继续执行，不因为提示词更新失败而中断整个流程
        
        message = EXECUTION_PROMPT.format(goal=plan.goal, all_steps=plan.steps, step=step.description, message=message)
        
        step.status = ExecutionStatus.RUNNING
        yield StepStartedEvent(step=step, plan=plan)

        # debug H
        self.execution_agent_logger.info("==="*10)
        self.execution_agent_logger.info(f"EXECUTOR")
        self.execution_agent_logger.info(f"self.system_prompt: {self.system_prompt}")
        self.execution_agent_logger.info("==="*10)

        async for event in self.execute(message):
            if isinstance(event, ErrorEvent):
                step.status = ExecutionStatus.FAILED
                step.error = event.error
                yield StepFailedEvent(
                    step=Step(
                        id="sub_task",
                        description=step.description,
                        status=ExecutionStatus.FAILED,
                        error=event.error
                    ),
                    plan=Plan(
                        id=f"sub_plan_{step.id}",
                        title=f"Sub Plan for {step.id} task",
                        goal=plan.goal,
                        steps=[Step(
                            id="sub_task",
                            description=step.description,
                            status=ExecutionStatus.FAILED,
                            error=event.error
                        )]
                    )
                )
                return
            
            if isinstance(event, PauseEvent):
                yield event
                return
            
            if isinstance(event, MessageEvent):
                step.status = ExecutionStatus.COMPLETED
                step.result = event.message
                yield StepCompletedEvent(step=step, plan=plan)
            yield event
        step.status = ExecutionStatus.COMPLETED

    async def summarize_steps(self) -> AsyncGenerator[AgentEvent, None]:
        async for event in self.execute(PERSISTENT_RESULT_PROMPT):
            yield event

        async for event in self.execute(SUMMARIZE_STEP_PROMPT):
            if isinstance(event, MessageEvent):
                self.memory.clear_messages()
                self.memory.add_message({
                    "role": "system",
                    "content": self.system_prompt
                })
                self.memory.add_message({
                    "role": "system",
                    "content": FLUSH_MEMORY_PROMPT.format(previous_steps=event.message)
                })
            yield event
        
    async def report_result(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        async for event in self.execute(REPORT_RESULT_PROMPT.format(message=message)):
            if isinstance(event, MessageEvent):
                yield ReportEvent(message=event.message)
                return
            yield event
