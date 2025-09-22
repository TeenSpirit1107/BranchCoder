from typing import AsyncGenerator, Optional
from datetime import datetime
import json
from json_repair import repair_json

from app.domain.models.plan import Plan, Step
from app.domain.services.agents.base import BaseAgent
from app.domain.models.memory import Memory
from app.domain.external.llm import LLM
from app.domain.services.prompts.super_planner_prompt import (
    PLANNER_SYSTEM_PROMPT,
    CREATE_PLAN_PROMPT,
    UPDATE_PLAN_PROMPT,
    REPORT_SYSTEM_PROMPT,
    REPORT_PROMPT,
)
from app.domain.models.event import (
    AgentEvent,
    PlanCreatedEvent,
    PlanUpdatedEvent,
    MessageEvent,
    PauseEvent,
    ErrorEvent, ReportEvent
)
from app.infrastructure.logging import setup_super_planner_agent_logger

logger = setup_super_planner_agent_logger("super_planner")

class PlannerAgent(BaseAgent):
    """
    Planner agent class, defining the basic behavior of planning
    """
    def __init__(
            self,
            memory: Memory,
            llm: LLM,
            knowledge: Memory,
    ):
        super().__init__(memory, llm, [])
        self.max_iterations = 3
        self.knowledge = knowledge

    system_prompt: str = PLANNER_SYSTEM_PROMPT.format(cur_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    async def create_plan(self, message: Optional[str] = None) -> AsyncGenerator[AgentEvent, None]:
        message = CREATE_PLAN_PROMPT.format(user_message=message) if message else None

        plan = None
        while plan is None:
            async for event in self.execute(message):
                if isinstance(event, MessageEvent):
                    logger.info(event.message)
                    parsed_response = []
                    try:
                        good_json_string = repair_json(event.message)
                        parsed_response = json.loads(good_json_string)

                        # 验证JSON结构
                        if not isinstance(parsed_response, dict):
                            logger.error(f"Expected dict, got {type(parsed_response)}: {parsed_response}")
                            continue
                        if "steps" not in parsed_response:
                            logger.error(f"Missing 'steps' field in parsed response: {parsed_response}")
                            continue
                        if not isinstance(parsed_response["steps"], list):
                            logger.error(f"Expected 'steps' to be list, got {type(parsed_response['steps'])}: {parsed_response['steps']}")
                            continue

                        steps = [Step(
                            id=step["id"], 
                            description=step["description"],
                            sub_plan_step=step.get("sub_flow_step"),
                            sub_flow_type=step.get("sub_flow_type", "").lower() if step.get("sub_flow_type") else None
                        ) for step in parsed_response["steps"] if isinstance(step, dict)]
                        
                        plan = Plan(id=f"plan_{len(steps)}", goal=parsed_response["goal"], title=parsed_response["title"],
                                    steps=steps, message=parsed_response["message"])
                        yield PlanCreatedEvent(plan=plan, issuperplan=True)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {e}, message: {event.message}")
                        continue
                    except KeyError as e:
                        logger.error(f"Missing required field: {e}, parsed_response: {parsed_response}")
                        continue
                    except Exception as e:
                        logger.error(f"Error parsing plan: {e}, message: {event.message}")
                        continue
                else:
                    yield event


    async def update_plan(self, plan: Plan, step: Step) -> AsyncGenerator[AgentEvent, None]:
        
        message = UPDATE_PLAN_PROMPT.format(
            step_description=step.description,
            report=step.result,
        )

        async for event in self.execute(message):
            parsed_response = None
            if isinstance(event, MessageEvent):
                logger.info(event.message)
                try:
                    good_json_string = repair_json(event.message)
                    parsed_response = json.loads(good_json_string)

                    # 验证JSON结构
                    if not isinstance(parsed_response, dict):
                        logger.error(f"Expected dict, got {type(parsed_response)}: {parsed_response}")
                        continue
                    if "steps" not in parsed_response:
                        logger.error(f"Missing 'steps' field in parsed response: {parsed_response}")
                        continue
                    if not isinstance(parsed_response["steps"], list):
                        logger.error(f"Expected 'steps' to be list, got {type(parsed_response['steps'])}: {parsed_response['steps']}")
                        continue
                        
                    new_steps = [Step(id=step["id"],
                                      description=step["description"],
                                      sub_plan_step=step.get("sub_flow_step"),
                                      sub_flow_type=step.get("sub_flow_type", "").lower() if step.get("sub_flow_type") else None
                                      ) for step in parsed_response["steps"] if isinstance(step, dict)]

                    # Find the index of the first pending step
                    first_pending_index = None
                    for i, step in enumerate(plan.steps):
                        if not step.is_done():
                            first_pending_index = i
                            break

                    updated_steps = []
                    # If there are pending steps, replace all pending steps
                    if first_pending_index is not None:
                        # Keep completed steps
                        updated_steps = plan.steps[:first_pending_index]
                    # Add new steps
                    updated_steps.extend(new_steps)
                    # Update steps in plan
                    plan.steps = updated_steps

                    yield PlanUpdatedEvent(plan=plan, issuperplan=True)

                    if not plan.steps:
                        yield PauseEvent()
                    # 更新计划之后直接结束update_plan
                    return
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}, message: {event.message}")
                    continue
                except KeyError as e:
                    logger.error(f"Missing required field: {e}, parsed_response: {parsed_response}")
                    continue
                except Exception as e:
                    logger.error(f"Error parsing plan update: {e}, message: {event.message}")
                    continue
            else:
                yield event

class ReportAgent(BaseAgent):
    """
    Planner agent class, defining the basic behavior of planning
    """

    def __init__(
            self,
            memory: Memory,
            llm: LLM,
            knowledge: Memory,
    ):
        super().__init__(memory, llm, [])
        self.max_iterations = 3
        self.knowledge = knowledge

    system_prompt: str = REPORT_SYSTEM_PROMPT.format(cur_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    async def generate_report(self, plan: Plan) -> AsyncGenerator[AgentEvent, None]:
        """
        总结任务执行情况
        包括工具使用情况和执行结果
        """
        if not self.knowledge:
            yield ErrorEvent(error="No knowledge available for generating report.")
            return

        message = REPORT_PROMPT.format(
            goal = plan.goal,
            memory = self.knowledge.get_messages(),
        )

        async for event in BaseAgent.execute(self, message):
            if isinstance(event, MessageEvent):
                yield ReportEvent(message=event.message)