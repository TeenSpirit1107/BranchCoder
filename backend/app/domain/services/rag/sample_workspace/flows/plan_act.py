import logging
from app.domain.services.flows.base import BaseFlow
from app.domain.models.agent import Agent
from app.domain.models.event import AgentEvent
from typing import AsyncGenerator, Optional
from enum import Enum
from app.domain.models.event import (
    AgentEvent, 
    PlanCreatedEvent, 
    PlanCompletedEvent,
    DoneEvent,
    PauseEvent,
    PlanUpdatedEvent,
    MessageEvent,
    ToolCallingEvent,
    ToolCalledEvent
)
from app.domain.models.plan import ExecutionStatus, Plan
from app.domain.services.agents.planner import PlannerAgent
from app.domain.services.agents.execution import ExecutionAgent
from app.domain.services.agents.notify import NotifyAgent
from app.domain.external.llm import LLM, AudioLLM, ImageLLM, VideoLLM, ReasonLLM
from app.domain.external.sandbox import Sandbox
from app.domain.external.browser import Browser
from app.domain.external.search import SearchEngine
from app.infrastructure.logging import setup_plan_act_logger
from app.domain.models.memory import Memory

logger = logging.getLogger(__name__)

class AgentStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    UPDATING = "updating"
    REPORTING = "reporting"

class SubPlannerType(Enum):
    MESSAGE = "message"
    SHELL = "shell"
    SEARCH = "search"
    FILE = "file"

