from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, AsyncGenerator

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


class BaseFlow(ABC):
    """Base interface for all flow agents"""
    
    @abstractmethod
    def __init__(self, workspace_dir: str, is_parent: bool = True):
        """
        Initialize the flow agent.
        
        Args:
            workspace_dir: Path to the workspace directory
            is_parent: Whether this agent can spawn sub-agents
        """
        pass
    
    @abstractmethod
    async def process(
        self,
        message: str,
        session_id: str,
        parent_history: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[BaseEvent, None]:
        """
        Process a user message and yield events during execution.
        
        Args:
            message: The user's input message
            session_id: Unique identifier for the session
            parent_history: Optional conversation history from parent agent
            
        Yields:
            BaseEvent: Events during processing (MessageEvent, ToolCallEvent, etc.)
        """
        pass
