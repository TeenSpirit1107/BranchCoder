import logging
from collections import deque

from app.domain.services.flows.base import BaseFlow, BaseSubFlow
from app.domain.models.agent import Agent
from typing import AsyncGenerator, Optional, Dict
from enum import Enum
from app.domain.models.event import (
    AgentEvent,
    PlanCreatedEvent,
    PlanCompletedEvent,
    DoneEvent,
    PauseEvent,
    PlanUpdatedEvent,
    MessageEvent,
    StepFailedEvent,
    StepCompletedEvent,
    StepStartedEvent,
    ErrorEvent,
    ReportEvent,
)
from app.domain.models.plan import ExecutionStatus, Plan, Step
from app.domain.services.agents.super_planner import PlannerAgent, ReportAgent
from app.domain.services.agents.notify import NotifyAgent
from app.domain.external.sandbox import Sandbox
from app.domain.external.browser import Browser
from app.domain.external.search import SearchEngine
from app.infrastructure.logging import setup_super_planner_flow_logger
from app.domain.models.memory import Memory
from app.domain.external.llm import LLM, AudioLLM, ImageLLM, VideoLLM, ReasonLLM

logger = logging.getLogger(__name__)

class FlowStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    UPDATING = "updating"
    REPORTING = "reporting"

class SuperFlow(BaseFlow):
    # 定义flow的唯一标识符
    flow_id = "TreeFLow"
    description = "a flow that uses multiple planners to handle complex tasks"

    def __init__(self, agent: Agent, llm: LLM, sandbox: Sandbox, browser: Browser,
                 search_engine: Optional[SearchEngine] = None, 
                 audio_llm: Optional[AudioLLM] = None,
                 image_llm: Optional[ImageLLM] = None,
                 video_llm: Optional[VideoLLM] = None,
                 reason_llm: Optional[ReasonLLM] = None,
                 **kwargs):
        super().__init__(agent, **kwargs)
        self.status = FlowStatus.IDLE

        # 设置专门的日志记录器
        self.super_flow_logger = setup_super_planner_flow_logger("SuperPlannerFlow")
        self.super_flow_logger.info(f"=== SuperPlannerFlow初始化 Agent ID: {agent.id} ===")

        # 初始化可用的基础设施
        self.llm = llm
        self.sandbox = sandbox
        self.browser = browser
        self.search_engine = search_engine
        self.audio_llm = audio_llm
        self.image_llm = image_llm
        self.video_llm = video_llm
        self.reason_llm = reason_llm

        # 初始化planner memory
        self.planner_memory = Memory()
        # 初始化knowledge memory
        self.knowledge = Memory()

        # 创建 planer agent
        self.planner_agent = PlannerAgent(
            llm=llm,
            memory = self.planner_memory,
            knowledge=self.knowledge,
        )
        self.super_flow_logger.debug(f"创建Planner Agent完成")

        self.report_agent = ReportAgent(
            llm=llm,
            memory = Memory(),
            knowledge=self.knowledge,
        )
        self.super_flow_logger.debug(f"创建Report Agent完成")

        # 创建 sub_flow_factory
        from app.domain.services.flows.factory import sub_flow_factory
        self.sub_flow_factory = sub_flow_factory
        self.sub_flow_type = self.sub_flow_factory.get_available_flows_enum()

        # 创建通知代理，通知用户进度
        self.notifier = NotifyAgent(
            llm=llm,
            memory=Memory(),
        )
        self.super_flow_logger.debug(f"创建Notify Agent完成")

        # 用于控制流和并发实现
        # 按照并发组划分的sub planner
        self.parallel_sub_flow_groups = None
        # 记录使用过的sub planner
        self.sub_flow_instance_used = []
        # 管理活动的子规划器
        self._active_sub_flow: Dict[str, BaseSubFlow] = {}
        # 记录子规划器的执行历史
        self._sub_flow_history: Dict[str, Dict] = {}


    @staticmethod
    def _determine_task_type(description: str) -> str:
        """
        根据步骤描述确定流程类型
        """
        description_lower = description.lower()
        if any(cmd in description_lower for cmd in ["run", "execute", "command", "shell"]):
            return "code"
        elif any(cmd in description_lower for cmd in ["browse", "visit", "web", "url", "search", "find", "lookup"]):
            return "search"
        elif any(cmd in description_lower for cmd in ["reason", "think", "analyze", "deduce", "infer"]):
            return "reasoning"
        elif any(cmd in description_lower for cmd in ["file", "document", "read", "write", "process"]):
            return "file"
        else:
            return "search" # 默认使用搜索流程


    async def execute_step(self, step: Step) -> AsyncGenerator[AgentEvent, None]:
        """
        执行计划中的单个步骤
        根据步骤类型创建对应的子流程并执行
        """
        self.super_flow_logger.info(f"执行子任务步骤 {step.id}: {step.description}")
        
        # 确定任务类型
        if step.sub_flow_type:
            # 添加调试信息
            self.super_flow_logger.debug(f"step.sub_flow_type 类型: {type(step.sub_flow_type)}")

            # 标准化处理
            if isinstance(step.sub_flow_type, str):
                # 如果是字符串，转换为 SubPlannerType 枚举
                task_type = self.sub_flow_type(step.sub_flow_type.lower())
                self.super_flow_logger.debug(f"字符串转换为枚举: {task_type}")
            else:
                # 如果是枚举，直接使用
                task_type = step.sub_flow_type
                self.super_flow_logger.debug(f"使用枚举: {task_type}")

            self.super_flow_logger.debug(f"使用 SuperPlanner 指定的任务类型: {task_type}")
        else:
            # 如果没有指定，才根据描述判断
            task_type = self._determine_task_type(step.description)
            self.super_flow_logger.debug(f"根据描述推断的任务类型: {task_type}")

        # 创建新的子规划器 SubFlow
        sub_flow = self.sub_flow_factory.create_flow(
            llm=self.llm,
            task_type=task_type,
            sandbox=self.sandbox,
            browser=self.browser,
            search_engine=self.search_engine,
            audio_llm=self.audio_llm,
            image_llm=self.image_llm,
            video_llm=self.video_llm,
            reason_llm=self.reason_llm,
        )

        step.status = ExecutionStatus.RUNNING
        yield StepStartedEvent(step=step, plan=self.plan)

        try:
            async for event in sub_flow.run(
                parent_plan = self.plan,
                parent_step = step,
                parent_memory = self.knowledge,
                task_type = task_type,
            ):
                # sub flow返回值处理 
                if isinstance(event, ErrorEvent):
                    step.status = ExecutionStatus.FAILED
                    step.error = event.error
                    yield StepFailedEvent(step=step, plan=self.plan)
                    return

                if isinstance(event, PauseEvent):
                    yield event
                    return

                if isinstance(event, MessageEvent):
                    step.status = ExecutionStatus.COMPLETED
                    step.result = event.message
                    yield StepCompletedEvent(step=step, plan=self.plan)
                
                # 只转发 ReportEvent，但转换为更简洁的消息
                if isinstance(event, ReportEvent):
                    yield MessageEvent(message=f"✅ {step.description} - 完成")
                # 完全过滤掉实现细节：ToolCallingEvent, ToolCalledEvent, MessageEvent, 
                # PlanCreatedEvent, PlanUpdatedEvent, PlanCompletedEvent, DoneEvent
                # ErrorEvent 和 PauseEvent 已在上面单独处理

        except Exception as e:

            step.status = ExecutionStatus.FAILED
            step.error = str(e)
            yield StepFailedEvent(step=step, plan=self.plan)
            return

        step.status = ExecutionStatus.COMPLETED


    def _build_parallel_execution_groups(self) -> Optional[deque]:
        # Concurrent Execution Groups
        self.parallel_sub_flow_groups = []
        prev_step = -1
        for i in range(len(self.plan.steps)):
            step = self.plan.steps[i]
            try:
                # 0. 跳过已完成或失败的步骤
                if step.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
                    self.super_flow_logger.debug(
                        f"跳过已完成/失败的步骤 {step.id}: {step.description} (状态: {step.status})")
                    continue

                # 1. 安全地处理 subplan_step 转换
                if not step.sub_plan_step:
                    self.super_flow_logger.error(f"步骤 {step.id} 缺少 subplan_step 属性")
                    step.status = ExecutionStatus.FAILED
                    step.error = "Missing subplan_step attribute"
                    continue

                try:
                    cur_step = int(step.sub_plan_step)
                except ValueError:
                    self.super_flow_logger.error(
                        f"步骤 {step.id} 的 subplan_step 值 '{step.sub_plan_step}' 无法转换为整数")
                    step.status = ExecutionStatus.FAILED
                    step.error = f"Invalid subplan_step value: {step.sub_plan_step}"
                    continue

                # 2. 检查步骤顺序
                if cur_step < prev_step:
                    error_msg = f"步骤顺序错误：当前步骤 {step.id} (subplan_step={cur_step}) 小于前一步骤 (subplan_step={prev_step})"
                    self.super_flow_logger.error(error_msg)
                    step.status = ExecutionStatus.FAILED
                    step.error = error_msg
                    continue

                # 3. 正常的步骤处理逻辑
                if cur_step > prev_step:
                    # case 1: this step is a new step
                    self.parallel_sub_flow_groups.append([step])
                    prev_step = cur_step
                elif cur_step == prev_step:
                    # case 2: this step is the same step as the previous step
                    self.parallel_sub_flow_groups[-1].append(step)

            except Exception as e:
                error_msg = f"处理步骤 {step.id} 时发生错误: {str(e)}"
                self.super_flow_logger.error(error_msg)
                step.status = ExecutionStatus.FAILED
                step.error = error_msg
                continue

        self.parallel_sub_flow_groups = deque(self.parallel_sub_flow_groups)
        self.super_flow_logger.info(
            f"构建了 {len(self.parallel_sub_flow_groups)} 个执行组，共 {sum(len(group) for group in self.parallel_sub_flow_groups)} 个待执行步骤")


    async def run(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        
        self.super_flow_logger.info(f"=== Super Flow开始处理用户消息 ===")
        self.super_flow_logger.info(f"用户输入: {message}")
        step = None

        if not self.is_idle():
            # interrupt the current flow
            self.status = FlowStatus.PLANNING
            self.planner_agent.roll_back()
            self.report_agent.roll_back()
            self.super_flow_logger.debug("中断当前流程，重新开始规划")

        while True:
            if self.status == FlowStatus.IDLE:
                self.status = FlowStatus.PLANNING
                self.super_flow_logger.info(f"状态变更: IDLE -> PLANNING")

                # 通知用户开始规划
                async for event in self.notifier.notify_received_message(message):
                  
                    if not isinstance(event, MessageEvent):
                        yield event

            elif self.status == FlowStatus.PLANNING:
                # 创建计划
                self.super_flow_logger.info(f"=== Super Flow开始创建计划 ===")
             #   self.super_flow_logger.debug(f"Super Planner输入: {message}")

                async for event in self.planner_agent.create_plan(message):
                    if isinstance(event, PlanCreatedEvent):
                        self.plan = event.plan
                        self.super_flow_logger.info(f"=== 计划创建成功 ===")
                        self.super_flow_logger.debug(f"计划ID: {event.plan.id}")
                        self.super_flow_logger.info(f"计划目标: {event.plan.goal}")
                        self.super_flow_logger.debug(f"计划标题: {event.plan.title}")
                        self.super_flow_logger.debug(f"计划步骤数量: {len(event.plan.steps)}")
                        for i, step in enumerate(event.plan.steps, 1):
                            self.super_flow_logger.debug(f"步骤{i}: [{step.id}] {step.description}")
                        if event.plan.message:
                            self.super_flow_logger.info(f"计划说明: {event.plan.message}")
                    elif isinstance(event, MessageEvent):
                        self.super_flow_logger.warning(f"Planner输出MessageEvent: {event.message}")
               #     yield event

                # 创建计划完成后，准备执行步骤
                if self.plan:
                    self._build_parallel_execution_groups()
                    # 检查是否有任何步骤可以执行,如果没有进入报告阶段
                    if not self.parallel_sub_flow_groups:
                        self.super_flow_logger.info("没有剩余的待执行步骤，进入报告阶段")
                        self.status = FlowStatus.REPORTING
                        continue
                    # 状态转换到执行阶段
                    self.status = FlowStatus.EXECUTING
                    self.super_flow_logger.info(f"状态变更: PLANNING -> EXECUTING")

            elif self.status == FlowStatus.EXECUTING:
                self.plan.status = ExecutionStatus.RUNNING

                if not self.parallel_sub_flow_groups:
                    self.status = FlowStatus.REPORTING
                    self.super_flow_logger.info("状态变更: EXECUTING -> REPORTING")
                    continue
                # 并发处理
                current_parallel_group = self.parallel_sub_flow_groups[0]  # 只查看，不弹出
                self.super_flow_logger.info(f"=== 开始执行步骤组（{len(current_parallel_group)}个步骤） ===")
                # 添加顺序执行逻辑
                if current_parallel_group:  # 确保当前组还有步骤
                    step = current_parallel_group.pop(0)  # 取出第一个步骤

                    self.knowledge.add_message({
                        'role': "user",
                        'content': step.description
                    })

                    async for execute_event in self.execute_step(step=step):
                        yield execute_event  # 传播 execute_step 内部过滤后的事件
                        self.super_flow_logger.debug(f"执行事件类型: {type(execute_event).__name__}")

                        if isinstance(execute_event, AgentEvent):
                            event_type = type(execute_event).__name__
                            self.super_flow_logger.debug("=" * 50)
                            self.super_flow_logger.debug(f">>> 执行事件类型: {event_type} <<<")
                            self.super_flow_logger.debug("=" * 50)

                    self.knowledge.add_message({
                        'role': "assistant",
                        'content': step.result
                    })

                    self.knowledge.add_file(step.file)
                    self.knowledge.add_web(step.web)

                    # 每个步骤执行完后立即进入更新状态
                    self.status = FlowStatus.UPDATING
                    self.super_flow_logger.info(f"步骤 {step.id} 执行完成，状态变更: EXECUTING -> UPDATING")
                
                # 并发处理，如果当前组为空，移除它
                if not current_parallel_group:
                    self.parallel_sub_flow_groups.popleft()  # 安全地移除空组

            elif self.status == FlowStatus.UPDATING:
                if self.plan.status == ExecutionStatus.PAUSED:
                    break
                # 更新计划
                logger.info(f"Agent {self.agent.id} started updating plan")
                self.super_flow_logger.info(f"=== 开始更新计划 ===")
                async for event in self.planner_agent.update_plan(plan=self.plan, step=step):
                    if isinstance(event, PlanUpdatedEvent):
                        self._show_plan(event.plan)
                        self.super_flow_logger.info(f"=== 计划更新完成 ===")
                        self.super_flow_logger.info(f"更新后步骤数量: {len(event.plan.steps)}")
                        for i, step in enumerate(event.plan.steps, 1):
                            status_info = f" (状态: {step.status})" if step.status != ExecutionStatus.PENDING else ""
                            self.super_flow_logger.info(f"步骤{i}: [{step.id}] {step.description}{status_info}")
                        # 发送简洁的计划更新通知
                        yield MessageEvent(message=f"🔄 计划已更新，当前剩余{len([s for s in event.plan.steps if s.status == ExecutionStatus.PENDING])}个待执行步骤")
                    elif isinstance(event, MessageEvent):
                        self.super_flow_logger.info(f"计划更新输出: {event.message}")
                        # 不转发JSON格式的MessageEvent
                    elif isinstance(event, PauseEvent):
                        self.plan.status = ExecutionStatus.COMPLETED
                        self.super_flow_logger.info(f"状态变更: UPDATING -> COMPLETED")
                        # 转发重要的状态变化事件
                        yield event

                    # 创建计划完成后，准备执行步骤
                    if self.plan:
                        self._build_parallel_execution_groups()

                        # 检查是否有任何步骤可以执行,如果没有进入报告阶段
                        if not self.parallel_sub_flow_groups:
                            self.super_flow_logger.info("没有剩余的待执行步骤，进入报告阶段")
                            self.status = FlowStatus.REPORTING
                            continue
                        # 状态转换到执行阶段
                        self.status = FlowStatus.EXECUTING
                        self.super_flow_logger.info(f"状态变更: UPDATING -> EXECUTING")

            elif self.status == FlowStatus.REPORTING:
                logger.info(f"Agent {self.agent.id} plan has been completed")
                self.super_flow_logger.info(f"=== 正在准备最终报告 ===")
                
                # 发送简洁的完成通知
                yield MessageEvent(message="所有步骤已完成，正在生成最终报告...")

                # 生成最终报告
                async for event in self.report_agent.generate_report(plan=self.plan):
                    yield event

                self.status = FlowStatus.COMPLETED
                self.super_flow_logger.info(f"状态变更: REPORTING -> COMPLETED")

            elif self.status == FlowStatus.COMPLETED:
                self.plan.status = ExecutionStatus.COMPLETED
                self.super_flow_logger.info(f"=== 计划执行完成 ===")
                self.super_flow_logger.info(f"最终计划状态: {self.plan.status}")
                yield PlanCompletedEvent(plan=self.plan, issuperplan=True)
                self.status = FlowStatus.IDLE
                self.super_flow_logger.info(f"状态变更: COMPLETED -> IDLE")
                break
        yield DoneEvent()

        logger.info(f"Agent {self.agent.id} message processing completed")
        self.super_flow_logger.info(f"=== 消息处理完成 ===")

    def is_idle(self) -> bool:
        return self.status == FlowStatus.IDLE

    def _show_plan(self, plan: Plan):
        logger.info("-" * 30)
        logger.info(f"Plan ID: {plan.id}")
        logger.info(f"Plan Goal: {plan.goal}")
        for step in plan.steps:
            logger.info(
                f"[{step.id}] {step.description}, Status: {step.status}, Result: {step.result}, Error: {step.error}")
        logger.info("-" * 30)

    def add_report_to_knowledge(self, current_report):
        self.knowledge.add_message({
            'role': "assistant",
            'message': current_report
        })

    def add_step_to_knowledge(self, current_step):
        self.knowledge.add_message({
            'role': "user",
            'message': current_step
        })