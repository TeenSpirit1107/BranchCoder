from pydantic import BaseModel
from typing import Any, Optional

class ToolResult(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
