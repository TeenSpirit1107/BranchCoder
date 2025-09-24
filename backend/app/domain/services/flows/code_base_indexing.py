import logging
from typing import AsyncGenerator, Optional
from enum import Enum

from app.domain.services.flows.base import BaseSubFlow
from app.domain.models.event import (
    AgentEvent, DoneEvent,
)
from app.domain.models.plan import Plan, Step
from app.domain.external.llm import LLM, AudioLLM, ImageLLM, VideoLLM, ReasonLLM
from app.domain.external.sandbox import Sandbox
from app.domain.external.browser import Browser
from app.domain.external.search import SearchEngine
from app.domain.models.memory import Memory
from app.domain.services.rag.description_generator import DescriptionGenerator

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    UPDATING = "updating"
    REPORTING = "reporting"


class CodeFlow(BaseSubFlow):
    # 定义flow的唯一标识符
    flow_id = "code"
    description = "子计划规划流程：先创建子计划，然后逐步执行，支持动态更新子计划"

    def __init__(
            self,
            llm: LLM,
            sandbox: Sandbox,
            browser: Browser,
            search_engine: Optional[SearchEngine] = None,
            audio_llm: Optional[AudioLLM] = None,
            image_llm: Optional[ImageLLM] = None,
            video_llm: Optional[VideoLLM] = None,
            reason_llm: Optional[ReasonLLM] = None,
            task_type: Enum = None,
    ):

        super().__init__(
            llm=llm,
            sandbox=sandbox,
            browser=browser,
            search_engine=search_engine,
            audio_llm=audio_llm,
            image_llm=image_llm,
            video_llm=video_llm,
            reason_llm=reason_llm,
            task_type=task_type,
        )

        self.status = AgentStatus.IDLE

        self.description_generator = DescriptionGenerator(
            llm=llm,
        )

    async def run(
            self,
            parent_plan: Plan,
            parent_step: Step,
            parent_memory: Memory,
            task_type: Enum
    ) -> AsyncGenerator[AgentEvent, None]:
        self.description_generator.run(workspace_dir=parent_step.workspace_dir)
        return DoneEvent

    def is_idle(self) -> bool:
        return self.status == AgentStatus.IDLE
