import logging

from app.domain.services.flows.base import BaseFlow
from app.domain.models.agent import Agent
from typing import AsyncGenerator, Optional
from app.domain.models.event import (
    AgentEvent, MessageEvent,
)
from app.domain.external.sandbox import Sandbox
from app.domain.external.browser import Browser
from app.domain.external.search import SearchEngine
from app.domain.external.llm import LLM, AudioLLM, ImageLLM, VideoLLM, ReasonLLM
from app.domain.services.rag.rag_service import RagService

from app.domain.models.event import ReportEvent

logger = logging.getLogger(__name__)

class BranchCodeFlow(BaseFlow):
    flow_id = "BranchCodeFlow"
    description = "a flow that uses multiple planners to handle complex tasks"

    def __init__(self, agent: Agent, llm: LLM, sandbox: Sandbox, browser: Browser,
                 search_engine: Optional[SearchEngine] = None,
                 audio_llm: Optional[AudioLLM] = None,
                 image_llm: Optional[ImageLLM] = None,
                 video_llm: Optional[VideoLLM] = None,
                 reason_llm: Optional[ReasonLLM] = None,
                 **kwargs):
        super().__init__(agent, **kwargs)

        self.llm = llm
        self.sandbox = sandbox
        self.browser = browser
        self.search_engine = search_engine
        self.audio_llm = audio_llm
        self.image_llm = image_llm
        self.video_llm = video_llm
        self.reason_llm = reason_llm

        self.rag_service = RagService(
            llm=self.llm,
            enable_rerank=True,
            rerank_top_n=10,
            initial_candidates=30
        )


    async def run(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        # await self.rag_service.initiate('sample_workspace')
        result = await self.rag_service.retrival(message)
        logger.info(result)
        yield ReportEvent(message=str(result))

    def is_idle(self) -> bool:
        return False

