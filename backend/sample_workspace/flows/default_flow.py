import logging
from app.domain.services.flows.base import BaseSubFlow
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
    ToolCalledEvent, ReportEvent
)
from app.domain.models.plan import ExecutionStatus, Plan, Step
from app.domain.services.agents.sub_planner import SubPlannerAgent
from app.domain.services.agents.execution import ExecutionAgent
from app.domain.services.agents.base import BaseAgent
from app.domain.external.llm import LLM, AudioLLM, ImageLLM, VideoLLM, ReasonLLM
from app.domain.external.sandbox import Sandbox
from app.domain.external.browser import Browser
from app.domain.external.search import SearchEngine
from app.infrastructure.logging import setup_sub_planner_flow_logger
from app.domain.models.memory import Memory
from app.domain.services.prompts.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class AgentStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    UPDATING = "updating"
    REPORTING = "reporting"

class DefaultFlow(BaseSubFlow):
    # 定义flow的唯一标识符
    flow_id = "default"
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
        # 设置专门的日志记录器
        self.sub_planner_flow_logger = setup_sub_planner_flow_logger(f"sub_planner_{task_type.value if task_type else 'unknown'}")
        self.sub_planner_flow_logger.info(f"=== SubPlannerFlow初始化 任务类型: {task_type.value if task_type else 'None'} ===")
        
        # 添加详细的调试日志
        #self.sub_planner_flow_logger.info(f"=== SubPlannerFlow.__init__ 开始 ===")
        # self.sub_planner_flow_logger.debug(f"接收到的参数:")
        # self.sub_planner_flow_logger.debug(f"  llm: {llm}")
        # self.sub_planner_flow_logger.debug(f"  sandbox: {sandbox}")
        # self.sub_planner_flow_logger.debug(f"  browser: {browser}")
        # self.sub_planner_flow_logger.debug(f"  search_engine: {search_engine}")
        # self.sub_planner_flow_logger.debug(f"  task_type: {task_type} (类型: {type(task_type)})")
        self.execution_result=Memory()
        if task_type:
            self.sub_planner_flow_logger.debug(f"task_type.value: {task_type.value}")
      #      self.sub_planner_flow_logger.debug(f"task_type.value 类型: {type(task_type.value)}")
        
        # 调用父类构造函数
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
        self.plan = None
        
        self.sub_planner_flow_logger.info(f"=== 开始创建SubPlannerAgent ===")
        
        try:
            # 创建子规划器代理
            self.sub_planner_flow_logger.debug(f"准备创建SubPlannerAgent，参数:")
            self.sub_planner_flow_logger.debug(f"  llm: {llm}")
            self.sub_planner_flow_logger.debug(f"  task_type: {task_type} (类型: {type(task_type)})")
            self.sub_planner_flow_logger.debug(f"  sandbox: {sandbox}")
            self.sub_planner_flow_logger.debug(f"  browser: {browser}")
            self.sub_planner_flow_logger.debug(f"  search_engine: {search_engine}")
            
            self.sub_planner = SubPlannerAgent(
                llm=llm,
                task_type=task_type,
                memory=Memory(),
                sandbox=sandbox,
                browser=browser,
                search_engine=search_engine,
                audio_llm=audio_llm,
                image_llm=image_llm,
                video_llm=video_llm,
                reason_llm=reason_llm,
            )
            self.sub_planner_flow_logger.info("创建SubPlanner Agent完成")
        except Exception as e:
            self.sub_planner_flow_logger.error(f"创建SubPlannerAgent失败: {str(e)}")
            self.sub_planner_flow_logger.error(f"错误类型: {type(e)}")
            import traceback
            self.sub_planner_flow_logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise
        
        try:
            self.sub_planner_flow_logger.info(f"=== 开始创建ExecutionAgent ===")
            # 创建执行代理
            self.executor = ExecutionAgent(
                memory=Memory(),
                llm=llm,
                sandbox=sandbox,
                browser=browser,
                search_engine=search_engine,
                audio_llm=audio_llm,
                image_llm=image_llm,
                video_llm=video_llm,
                reason_llm=reason_llm,
                type_value=task_type.value
            )
            self.sub_planner_flow_logger.info("创建Execution Agent完成")
        except Exception as e:
            self.sub_planner_flow_logger.error(f"创建ExecutionAgent失败: {str(e)}")
            self.sub_planner_flow_logger.error(f"错误类型: {type(e)}")
            import traceback
            self.sub_planner_flow_logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise

    async def run(
        self,
        parent_plan: Plan,
        parent_step: Step,
        parent_memory: Memory,
        task_type: Enum
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        执行子计划流程
        
        Args:
            parent_plan: 父规划器当前的计划
            parent_step: 要执行的步骤
            parent_memory: 父规划器当前的记忆
            task_type: 当前步骤的任务类型
        """
        # TODO
        self.sub_planner.fix(parent_plan,parent_step)

        self.sub_planner_flow_logger.info(f"=== 开始执行子计划 ===")
        self.sub_planner_flow_logger.debug(f"父计划ID: {parent_plan.id}")
        self.sub_planner_flow_logger.debug(f"父步骤ID: {parent_step.id}")
        self.sub_planner_flow_logger.debug(f"任务类型: {task_type.value}")
        
        # 根据传入的task_type更新提示词
        self.sub_planner_flow_logger.debug(f"=== 开始更新系统提示词 ===")
        try:
            # 更新子规划器的系统提示词
            updated_system_prompt = PromptManager.get_system_prompt_with_tools(self.sub_planner.tools, is_executor=False)
            self.sub_planner_flow_logger.debug(f"[DEBUG MEM] SubPlannerFlow before update mem: {updated_system_prompt}")
            updated_system_prompt = PromptManager.update_mem(updated_system_prompt, parent_memory)
            self.sub_planner_flow_logger.debug(f"[DEBUG MEM] SubPlannerFlow after update mem: {updated_system_prompt}")
            updated_system_prompt = PromptManager.insert_datetime(updated_system_prompt)
            if hasattr(self.sub_planner, 'system_prompt'):
                self.sub_planner.system_prompt = updated_system_prompt
                self.sub_planner_flow_logger.debug(f"子规划器系统提示词更新成功")
                self.sub_planner_flow_logger.debug(f"新提示词长度: {len(updated_system_prompt)}")
            else:
                self.sub_planner_flow_logger.warning(f"子规划器没有system_prompt属性")
                
            # 更新执行器的系统提示词
            executor_system_prompt = PromptManager.insert_datetime(PromptManager.get_system_prompt_with_tools(self.executor.tools, is_executor=True))
            if hasattr(self.executor, 'system_prompt'):
                self.executor.system_prompt = executor_system_prompt
                self.sub_planner_flow_logger.debug(f"执行器系统提示词更新成功")
                self.sub_planner_flow_logger.debug(f"执行器新提示词长度: {len(executor_system_prompt)}")
            else:
                self.sub_planner_flow_logger.warning(f"执行器没有system_prompt属性")
                
        except Exception as e:
            self.sub_planner_flow_logger.error(f"更新系统提示词失败: {str(e)}")
            self.sub_planner_flow_logger.error(f"错误类型: {type(e)}")
            import traceback
            self.sub_planner_flow_logger.error(f"错误堆栈: {traceback.format_exc()}")
            # 继续执行，不因为提示词更新失败而中断整个流程
        
        if not self.is_idle():
            # interrupt the current flow
            self.status = AgentStatus.PLANNING
            self.sub_planner.roll_back()
            self.executor.roll_back()
            self.sub_planner_flow_logger.debug("中断当前流程，重新开始规划")

        # 使用父步骤的描述作为输入消息
        message = parent_step.description
        logger.info(f"开始处理步骤: {message[:50]}...")
        
        # 创建子计划
        self.status = AgentStatus.PLANNING
        self.sub_planner_flow_logger.info(f"状态变更: IDLE -> PLANNING")
        
        async for event in self.sub_planner.create_plan(message):
            if isinstance(event, PlanCreatedEvent):
                self.plan = event.plan
                logger.info(f"创建子计划成功，包含 {len(event.plan.steps)} 个步骤")
                self.sub_planner_flow_logger.info(f"=== 子计划创建成功 ===")
                self.sub_planner_flow_logger.debug(f"子计划ID: {event.plan.id}")
                self.sub_planner_flow_logger.info(f"子计划目标: {event.plan.goal}")
                self.sub_planner_flow_logger.debug(f"子计划标题: {event.plan.title}")
                self.sub_planner_flow_logger.debug(f"子计划步骤数量: {len(event.plan.steps)}")
                for i, step in enumerate(event.plan.steps, 1):
                    self.sub_planner_flow_logger.debug(f"步骤{i}: [{step.id}] {step.description}")
                if event.plan.message:
                    self.sub_planner_flow_logger.debug(f"子计划说明: {event.plan.message}")
            elif isinstance(event, MessageEvent):
                self.sub_planner_flow_logger.info(f"Planner输出: {event.message}")
            #yield event
            
        self.status = AgentStatus.EXECUTING
        self.sub_planner_flow_logger.info(f"状态变更: PLANNING -> EXECUTING")
        
        # 执行子计划
        while True:
            if self.status == AgentStatus.EXECUTING:
                # 执行计划
                self.plan.status = ExecutionStatus.RUNNING
                step = self.plan.get_next_step()
                if not step:
                    logger.info(f"子计划执行完成，状态变更: EXECUTING -> REPORTING")
                    self.status = AgentStatus.REPORTING
                    self.sub_planner_flow_logger.info(f"所有步骤执行完成，状态变更: EXECUTING -> REPORTING")
                    continue
                    
                # 执行步骤
                logger.info(f"开始执行步骤 {step.id}: {step.description[:50]}...")
                self.sub_planner_flow_logger.info(f"=== 开始执行步骤 ===")
                self.sub_planner_flow_logger.debug(f"步骤ID: {step.id}")
                self.sub_planner_flow_logger.debug(f"步骤描述: {step.description}")
                self.sub_planner_flow_logger.debug(f"Executor输入: 目标={self.plan.goal}, 步骤={step.description}")
                
                async for event in self.executor.execute_step(self.plan, step, message):
                    if isinstance(event, ToolCallingEvent):
                        self.sub_planner_flow_logger.debug(f"工具调用: {event.tool_name}")
                        self.sub_planner_flow_logger.debug(f"工具函数: {event.function_name}")
                        self.sub_planner_flow_logger.debug(f"工具参数: {event.function_args}")
                    elif isinstance(event, ToolCalledEvent):
                        self.sub_planner_flow_logger.debug(f"工具结果: {event.tool_name}")
                        self.sub_planner_flow_logger.debug(f"工具函数: {event.function_name}")
                        self.sub_planner_flow_logger.debug(f"工具输出: {event.function_result}")
                        if hasattr(event, 'error') and event.error:
                            self.sub_planner_flow_logger.error(f"工具错误: {event.error}")
                    elif isinstance(event, MessageEvent):
                        self.sub_planner_flow_logger.debug(f"Executor输出: {event.message}")
                        # 将执行结果保存到execution_result中
                        self.execution_result.add_message({
                            "role": "assistant",
                            "content": event.message
                        })
                #    yield event
                        
                logger.info(f"步骤 {step.id} 执行完成，状态变更: EXECUTING -> UPDATING")
                self.sub_planner_flow_logger.debug(f"步骤执行完成: {step.id}")
                self.sub_planner_flow_logger.debug(f"步骤状态: {step.status}")
                if step.result:
                    self.sub_planner_flow_logger.info(f"步骤结果: {step.result}")
                if step.error:
                    self.sub_planner_flow_logger.error(f"步骤错误: {step.error}")
                self.status = AgentStatus.UPDATING
                self.sub_planner_flow_logger.info(f"状态变更: EXECUTING -> UPDATING")
                
            elif self.status == AgentStatus.UPDATING:
                if self.plan.status == ExecutionStatus.PAUSED:
                    break
                    
                # 执行Agent总结所作所为
                self.sub_planner_flow_logger.info(f"=== 开始总结步骤 ===")
                previous_steps = ""
                async for event in self.executor.summarize_steps():
                    # 不转发总结事件到前端，这些是内部实现细节
                    # yield event
                    if isinstance(event, MessageEvent):
                        previous_steps = event.message
                        # 将总结保存到execution_result中
                        self.execution_result.add_message({
                            "role": "assistant",
                            "content": event.message
                        })
                        
                # 更新计划
                self.sub_planner_flow_logger.info(f"=== 开始更新子计划 ===")
                self.sub_planner_flow_logger.info(f"计划更新输入 - 当前计划: {self.plan.model_dump_json(include={'steps'})}")
                self.sub_planner_flow_logger.info(f"计划更新输入 - 目标: {self.plan.goal}")
                self.sub_planner_flow_logger.info(f"计划更新输入 - 已完成步骤总结: {previous_steps}")
                
                async for event in self.sub_planner.update_plan(self.plan, previous_steps):
                    if isinstance(event, PlanUpdatedEvent):
                        self._show_plan(event.plan)
                        self.sub_planner_flow_logger.info(f"=== 子计划更新完成 ===")
                        self.sub_planner_flow_logger.debug(f"更新后步骤数量: {len(event.plan.steps)}")
                        for i, step in enumerate(event.plan.steps, 1):
                            status_info = f" (状态: {step.status})" if step.status != ExecutionStatus.PENDING else ""
                            self.sub_planner_flow_logger.debug(f"步骤{i}: [{step.id}] {step.description}{status_info}")
                    elif isinstance(event, MessageEvent):
                        self.sub_planner_flow_logger.info(f"计划更新输出: {event.message}")
                        # 将更新信息保存到execution_result中
                        self.execution_result.add_message({
                            "role": "assistant",
                            "content": event.message
                        })
                    elif isinstance(event, PauseEvent):
                        self.plan.status = ExecutionStatus.COMPLETED
                        self.sub_planner_flow_logger.info(f"状态变更: UPDATING -> COMPLETED")
                 #   yield event

                logger.info(f"子计划更新完成，状态变更: UPDATING -> EXECUTING")
                self.status = AgentStatus.EXECUTING
                self.sub_planner_flow_logger.info(f"状态变更: UPDATING -> EXECUTING")

            elif self.status == AgentStatus.REPORTING:
                logger.info(f"子计划执行完成，准备生成报告")
                self.sub_planner_flow_logger.info(f"=== 正在准备最终报告 ===")
                
                final_report = ""
                async for event in self.executor.report_result(message):
                    if isinstance(event, MessageEvent):
                        # 将报告保存到execution_result中
                        parent_step.result = event.message
                        final_report = event.message  # 只保留最终报告
                 #   yield event
                yield ReportEvent(message=str(self.execution_result.get_messages()))
                # # 只发送简洁的最终报告，而不是整个执行历史
                # yield ReportEvent(message=final_report or parent_step.result or "子任务执行完成")
                self.status = AgentStatus.COMPLETED
                self.sub_planner_flow_logger.info(f"状态变更: REPORTING -> COMPLETED")
                
            elif self.status == AgentStatus.COMPLETED:
                self.plan.status = ExecutionStatus.COMPLETED
                logger.info(f"子计划执行完成")
                self.sub_planner_flow_logger.info(f"=== 子计划执行完成 ===")
                self.sub_planner_flow_logger.info(f"最终计划状态: {self.plan.status}")
                    
                yield PlanCompletedEvent(plan=self.plan, issubplan=True) 
                self.status = AgentStatus.IDLE
                self.sub_planner_flow_logger.info(f"状态变更: COMPLETED -> IDLE")
                break
                
        #yield DoneEvent()
        """需要声明另一种doneevent"""
        
        logger.info(f"子计划处理完成")
        self.sub_planner_flow_logger.info(f"=== 子计划处理完成 ===")
    
    def is_idle(self) -> bool:
        return self.status == AgentStatus.IDLE
    
    def _show_plan(self, plan: Plan):
        logger.info("-" * 30)
        logger.info(f"Plan ID: {plan.id}")
        logger.info(f"Plan Goal: {plan.goal}")
        for step in plan.steps:
            logger.info(f"[{step.id}] {step.description}, Status: {step.status}, Result: {step.result}, Error: {step.error}")
        logger.info("-" * 30)
