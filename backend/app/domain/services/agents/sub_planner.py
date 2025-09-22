from typing import AsyncGenerator, Optional
from datetime import datetime
from enum import Enum
import json
import logging
from json_repair import repair_json
from app.domain.models.plan import Plan, Step, ExecutionStatus
from app.domain.services.agents.base import BaseAgent
from app.domain.models.memory import Memory
from app.domain.external.llm import LLM, AudioLLM, ImageLLM, VideoLLM, ReasonLLM
from app.domain.services.agents.execution import ExecutionAgent
from app.domain.external.sandbox import Sandbox
from app.domain.external.browser import Browser
from app.domain.external.search import SearchEngine
from app.domain.services.prompts.prompt_manager import PromptManager
from app.domain.models.event import (
    AgentEvent,
    StepCompletedEvent,
    StepFailedEvent,
    MessageEvent,
    ErrorEvent,
    StepStartedEvent,
    PauseEvent,
    ReportEvent,
    ToolCallingEvent,
    ToolCalledEvent,
    PlanCreatedEvent,
    PlanUpdatedEvent
)
from app.infrastructure.logging import setup_sub_planner_agent_logger
from app.domain.services.tools import ShellTool, BrowserTool, SearchTool, FileTool, MessageTool

logger = logging.getLogger(__name__)

# enum moved to plan.py
class SubPlannerType(Enum):
    CODE = "code"
    REASONING = "reasoning"
    SEARCH = "search"
    FILE = "file"

