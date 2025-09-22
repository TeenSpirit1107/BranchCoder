from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CreateEventSubscriptionRequest(BaseModel):
    """创建事件订阅请求"""
    agent_id: str = Field(..., description="Agent ID")
    from_sequence: int = Field(default=1, description="从指定序号开始订阅事件")


class EventSubscriptionResponse(BaseModel):
    """事件订阅响应"""
    subscription_id: str = Field(..., description="订阅ID")
    agent_id: str = Field(..., description="Agent ID") 
    from_sequence: int = Field(..., description="起始序号")
    created_at: datetime = Field(..., description="创建时间")
    is_active: bool = Field(..., description="是否活跃")


class EventSubscriptionHeartbeatRequest(BaseModel):
    """事件订阅心跳请求"""
    subscription_id: str = Field(..., description="订阅ID")


class EventStreamRequest(BaseModel):
    """事件流请求"""
    agent_id: str = Field(..., description="Agent ID")
    from_sequence: int = Field(default=1, description="从指定序号开始")
    subscription_id: Optional[str] = Field(None, description="订阅ID（用于心跳更新）") 