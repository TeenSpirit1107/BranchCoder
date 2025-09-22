"""User context service for handling user information in requests."""

from typing import Optional, Dict, Any
from contextvars import ContextVar
from fastapi import Request, Depends

from ...domain.models.user import User
from ...domain.services.user_service import UserService
from ...infrastructure.external.auth.oauth2 import OAuth2Service
from ...infrastructure.external.factories import get_user_repository

# 创建用户上下文变量
current_user_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar("current_user_context", default=None)
current_user_model: ContextVar[Optional[User]] = ContextVar("current_user_model", default=None)


class UserContext:
    """User context manager for the current request."""
    
    @staticmethod
    async def get_current_user_info(request: Request) -> Optional[Dict[str, Any]]:
        """
        Get the current user information from OAuth2 headers.
        
        Args:
            request: The FastAPI request
            
        Returns:
            User information dictionary or None
        """
        # 从请求头中获取用户信息
        user_info = await OAuth2Service.get_current_user(request)
        
        if user_info:
            # 存储在上下文变量中
            current_user_context.set(user_info)
            return user_info
        
        return None
    
    @staticmethod
    async def get_current_user(request: Request) -> Optional[User]:
        """
        Get the current user model from the database/store.
        
        Args:
            request: The FastAPI request
            
        Returns:
            User model or None
        """
        user_info = await UserContext.get_current_user_info(request)
        
        if not user_info:
            return None
        
        # 从用户服务获取或创建用户
        user_repository = get_user_repository()
        user_service = UserService(user_repository)
        user = await user_service.get_or_create_user(user_info)
        
        # 存储在上下文变量中
        current_user_model.set(user)
        
        return user
    
    @staticmethod
    def get_current_user_id() -> Optional[str]:
        """
        Get the current user ID from context.
        
        Returns:
            User ID or None
        """
        user_info = current_user_context.get()
        if user_info:
            return user_info.get("user_id")
        return None
    
    @staticmethod
    def get_user_model() -> Optional[User]:
        """
        Get the current user model from context.
        
        Returns:
            User model or None
        """
        return current_user_model.get()


async def get_current_user(request: Request) -> Optional[User]:
    """
    FastAPI dependency for getting the current user.
    
    Args:
        request: The FastAPI request
        
    Returns:
        User model or None
    """
    return await UserContext.get_current_user(request)


async def get_optional_user(request: Request) -> Optional[User]:
    """
    FastAPI dependency for getting the optional current user.
    
    Args:
        request: The FastAPI request
        
    Returns:
        User model or None
    """
    try:
        return await UserContext.get_current_user(request)
    except Exception:
        return None


async def get_required_user(request: Request) -> User:
    """
    FastAPI dependency for getting the required current user.
    
    Args:
        request: The FastAPI request
        
    Returns:
        User model
        
    Raises:
        HTTPException: If user is not authenticated
    """
    from fastapi import HTTPException, status
    
    user = await UserContext.get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user 