class SubPlannerAgent(BaseAgent):
    """
    子规划器代理类，负责执行超级规划器分配的具体任务
    根据任务类型选择合适的工具，并通过execution agent执行具体操作
    """

    system_prompt: str = None  # 初始化为 None，实际在 __init__ 里赋值
    format: Optional[str] = "json_object"

    def __init__(
        self,
        llm: LLM,
        task_type: Enum,
        # for shared memory between executors
        memory: Memory = None,
        sandbox: Optional[Sandbox] = None,
        browser: Optional[Browser] = None,
        search_engine: Optional[SearchEngine] = None,
        audio_llm: Optional[AudioLLM] = None,
        image_llm: Optional[ImageLLM] = None,
        video_llm: Optional[VideoLLM] = None,
        reason_llm: Optional[ReasonLLM] = None,
    ):
        # 设置专门的日志记录器
        self.sub_planner_agent_logger = setup_sub_planner_agent_logger(f"sub_planner_agent_{task_type.value if task_type else 'unknown'}")
        self.sub_planner_agent_logger.debug(f"=== SubPlannerAgent初始化 任务类型: {task_type.value if task_type else 'None'} ===")
        
        # 添加详细的调试日志
        self.sub_planner_agent_logger.debug(f"=== SubPlannerAgent.__init__ 开始 ===")
        self.sub_planner_agent_logger.debug(f"接收到的参数:")
        self.sub_planner_agent_logger.debug(f"  llm: {llm}")
        self.sub_planner_agent_logger.debug(f"  task_type: {task_type} (类型: {type(task_type)})")
        self.sub_planner_agent_logger.debug(f"  memory: {memory}")
        self.sub_planner_agent_logger.debug(f"  sandbox: {sandbox}")
        self.sub_planner_agent_logger.debug(f"  browser: {browser}")
        self.sub_planner_agent_logger.debug(f"  search_engine: {search_engine}")
        
        if task_type:
            self.sub_planner_agent_logger.debug(f"task_type.value: {task_type.value}")
            self.sub_planner_agent_logger.debug(f"task_type.value 类型: {type(task_type.value)}")
        
        # 根据任务类型初始化工具
        tools = []
        from app.domain.services.tools.file import FileTool
        from app.domain.services.tools.message import MessageTool
        tools.append(FileTool(sandbox))
        tools.append(MessageTool())

        if task_type.value == "code":
            from app.domain.services.tools.shell import ShellTool
            if sandbox:
                tools.append(ShellTool(sandbox))
        elif task_type.value == "search":
            from app.domain.services.tools.search import SearchTool
            from app.domain.services.tools.browser import BrowserTool
            from app.domain.services.tools.audio import AudioTool
            from app.domain.services.tools.image import ImageTool
            if search_engine:
                tools.append(SearchTool(search_engine))
            if browser:
                tools.append(BrowserTool(browser))
            if sandbox and audio_llm and llm:
                tools.append(AudioTool(sandbox, audio_llm, llm))
            if sandbox and image_llm:
                tools.append(ImageTool(sandbox, image_llm))
        elif task_type.value == "file":
            from app.domain.services.tools.image import ImageTool
            from app.domain.services.tools.audio import AudioTool
            from app.domain.services.tools.shell import ShellTool
            if sandbox and image_llm:
                tools.append(ImageTool(sandbox, image_llm))
            if sandbox and audio_llm and llm:
                tools.append(AudioTool(sandbox, audio_llm, llm))
            if sandbox:
                tools.append(ShellTool(sandbox))
        elif task_type.value == "reasoning":
            from app.domain.services.tools.reasoning import DeepReasoningTool
            from app.domain.services.tools.shell import ShellTool
            if reason_llm:
                tools.append(DeepReasoningTool(reason_llm))
            if sandbox:
                tools.append(ShellTool(sandbox))
        self.sub_planner_agent_logger.debug(f"工具初始化完成，共{len(tools)}个工具")
        for i, tool in enumerate(tools):
            self.sub_planner_agent_logger.debug(f"工具{i+1}: {type(tool).__name__}")

        # 设置可用工具列表（动态）
        self.tools = tools
        self._setup_tools()
        self.sub_planner_agent_logger.debug(f"可用工具列表: {self.available_tools}")
        
        # 生成系统提示词
        self.sub_planner_agent_logger.debug(f"=== 开始生成系统提示词 ===")
        try:
            self.system_prompt = PromptManager.get_subplanner_prompt(task_type).format(cur_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.sub_planner_agent_logger.debug(f"系统提示词生成成功")
            self.sub_planner_agent_logger.debug(f"系统提示词长度: {len(self.system_prompt)}")
        except Exception as e:
            self.sub_planner_agent_logger.error(f"生成系统提示词失败: {str(e)}")
            self.sub_planner_agent_logger.error(f"错误类型: {type(e)}")
            import traceback
            self.sub_planner_agent_logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise
        
        # 调用父类构造函数
      #  self.sub_planner_agent_logger.info(f"=== 开始调用父类构造函数 ===")
        try:
            super().__init__(
                memory=memory,
                llm=llm,
                tools=tools
            )
         #   self.sub_planner_agent_logger.info(f"父类构造函数调用成功")
        except Exception as e:
            self.sub_planner_agent_logger.error(f"调用父类构造函数失败: {str(e)}")
            self.sub_planner_agent_logger.error(f"错误类型: {type(e)}")
            import traceback
            self.sub_planner_agent_logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise
        
        # 存储额外的参数作为实例变量
        self.sandbox = sandbox
        self.browser = browser
        self.search_engine = search_engine
        self.audio_llm = audio_llm
        self.image_llm = image_llm
        self.video_llm = video_llm
        self.reason_llm = reason_llm
        
        # 设置其他属性
        self.task_type = task_type
        self.task_description = ''
        self.goal = ''

        self.sub_planner_agent_logger.info(f"=== SubPlannerAgent初始化完成 ===")
    #    self.sub_planner_agent_logger.info(f"任务类型: {self.task_type.value}")
    #    self.sub_planner_agent_logger.info(f"可用工具: {self.available_tools}")
        
        self.execution_result = None
        self.status = ExecutionStatus.PENDING

        # 创建execution agent用于执行具体操作，共享memory
        self.executor = ExecutionAgent(
            memory=Memory(), # executors share memory
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
        
        # 生成系统提示词 - 使用正确的方法处理工具规则
        self.sub_planner_agent_logger.debug(f"=== 开始生成系统提示词 ===")
        try:
            self.system_prompt = PromptManager.insert_datetime(PromptManager.get_system_prompt_with_tools(self.executor.tools, is_executor = False))
            self.sub_planner_agent_logger.debug(f"系统提示词生成成功")
            self.sub_planner_agent_logger.debug(f"系统提示词长度: {len(self.system_prompt)}")
        except Exception as e:
            self.sub_planner_agent_logger.error(f"生成系统提示词失败: {str(e)}")
            self.sub_planner_agent_logger.error(f"错误类型: {type(e)}")
            import traceback
            self.sub_planner_agent_logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise

    def fix(self,parent_plan: Plan, parent_step: Step):
        self.goal = parent_plan.goal
        self.task_description = parent_step.description

    def _setup_tools(self):
        """根据实际初始化的工具设置可用工具名称"""
        # 支持的工具类型与名称映射
        tool_type_map = {
            'ShellTool': 'shell',
            'BrowserTool': 'browser',
            'SearchTool': 'search',
            'FileTool': 'file',
            'MessageTool': 'message',
            'AudioTool': 'audio',
            'ImageTool': 'image',
            'DeepReasoningTool': 'reasoning',
            'VideoTool': 'video',
        }
        self.available_tools = []
        for tool in self.tools:
            tool_class = tool.__class__.__name__
            tool_name = tool_type_map.get(tool_class)
            if tool_name and tool_name not in self.available_tools:
                self.available_tools.append(tool_name)
        # 如果没有任何工具，使用默认的message工具
        if not self.available_tools:
            self.available_tools = ["message"]
        # 添加调试日志
        self.sub_planner_agent_logger.debug(f"检测到的工具: {[tool.__class__.__name__ for tool in self.tools]}")
        self.sub_planner_agent_logger.debug(f"设置的可用工具: {self.available_tools}")

    async def create_plan(self, message: Optional[str] = None) -> AsyncGenerator[AgentEvent, None]:
        """
        创建子计划，传递任务特定的参数
        """
        prompt_template = PromptManager.get_create_plan_prompt(self.task_type)

        prompt_message = prompt_template.format(
            goal=self.goal,
            task_description=self.task_description,
            task_type=self.task_type.value,
            available_tools=self.available_tools,
            user_message=message or self.task_description
        )
        
        plan = None
        while plan is None:
            async for event in self.execute(prompt_message):
                if isinstance(event, MessageEvent):
              #      self.sub_planner_agent_logger.info(event.message)
                    try:
                        good_json_string = repair_json(event.message)
                        parsed_response = json.loads(good_json_string)
                        
                        # 验证JSON结构
                        if not isinstance(parsed_response, dict):
                            self.sub_planner_agent_logger.error(f"Expected dict, got {type(parsed_response)}: {parsed_response}")
                            continue
                            
                        if "steps" not in parsed_response:
                            self.sub_planner_agent_logger.error(f"Missing 'steps' field in parsed response: {parsed_response}")
                            continue
                            
                        if not isinstance(parsed_response["steps"], list):
                            self.sub_planner_agent_logger.error(f"Expected 'steps' to be list, got {type(parsed_response['steps'])}: {parsed_response['steps']}")
                            continue
                        
                        steps = [Step(id=step["id"], description=step["description"]) 
                                for step in parsed_response["steps"] if isinstance(step, dict)]
                        plan = Plan(
                            id=f"plan_{self.task_type.value}_{len(steps)}", 
                            goal=parsed_response["goal"], 
                            title=parsed_response["title"],
                            steps=steps, 
                            message=parsed_response["message"]
                        )
                        yield PlanCreatedEvent(plan=plan, issubplan=True)
                    except json.JSONDecodeError as e:
                        self.sub_planner_agent_logger.error(f"JSON decode error: {e}, message: {event.message}")
                        continue
                    except KeyError as e:
                        self.sub_planner_agent_logger.error(f"Missing required field: {e}, parsed_response: {parsed_response}")
                        continue
                    except Exception as e:
                        self.sub_planner_agent_logger.error(f"Error parsing plan: {e}, message: {event.message}")
                        continue
                else:
                    yield event

    async def update_plan(self, plan: Plan, previous_steps: str) -> AsyncGenerator[AgentEvent, None]:
        """
        更新子计划，传递任务特定的参数
        """
        prompt_template = PromptManager.get_update_plan_prompt(self.task_type)
        prompt_message = prompt_template.format(
            goal=self.goal,
            task_type=self.task_type.value,
            #task_description=self.task_description,
            available_tools=self.available_tools,
            plan=plan.model_dump_json(include={"steps"}), 
            previous_steps=previous_steps
        )
        
        async for event in self.execute(prompt_message):
            if isinstance(event, MessageEvent):
                self.sub_planner_agent_logger.info(event.message)
                try:
                    good_json_string = repair_json(event.message)
                    parsed_response = json.loads(good_json_string)
                    
                    # 验证JSON结构
                    if not isinstance(parsed_response, dict):
                        self.sub_planner_agent_logger.error(f"Expected dict, got {type(parsed_response)}: {parsed_response}")
                        continue
                    
                    # 检测是否是其他格式的响应（如总结格式）
                    summary_fields = ["task_completion_status", "key_findings_and_results", 
                                    "tool_usage_summary", "issues_and_challenges", 
                                    "next_steps", "executive_summary"]
                    
                    is_summary_format = any(field in parsed_response for field in summary_fields)
                    
                    if is_summary_format:
                        self.sub_planner_agent_logger.warning(f"LLM returned summary format instead of plan update format. Generating fallback plan.")
                        # 生成一个默认的计划更新：保持剩余的未完成步骤
                        remaining_steps = [step for step in plan.steps if not step.is_done()]
                        new_steps = remaining_steps
                        self.sub_planner_agent_logger.info(f"Fallback plan generated with {len(new_steps)} remaining steps")
                        
                    elif "steps" not in parsed_response:
                        self.sub_planner_agent_logger.error(f"Missing 'steps' field in parsed response: {parsed_response}")
                        # 自动补充默认的 steps 字段
                        remaining_steps = [step for step in plan.steps if not step.is_done()]
                        new_steps = remaining_steps
                        self.sub_planner_agent_logger.info(f"Auto-generated fallback plan with {len(new_steps)} remaining steps due to missing 'steps' field")
                        
                    elif not isinstance(parsed_response["steps"], list):
                        self.sub_planner_agent_logger.error(f"Expected 'steps' to be list, got {type(parsed_response['steps'])}: {parsed_response['steps']}")
                        # 自动补充默认的 steps 列表
                        remaining_steps = [step for step in plan.steps if not step.is_done()]
                        new_steps = remaining_steps
                        self.sub_planner_agent_logger.info(f"Auto-generated fallback plan with {len(new_steps)} remaining steps due to invalid 'steps' format")
                        
                    else:
                        # 正常的计划更新格式，但需要检查和补充缺少的字段
                        new_steps = []
                        for step_data in parsed_response["steps"]:
                            if isinstance(step_data, dict):
                                # 自动补充缺少的字段，提供默认值
                                step_dict = {
                                    "id": step_data.get("id", f"step_{len(new_steps) + 1}"),
                                    "description": step_data.get("description", "未指定描述的步骤"),
                                    "subplan_step": step_data.get("subplan_step"),
                                    "subplanner_type": step_data.get("subplanner_type", "").lower() if step_data.get("subplanner_type") else None
                                }
                                
                                # 记录补充了哪些字段
                                missing_fields = []
                                if "id" not in step_data:
                                    missing_fields.append("id")
                                if "description" not in step_data:
                                    missing_fields.append("description")
                                    
                                if missing_fields:
                                    self.sub_planner_agent_logger.warning(f"Auto-filled missing fields for step: {missing_fields}")
                                
                                new_step = Step(
                                    id=step_dict["id"],
                                    description=step_dict["description"],
                                    sub_plan_step=step_dict["subplan_step"],
                                    sub_flow_type=step_dict["subplanner_type"]
                                )
                                new_steps.append(new_step)
                            else:
                                self.sub_planner_agent_logger.warning(f"Skipping invalid step data: {step_data}")

                    # 自动补充其他响应字段的默认值
                    if "message" not in parsed_response:
                        parsed_response["message"] = "计划已更新"
                        self.sub_planner_agent_logger.info("Auto-filled missing 'message' field")
                    
                    if "goal" not in parsed_response:
                        parsed_response["goal"] = self.goal
                        self.sub_planner_agent_logger.info("Auto-filled missing 'goal' field")
                    
                    if "title" not in parsed_response:
                        parsed_response["title"] = f"更新的{self.task_type.value}子计划"
                        self.sub_planner_agent_logger.info("Auto-filled missing 'title' field")

                    # Find the index of the first pending step
                    first_pending_index = None
                    for i, step in enumerate(plan.steps):
                        if not step.is_done():
                            first_pending_index = i
                            break

                    # If there are pending steps, replace all pending steps
                    if first_pending_index is not None:
                        # Keep completed steps
                        updated_steps = plan.steps[:first_pending_index]
                        # Add new steps
                        updated_steps.extend(new_steps)
                        # Update steps in plan
                        plan.steps = updated_steps
                    else:
                        # 如果没有待处理的步骤，直接使用新步骤
                        plan.steps.extend(new_steps)

                    yield PlanUpdatedEvent(plan=plan,issubplan=True)

                    if not plan.steps:
                        yield PauseEvent()
                        
                except json.JSONDecodeError as e:
                    self.sub_planner_agent_logger.error(f"JSON decode error: {e}, message: {event.message}")
                    # 生成默认计划：保持剩余未完成的步骤
                    remaining_steps = [step for step in plan.steps if not step.is_done()]
                    
                    # Find the index of the first pending step
                    first_pending_index = None
                    for i, step in enumerate(plan.steps):
                        if not step.is_done():
                            first_pending_index = i
                            break

                    # If there are pending steps, keep them
                    if first_pending_index is not None:
                        plan.steps = plan.steps[:first_pending_index] + remaining_steps
                    
                    self.sub_planner_agent_logger.info(f"Generated fallback plan with {len(remaining_steps)} remaining steps due to JSON decode error")
                    yield PlanUpdatedEvent(plan=plan)
                    return
                except KeyError as e:
                    self.sub_planner_agent_logger.error(f"Missing required field: {e}, parsed_response: {parsed_response}")
                    continue
                except Exception as e:
                    self.sub_planner_agent_logger.error(f"Error parsing plan update: {e}, message: {event.message}")
                    continue
            
            yield event