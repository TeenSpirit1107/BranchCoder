"""仓储工厂：提供仓储实例"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncEngine
from app.domain.external.user_repository import UserRepository
from app.domain.external.conversation_repository import ConversationRepository
from app.domain.external.agent_context_repository import AgentContextRepository
from app.infrastructure.external.user.memory_repository import MemoryUserRepository
from app.infrastructure.external.conversation.memory_repository import MemoryConversationRepository
from app.infrastructure.external.agent_context.memory_repository import MemoryAgentContextRepository
from app.infrastructure.external.user.sqlite_repository import SQLiteUserRepository
from app.infrastructure.external.conversation.sqlite_repository import SQLiteConversationRepository
from app.infrastructure.external.agent_context.sqlite_repository import SQLiteAgentContextRepository
from app.infrastructure.external.event_subscription.memory_repository import MemoryEventSubscriptionManager
from app.infrastructure.external.event_subscription.sqlite_repository import SQLiteEventSubscriptionManager
from app.infrastructure.config import get_settings, Settings
from app.infrastructure.database.connection import get_engine

def get_user_repository(settings: Optional[Settings] = None, engine: Optional[AsyncEngine] = None) -> UserRepository:
    """
    获取用户仓储实例
    
    Args:
        settings: 配置对象，如果为None则使用默认配置
        engine: 可选的数据库引擎，如果提供则使用该引擎而不是默认引擎
        
    Returns:
        UserRepository 实例
        
    Raises:
        ValueError: 当数据库类型不支持时
    """
    if settings is None:
        settings = get_settings()
            
    if settings.database_type == "sqlite":
        if engine is None:
            engine = get_engine()
        return SQLiteUserRepository(engine)
    elif settings.database_type == "memory":
        return MemoryUserRepository()
    else:
        raise ValueError(f"Unsupported database type: {settings.database_type}")

def get_conversation_repository(settings: Optional[Settings] = None, engine: Optional[AsyncEngine] = None) -> ConversationRepository:
    """
    获取会话仓储实例
    
    Args:
        settings: 配置对象，如果为None则使用默认配置
        engine: 可选的数据库引擎，如果提供则使用该引擎而不是默认引擎
        
    Returns:
        ConversationRepository 实例
        
    Raises:
        ValueError: 当数据库类型不支持时
    """
    if settings is None:
        settings = get_settings()
            
    if settings.database_type == "sqlite":
        if engine is None:
            engine = get_engine()
        return SQLiteConversationRepository(engine)
    elif settings.database_type == "memory":
        return MemoryConversationRepository()
    else:
        raise ValueError(f"Unsupported database type: {settings.database_type}")

def get_agent_context_repository(settings: Optional[Settings] = None, engine: Optional[AsyncEngine] = None) -> AgentContextRepository:
    """
    获取Agent上下文仓储实例
    
    Args:
        settings: 配置对象，如果为None则使用默认配置
        engine: 可选的数据库引擎，如果提供则使用该引擎而不是默认引擎
        
    Returns:
        AgentContextRepository 实例
        
    Raises:
        ValueError: 当数据库类型不支持时
    """
    if settings is None:
        settings = get_settings()
            
    if settings.database_type == "sqlite":
        if engine is None:
            engine = get_engine()
        return SQLiteAgentContextRepository(engine)
    elif settings.database_type == "memory":
        return MemoryAgentContextRepository()
    else:
        raise ValueError(f"Unsupported database type: {settings.database_type}")

def get_event_subscription_manager(settings: Optional[Settings] = None, engine: Optional[AsyncEngine] = None):
    """
    获取事件订阅管理器实例
    
    Args:
        settings: 配置对象，如果为None则使用默认配置
        engine: 可选的数据库引擎，如果提供则使用该引擎而不是默认引擎
        
    Returns:
        EventSubscriptionManager 实例
        
    Raises:
        ValueError: 当数据库类型不支持时
    """
    if settings is None:
        settings = get_settings()
            
    if settings.database_type == "sqlite":
        if engine is None:
            engine = get_engine()
        return SQLiteEventSubscriptionManager(engine)
    elif settings.database_type == "memory":
        return MemoryEventSubscriptionManager()
    else:
        raise ValueError(f"Unsupported database type: {settings.database_type}")
