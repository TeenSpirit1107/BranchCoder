import logging
from app.domain.services.flows.base import BaseFlow
from app.domain.models.agent import Agent
from app.domain.models.event import AgentEvent, MessageEvent, DoneEvent
from typing import AsyncGenerator, Optional
from app.domain.external.llm import LLM, AudioLLM, ImageLLM, VideoLLM, ReasonLLM
from app.domain.external.sandbox import Sandbox
from app.domain.external.browser import Browser
from app.domain.external.search import SearchEngine

logger = logging.getLogger(__name__)

class SimpleChatFlow(BaseFlow):
    """简单聊天流程：直接与LLM对话，不进行计划和执行"""
    
    # 定义flow的唯一标识符
    flow_id = "simple_chat"
    description = "简单聊天流程：直接与LLM对话，适用于简单的问答场景"
    
    def __init__(self, agent: Agent, llm: LLM, audio_llm: AudioLLM, image_llm: ImageLLM, video_llm: VideoLLM, reason_llm: ReasonLLM, sandbox: Sandbox, browser: Browser, 
                 search_engine: Optional[SearchEngine] = None, **kwargs):
        super().__init__(agent, **kwargs)
        self.llm = llm
        self.audio_llm = audio_llm
        self.image_llm = image_llm
        self.video_llm = video_llm
        self.reason_llm = reason_llm
        self.sandbox = sandbox
        self.browser = browser
        self.search_engine = search_engine
        self._is_idle = True
        logger.debug(f"Created SimpleChatFlow for Agent {self.agent.id}")
    
    async def run(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        """执行简单聊天流程"""
        self._is_idle = False
        logger.info(f"Agent {self.agent.id} started simple chat with message: {message[:50]}...")
        
        try:
            # 构建简单的提示词
            prompt = f"""你是一个有用的AI助手。请回答用户的问题。

用户问题: {message}

请提供有用和准确的回答："""
            
            # 调用LLM获取回复
            response = await self.llm.ask(
                messages=[{"role": "user", "content": prompt}],
            )
            
            # 发送回复事件
            yield MessageEvent(message=response.content)
            logger.info(f"Agent {self.agent.id} completed simple chat response")
            
        except Exception as e:
            logger.error(f"Agent {self.agent.id} simple chat failed: {str(e)}")
            yield MessageEvent(message=f"抱歉，处理您的请求时出现错误：{str(e)}")
        
        finally:
            self._is_idle = True
            yield DoneEvent()
    
    def is_idle(self) -> bool:
        """检查flow是否处于空闲状态"""
        return self._is_idle 