class PlanActFlow(BaseFlow):
    # 定义flow的唯一标识符
    flow_id = "plan_act"
    description = "计划-执行流程：先创建计划，然后逐步执行，支持动态更新计划"
    
    def __init__(self, agent: Agent, llm: LLM, audio_llm: AudioLLM, image_llm: ImageLLM, video_llm: VideoLLM, reason_llm: ReasonLLM, sandbox: Sandbox, browser: Browser, 
                 search_engine: Optional[SearchEngine] = None, **kwargs):
        super().__init__(agent, **kwargs)
        self.status = AgentStatus.IDLE
        self.plan = None
        
        # 设置专门的日志记录器
        self.plan_act_logger = setup_plan_act_logger("plan_act")
        self.plan_act_logger.info(f"=== PlanActFlow初始化 Agent ID: {agent.id} ===")
        
        # 创建计划代理和执行代理
        self.planner = PlannerAgent(
            llm=llm,
            memory=agent.planner_memory,
        )
        logger.debug(f"Created planner agent for Agent {self.agent.id}")
        self.plan_act_logger.info(f"创建Planner Agent完成")
        
        self.executor = ExecutionAgent(
            llm=llm,
            audio_llm=audio_llm,
            image_llm=image_llm,
            video_llm=video_llm,
            reason_llm=reason_llm,
            memory=agent.execution_memory,
            sandbox=sandbox,
            browser=browser,
            search_engine=search_engine,
        )
        logger.debug(f"Created execution agent for Agent {self.agent.id}")
        self.plan_act_logger.info(f"创建Execution Agent完成")
        
        # 创建通知代理，与执行代理共用memory
        self.notifier = NotifyAgent(
            llm=llm,
            memory=Memory(),  # 与execution agent共用memory
        )
        logger.debug(f"Created notify agent for Agent {self.agent.id}")
        self.plan_act_logger.info(f"创建Notify Agent完成")

    async def run(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        self.plan_act_logger.info(f"=== 开始处理用户消息 ===")
        self.plan_act_logger.info(f"用户输入: {message}")
        
        if not self.is_idle():
            # interrupt the current flow
            self.status = AgentStatus.PLANNING
            self.planner.roll_back()
            self.executor.roll_back()
            self.notifier.roll_back()  # 同时回滚notify agent
            self.plan_act_logger.info("中断当前流程，重新开始规划")

        logger.info(f"Agent {self.agent.id} started processing message: {message[:50]}...")
        step = None
        while True:
            if self.status == AgentStatus.IDLE:
                logger.info(f"Agent {self.agent.id} state changed from {AgentStatus.IDLE} to {AgentStatus.PLANNING}")
                self.status = AgentStatus.PLANNING
                self.plan_act_logger.info(f"状态变更: IDLE -> PLANNING")
                
                # 通知用户开始规划
                async for event in self.notifier.notify_received_message(message):
                    yield event
                    
            elif self.status == AgentStatus.PLANNING:
                # 创建计划
                logger.info(f"Agent {self.agent.id} started creating plan")
                self.plan_act_logger.info(f"=== 开始创建计划 ===")
                self.plan_act_logger.info(f"Planner输入: {message}")
                
                async for event in self.planner.create_plan(message):
                    if isinstance(event, PlanCreatedEvent):
                        self.plan = event.plan
                        logger.info(f"Agent {self.agent.id} created plan successfully with {len(event.plan.steps)} steps")
                        self.plan_act_logger.info(f"=== 计划创建成功 ===")
                        self.plan_act_logger.info(f"计划ID: {event.plan.id}")
                        self.plan_act_logger.info(f"计划目标: {event.plan.goal}")
                        self.plan_act_logger.info(f"计划标题: {event.plan.title}")
                        self.plan_act_logger.info(f"计划步骤数量: {len(event.plan.steps)}")
                        for i, step in enumerate(event.plan.steps, 1):
                            self.plan_act_logger.info(f"步骤{i}: [{step.id}] {step.description}")
                        if event.plan.message:
                            self.plan_act_logger.info(f"计划说明: {event.plan.message}")
                    elif isinstance(event, MessageEvent):
                        self.plan_act_logger.info(f"Planner输出: {event.message}")
                    yield event
                logger.info(f"Agent {self.agent.id} state changed from {AgentStatus.PLANNING} to {AgentStatus.EXECUTING}")
                self.status = AgentStatus.EXECUTING
                self.plan_act_logger.info(f"状态变更: PLANNING -> EXECUTING")
                    
            elif self.status == AgentStatus.EXECUTING:
                # 执行计划
                self.plan.status = ExecutionStatus.RUNNING
                step = self.plan.get_next_step()
                if not step:
                    logger.info(f"Agent {self.agent.id} has no more steps, state changed from {AgentStatus.EXECUTING} to {AgentStatus.REPORTING}")
                    self.status = AgentStatus.REPORTING
                    self.plan_act_logger.info(f"所有步骤执行完成，状态变更: EXECUTING -> REPORTING")
                    continue
                    
                # 执行步骤
                logger.info(f"Agent {self.agent.id} started executing step {step.id}: {step.description[:50]}...")
                self.plan_act_logger.info(f"=== 开始执行步骤 ===")
                self.plan_act_logger.info(f"步骤ID: {step.id}")
                self.plan_act_logger.info(f"步骤描述: {step.description}")
                self.plan_act_logger.info(f"Executor输入: 目标={self.plan.goal}, 步骤={step.description}")
                
                async for event in self.executor.execute_step(self.plan, step, message):
                    if isinstance(event, ToolCallingEvent):
                        self.plan_act_logger.info(f"工具调用: {event.tool_name}")
                        self.plan_act_logger.info(f"工具函数: {event.function_name}")
                        self.plan_act_logger.info(f"工具参数: {event.function_args}")
                    elif isinstance(event, ToolCalledEvent):
                        self.plan_act_logger.info(f"工具结果: {event.tool_name}")
                        self.plan_act_logger.info(f"工具函数: {event.function_name}")
                        self.plan_act_logger.info(f"工具输出: {event.function_result}")
                        if hasattr(event, 'error') and event.error:
                            self.plan_act_logger.error(f"工具错误: {event.error}")
                    elif isinstance(event, MessageEvent):
                        self.plan_act_logger.info(f"Executor输出: {event.message}")
                    yield event
                        
                logger.info(f"Agent {self.agent.id} completed step {step.id}, state changed from {AgentStatus.EXECUTING} to {AgentStatus.UPDATING}")
                self.plan_act_logger.info(f"步骤执行完成: {step.id}")
                self.plan_act_logger.info(f"步骤状态: {step.status}")
                if step.result:
                    self.plan_act_logger.info(f"步骤结果: {step.result}")
                if step.error:
                    self.plan_act_logger.error(f"步骤错误: {step.error}")
                self.status = AgentStatus.UPDATING
                self.plan_act_logger.info(f"状态变更: EXECUTING -> UPDATING")
                
            elif self.status == AgentStatus.UPDATING:
                if self.plan.status == ExecutionStatus.PAUSED:
                    break
                    
                # 执行Agent总结所作所为 / 压缩记忆上下文 / 获取浓缩的记忆，给到更新计划Agent
                self.plan_act_logger.info(f"=== 开始总结步骤 ===")
                previous_steps = ""
                async for event in self.executor.summarize_steps():
                    yield event
                    if isinstance(event, MessageEvent):
                        logger.info(f"Agent {self.agent.id} summarized steps, message: {event.message}")
                        previous_steps = event.message
                        self.plan_act_logger.info(f"步骤总结完成: {event.message}")
                        
                # 更新计划
                logger.info(f"Agent {self.agent.id} started updating plan")
                self.plan_act_logger.info(f"=== 开始更新计划 ===")
                self.plan_act_logger.info(f"计划更新输入 - 当前计划: {self.plan.model_dump_json(include={'steps'})}")
                self.plan_act_logger.info(f"计划更新输入 - 目标: {self.plan.goal}")
                self.plan_act_logger.info(f"计划更新输入 - 已完成步骤总结: {previous_steps}")
                
                async for event in self.planner.update_plan(self.plan, previous_steps):
                    if isinstance(event, PlanUpdatedEvent):
                        self._show_plan(event.plan)
                        self.plan_act_logger.info(f"=== 计划更新完成 ===")
                        self.plan_act_logger.info(f"更新后步骤数量: {len(event.plan.steps)}")
                        for i, step in enumerate(event.plan.steps, 1):
                            status_info = f" (状态: {step.status})" if step.status != ExecutionStatus.PENDING else ""
                            self.plan_act_logger.info(f"步骤{i}: [{step.id}] {step.description}{status_info}")
                    elif isinstance(event, MessageEvent):
                        self.plan_act_logger.info(f"计划更新输出: {event.message}")
                    elif isinstance(event, PauseEvent):
                        self.plan.status = ExecutionStatus.COMPLETED
                        self.plan_act_logger.info(f"状态变更: UPDATING -> COMPLETED")
                    yield event

                logger.info(f"Agent {self.agent.id} plan update completed, state changed from {AgentStatus.UPDATING} to {AgentStatus.EXECUTING}")
                self.status = AgentStatus.EXECUTING
                self.plan_act_logger.info(f"状态变更: UPDATING -> EXECUTING")

            elif self.status == AgentStatus.REPORTING:
                logger.info(f"Agent {self.agent.id} plan has been completed")
                self.plan_act_logger.info(f"=== 正在准备最终报告 ===")
                
                # 通知用户计划全部完成
                async for notify_event in self.notifier.notify_plan_progress(self.plan, "所有步骤已完成，正在准备最终报告"):
                    yield notify_event
                    
                async for event in self.executor.report_result(message):
                    yield event
                    
                self.status = AgentStatus.COMPLETED
                self.plan_act_logger.info(f"状态变更: REPORTING -> COMPLETED")
                
            elif self.status == AgentStatus.COMPLETED:
                self.plan.status = ExecutionStatus.COMPLETED
                logger.info(f"Agent {self.agent.id} plan has been completed")
                self.plan_act_logger.info(f"=== 计划执行完成 ===")
                self.plan_act_logger.info(f"最终计划状态: {self.plan.status}")
                    
                yield PlanCompletedEvent(plan=self.plan) 
                self.status = AgentStatus.IDLE
                self.plan_act_logger.info(f"状态变更: COMPLETED -> IDLE")
                break
        yield DoneEvent()
        
        logger.info(f"Agent {self.agent.id} message processing completed")
        self.plan_act_logger.info(f"=== 消息处理完成 ===")
    
    def is_idle(self) -> bool:
        return self.status == AgentStatus.IDLE
    
    def _show_plan(self, plan: Plan):
        logger.info("-" * 30)
        logger.info(f"Plan ID: {plan.id}")
        logger.info(f"Plan Goal: {plan.goal}")
        for step in plan.steps:
            logger.info(f"[{step.id}] {step.description}, Status: {step.status}, Result: {step.result}, Error: {step.error}")
        logger.info("-" * 30)
