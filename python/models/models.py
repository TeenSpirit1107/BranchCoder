from abc import ABC
from dataclasses import dataclass

@dataclass
class BaseEvent(ABC):
    type: str
    message: str = ""

@dataclass
class ToolCallEvent(BaseEvent):
    type: str = "tool_call"
    tool_name: str = ""
    tool_args: dict = None

@dataclass
class ToolResultEvent(BaseEvent):
    type: str = "tool_result"
    tool_name: str = ""
    result: dict = None

@dataclass
class MessageEvent(BaseEvent):
    type: str = "notification_message"

@dataclass
class ReportEvent(BaseEvent):
    type: str = "final_message"
