"""SQLAlchemy ORM模型定义"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, VARCHAR

from app.infrastructure.database.connection import Base
from app.domain.services.agents.utils import safe_json_dumps

class JSONType(TypeDecorator):
    """JSON类型装饰器，用于存储JSON数据"""
    impl = VARCHAR
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return safe_json_dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return value

class UserORM(Base):
    """用户ORM模型"""
    __tablename__ = "users"
    
    id = Column(String(255), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    groups = Column(JSONType, default=list)
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, default=datetime.now)
    
    # 关联关系
    tasks = relationship("UserTaskORM", back_populates="user", cascade="all, delete-orphan")
    files = relationship("UserFileORM", back_populates="user", cascade="all, delete-orphan")

class UserTaskORM(Base):
    """用户任务ORM模型"""
    __tablename__ = "user_tasks"
    
    id = Column(String(255), primary_key=True)
    user_id = Column(String(255), ForeignKey("users.id"), nullable=False, index=True)
    agent_id = Column(String(255), nullable=False)
    title = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)
    meta_data = Column(JSONType, default=dict)
    
    # 关联关系
    user = relationship("UserORM", back_populates="tasks")

class UserFileORM(Base):
    """用户文件ORM模型"""
    __tablename__ = "user_files"
    
    id = Column(String(255), primary_key=True)
    user_id = Column(String(255), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    path = Column(String(1000), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)
    meta_data = Column(JSONType, default=dict)
    
    # 关联关系
    user = relationship("UserORM", back_populates="files")

class ConversationHistoryORM(Base):
    """会话历史ORM模型"""
    __tablename__ = "conversation_histories"
    
    agent_id = Column(String(255), primary_key=True)
    user_id = Column(String(255), nullable=True, index=True)
    flow_id = Column(String(255), nullable=False, default="plan_act")
    title = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)
    
    # 关联关系
    events = relationship("ConversationEventORM", back_populates="history", cascade="all, delete-orphan")

class ConversationEventORM(Base):
    """会话事件ORM模型"""
    __tablename__ = "conversation_events"
    
    id = Column(String(255), primary_key=True)
    agent_id = Column(String(255), ForeignKey("conversation_histories.agent_id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    event_data = Column(JSONType, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    sequence = Column(Integer, nullable=False)
    
    # 关联关系
    history = relationship("ConversationHistoryORM", back_populates="events")
    
    # 复合索引和唯一约束
    __table_args__ = (
        Index('idx_agent_sequence', 'agent_id', 'sequence'),
        Index('idx_agent_timestamp', 'agent_id', 'timestamp'),
        UniqueConstraint('agent_id', 'sequence', name='uq_agent_sequence'),
    )

class EventBroadcasterORM(Base):
    """事件广播器ORM模型"""
    __tablename__ = "event_broadcasters"
    
    agent_id = Column(String(255), primary_key=True)
    current_sequence = Column(Integer, default=0)
    max_buffer_size = Column(Integer, default=1000)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)
    
    # 关联关系
    buffered_events = relationship("BufferedEventORM", back_populates="broadcaster", cascade="all, delete-orphan")

class BufferedEventORM(Base):
    """缓冲事件ORM模型"""
    __tablename__ = "buffered_events"
    
    id = Column(String(255), primary_key=True)
    agent_id = Column(String(255), ForeignKey("event_broadcasters.agent_id"), nullable=False)
    sequence = Column(Integer, nullable=False)
    event_type = Column(String(100), nullable=False)
    event_data = Column(JSONType, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    
    # 关联关系
    broadcaster = relationship("EventBroadcasterORM", back_populates="buffered_events")
    
    # 复合索引
    __table_args__ = (
        Index('idx_agent_sequence_buffered', 'agent_id', 'sequence'),
    )

class EventSubscriberORM(Base):
    """事件订阅者ORM模型"""
    __tablename__ = "event_subscribers"
    
    subscriber_id = Column(String(255), primary_key=True)
    agent_id = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now)
    last_activity = Column(DateTime, default=datetime.now)
    is_active = Column(String(10), default="true")  # 使用字符串存储布尔值
    heartbeat_timeout_seconds = Column(Integer, default=300)  # 5分钟超时
    
    # 复合索引
    __table_args__ = (
        Index('idx_agent_active', 'agent_id', 'is_active'),
        Index('idx_last_activity', 'last_activity'),
    )

class AgentContextORM(Base):
    """Agent上下文ORM模型"""
    __tablename__ = "agent_contexts"
    
    agent_id = Column(String(255), primary_key=True)
    user_id = Column(String(255), nullable=True, index=True)
    flow_id = Column(String(255), nullable=False, default="plan_act")
    sandbox_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="created", index=True)
    last_message = Column(Text, nullable=True)
    last_message_time = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)
    meta_data = Column(JSONType, default=dict)
    
    # Agent模型数据（序列化存储）
    agent_data = Column(JSONType, nullable=False)
    
    # 复合索引
    __table_args__ = (
        Index('idx_user_status', 'user_id', 'status'),
        Index('idx_status_updated', 'status', 'updated_at'),
        Index('idx_user_updated', 'user_id', 'updated_at'),
    ) 