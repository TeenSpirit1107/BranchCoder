"""API依赖项"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.services.user_service import UserService
from app.infrastructure.external.factories import get_user_repository, get_conversation_repository
from app.infrastructure.database.connection import get_session, get_engine

async def get_user_service() -> UserService:
    """
    获取用户服务实例
    
    Returns:
        UserService 实例
    """
    user_repository = get_user_repository()
    return UserService(user_repository)
