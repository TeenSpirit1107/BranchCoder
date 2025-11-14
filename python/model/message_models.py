#!/usr/bin/env python3
"""
Message models for flow agent output
All messages yielded by flow_agent.process() should use these models.
"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class FlowMessage:
    """Base class for all flow agent messages."""
    type: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        return asdict(self)


@dataclass
class StatusMessage(FlowMessage):
    """Status update message during processing."""
    type: str = "status"
    content: str = ""
    
    def __post_init__(self):
        """Ensure type is set correctly."""
        self.type = "status"


@dataclass
class ToolCallMessage(FlowMessage):
    """Tool call notification message."""
    type: str = "tool_call"
    tool_name: str = ""
    content: str = ""
    
    def __post_init__(self):
        """Ensure type is set correctly."""
        self.type = "tool_call"


@dataclass
class ToolResultMessage(FlowMessage):
    """Tool execution result notification message."""
    type: str = "tool_result"
    tool_name: str = ""
    content: str = ""
    
    def __post_init__(self):
        """Ensure type is set correctly."""
        self.type = "tool_result"


@dataclass
class FinalMessage(FlowMessage):
    """Final message to send to frontend."""
    type: str = "message"
    content: str = ""
    
    def __post_init__(self):
        """Ensure type is set correctly."""
        self.type = "message"

