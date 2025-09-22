from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class ConversationEvent(BaseModel):
    """会话事件记录"""
    
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    agent_id: str  # 使用agent_id作为会话标识
    event_type: str  # 事件类型：message, tool, step, plan, error, done等
    event_data: Dict[str, Any]  # 事件数据
    timestamp: datetime = Field(default_factory=datetime.now)
    sequence: int  # 事件在会话中的序号
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ConversationHistory(BaseModel):
    """会话历史记录"""
    
    agent_id: str  # 使用agent_id作为会话标识
    user_id: Optional[str] = None
    flow_id: str = "plan_act"
    title: Optional[str] = None  # 会话标题
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    events: List[ConversationEvent] = Field(default_factory=list)
    
    def add_event(self, event_type: str, event_data: Dict[str, Any]) -> ConversationEvent:
        """添加事件到会话历史"""
        event = ConversationEvent(
            agent_id=self.agent_id,
            event_type=event_type,
            event_data=event_data,
            sequence=len(self.events) + 1
        )
        self.events.append(event)
        self.updated_at = datetime.now()
        return event
    
    def get_events_from_sequence(self, from_sequence: int = 1) -> List[ConversationEvent]:
        """获取从指定序号开始的事件"""
        return [event for event in self.events if event.sequence >= from_sequence]
    
    def get_latest_events(self, count: int = 10) -> List[ConversationEvent]:
        """获取最新的N个事件"""
        return self.events[-count:] if len(self.events) > count else self.events
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 