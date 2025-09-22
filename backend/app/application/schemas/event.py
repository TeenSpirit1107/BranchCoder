from pydantic import BaseModel, Field
from typing import Any, Union, Literal, Dict, Optional, List
import time
from app.domain.models.plan import ExecutionStatus


class BaseData(BaseModel):
    timestamp: int = Field(default_factory=lambda: int(time.time()))

class MessageData(BaseData):
    content: str

class ToolData(BaseData):
    name: str
    function: str
    args: Dict[str, Any]
    result: Optional[Any] = None
    status: Literal["calling", "called"]

class StepData(BaseData):
    status: ExecutionStatus
    id: str
    description: str


class PlanData(BaseData):
    steps: List[StepData]
    issuperplan: bool = False
    issubplan: bool = False

class ErrorData(BaseData):
    error: str

class TitleData(BaseData):
    title: str

class UserInputData(BaseData):
    content: str
    file_ids: List[str]

class SSEEvent(BaseModel):
    event: str
    data: Optional[Union[str, BaseData]]

class MessageSSEEvent(SSEEvent):
    event: Literal["message"] = "message"
    data: MessageData

class ToolSSEEvent(SSEEvent):
    event: Literal["tool"] = "tool"
    data: ToolData

class DoneSSEEvent(SSEEvent):
    event: Literal["done"] = "done"
    data: BaseData

class ErrorSSEEvent(SSEEvent):
    event: Literal["error"] = "error"
    data: ErrorData

class StepSSEEvent(SSEEvent):
    event: Literal["step"] = "step"
    data: StepData

class TitleSSEEvent(SSEEvent):
    event: Literal["title"] = "title"
    data: TitleData

class PlanSSEEvent(SSEEvent):
    event: Literal["plan"] = "plan"
    data: PlanData

class UserInputSSEEvent(SSEEvent):
    event: Literal["user_input"] = "user_input"
    data: UserInputData

