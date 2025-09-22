"""Agent上下文领域模型"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

from app.domain.models.agent import Agent


@dataclass
class AgentContext:
    """Agent上下文领域模型
    
    包含Agent运行时的核心信息，但不包含运行时资源（如队列、任务等）
    """
    agent_id: str
    agent: Agent
    flow_id: str
    sandbox_id: Optional[str] = None
    status: str = "created"  # created, running, stopped, error
    last_message: Optional[str] = None
    last_message_time: Optional[int] = None
    created_at: datetime = None
    updated_at: datetime = None
    meta_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
        if self.meta_data is None:
            self.meta_data = {}
    
    def update_status(self, status: str) -> None:
        """更新状态"""
        self.status = status
        self.updated_at = datetime.now()
    
    def update_last_message(self, message: str, timestamp: Optional[int] = None) -> None:
        """更新最后消息"""
        self.last_message = message
        self.last_message_time = timestamp
        self.updated_at = datetime.now()
    
    def set_sandbox_id(self, sandbox_id: str) -> None:
        """设置沙盒ID"""
        self.sandbox_id = sandbox_id
        self.updated_at = datetime.now() 