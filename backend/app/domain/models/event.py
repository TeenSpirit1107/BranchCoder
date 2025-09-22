from pydantic import BaseModel
from typing import Dict, Any, Literal
import logging
from app.domain.models.plan import Plan, Step


class AgentEvent(BaseModel):
    """Base class for agent events"""
    type: str

class ErrorEvent(AgentEvent):
    """Error event"""
    type: Literal["error"] = "error"
    error: str

class PauseEvent(AgentEvent):
    """Pause event"""
    type: Literal["pause"] = "pause"

class PlanCreatedEvent(AgentEvent):
    """Plan creation completed event"""
    type: Literal["plan_created"] = "plan_created"
    plan: Plan
    issuperplan: bool = False
    issubplan: bool = False

class PlanUpdatedEvent(AgentEvent):
    """Plan update completed event"""
    type: Literal["plan_updated"] = "plan_updated"
    plan: Plan
    issuperplan: bool = False
    issubplan: bool = False

class ToolCallingEvent(AgentEvent):
    """Tool calling event (before execution)"""
    type: Literal["tool_calling"] = "tool_calling"
    tool_name: str
    function_name: str
    function_args: Dict[str, Any]

class ToolCalledEvent(AgentEvent):
    """Tool called event (after execution)"""
    type: Literal["tool_called"] = "tool_called"
    tool_name: str
    function_name: str
    function_args: Dict[str, Any]
    function_result: Any

class StepStartedEvent(AgentEvent):
    """Step started event"""
    type: Literal["step_started"] = "step_started"
    step: Step
    plan: Plan

class StepFailedEvent(AgentEvent):
    """Step execution failed event"""
    type: Literal["step_failed"] = "step_failed"
    step: Step
    plan: Plan

class StepCompletedEvent(AgentEvent):
    """Step execution completed event"""
    type: Literal["step_completed"] = "step_completed"
    step: Step
    plan: Plan

class PlanCompletedEvent(AgentEvent):
    """Plan execution completed event"""
    type: Literal["plan_completed"] = "plan_completed"
    plan: Plan
    issuperplan: bool = False
    issubplan: bool = False

class MessageEvent(AgentEvent):
    """Message event"""
    type: Literal["message"] = "message"
    message: str

class ReportEvent(AgentEvent):
    """Report event"""
    type: Literal["report"] = "report"
    message: str

class UserInputEvent(AgentEvent):
    """User input event"""
    type: Literal["user_input"] = "user_input"
    message: str
    file_ids: list[str]

class DoneEvent(AgentEvent):
    """Done event"""
    type: Literal["done"] = "done"
