from enum import Enum

from app.domain.models.event import AgentEvent
from app.domain.models.agent import Agent
from typing import AsyncGenerator, Optional, Protocol
from abc import ABC, abstractmethod

from app.domain.models.plan import Plan, Step
from app.domain.models.memory import Memory
from app.domain.external.llm import LLM, AudioLLM, ImageLLM, VideoLLM, ReasonLLM
from app.domain.external.sandbox import Sandbox
from app.domain.external.browser import Browser
from app.domain.external.search import SearchEngine

class BaseFlow(ABC):
    # 每个flow类都需要定义一个唯一的flow_id
    flow_id: str = None
    
    def __init__(self, agent: Agent, **kwargs):
        self.agent = agent
        # 验证flow_id是否已定义
        if self.flow_id is None:
            raise ValueError(f"Flow class {self.__class__.__name__} must define a flow_id")

    @abstractmethod
    async def run(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        """执行flow的主要逻辑"""
        pass
    
    @abstractmethod
    def is_idle(self) -> bool:
        """检查flow是否处于空闲状态"""
        pass
    
    @classmethod
    def get_flow_id(cls) -> str:
        """获取flow的唯一标识符"""
        return cls.flow_id

    @classmethod
    def get_description(cls) -> str:
        """获取flow的描述信息"""
        return getattr(cls, 'description', f"Flow {cls.flow_id}")

class BaseSubFlow(ABC):
    """
    子规划器流程的基础接口类
    定义了子规划器流程必须实现的核心方法
    """
    # 每个flow类都需要定义一个唯一的flow_id
    flow_id: str = None

    # 初始化SubFlow可用的基础设施
    def __init__(
        self,
        llm: LLM,
        sandbox: Optional[Sandbox] = None,
        browser: Optional[Browser] = None,
        search_engine: Optional[SearchEngine] = None,
        audio_llm: Optional[AudioLLM] = None,
        image_llm: Optional[ImageLLM] = None,
        video_llm: Optional[VideoLLM] = None,
        reason_llm: Optional[ReasonLLM] = None,
        task_type: Optional[Enum] = None,
    ):
        self.llm = llm
        self.sandbox = sandbox
        self.browser = browser
        self.search_engine = search_engine
        self.audio_llm = audio_llm
        self.image_llm = image_llm
        self.video_llm = video_llm
        self.reason_llm = reason_llm
        self.task_type = task_type

    @abstractmethod
    async def run(self, parent_plan: Plan, parent_step: Step, parent_memory: Memory,
                   task_type: Enum) -> AsyncGenerator[AgentEvent, None]:
        """
        执行计划中的单个步骤
        根据步骤类型创建对应的子规划器并执行
        并生成当前子规划器的最终报告
        包括执行过程、工具使用和最终结果

        Args:
            parent_plan: 父规划器当前的计划
            parent_step: 要执行的步骤
            parent_memory: 父规划器当前的记忆
            task_type: 当前步骤的任务类型

        Yields:
            AgentEvent: 执行过程中的各种事件
        """
        pass

    @abstractmethod
    def is_idle(self) -> bool:
        """检查flow是否处于空闲状态"""
        pass

    @classmethod
    def get_flow_id(cls) -> str:
        """获取flow的唯一标识符"""
        return cls.flow_id

    @classmethod
    def get_description(cls) -> str:
        """获取flow的描述信息"""
        return getattr(cls, 'description', f"Flow {cls.flow_id}")