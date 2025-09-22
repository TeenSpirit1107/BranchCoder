"""OAuth2 authentication service for extracting user information from OAuth2 Proxy headers."""

from fastapi import Request
from typing import Optional, Dict, Any
import logging
from app.infrastructure.config import get_settings

logger = logging.getLogger(__name__)

class OAuth2Service:
    """Service for handling OAuth2 authentication and user information."""
    
    # OAuth2 Proxy header names
    USER_HEADER = "X-Auth-Request-User"
    EMAIL_HEADER = "X-Auth-Request-Email"
    GROUPS_HEADER = "X-Auth-Request-Groups"
    
    # 开发模式默认用户
    DEFAULT_DEV_USER = {
        "user_id": "dev_user",
        "email": "dev@example.com",
        "groups": [],
        "is_authenticated": True
    }
    
    @classmethod
    async def get_current_user(cls, request: Request) -> Optional[Dict[Any, Any]]:
        """
        Extract user information from OAuth2 Proxy headers.
        
        Args:
            request: The incoming FastAPI request
            
        Returns:
            A dictionary containing user information or None if no user information is found
        """
        # 在开发模式下返回默认用户信息
        if get_settings().bypass_oauth2:
            logger.debug("Using development mode, bypassing OAuth2 authentication")
            return cls.DEFAULT_DEV_USER
            
        headers = request.headers
        
        user_id = headers.get(cls.USER_HEADER)
        email = headers.get(cls.EMAIL_HEADER)
        groups = headers.get(cls.GROUPS_HEADER, "").split(",") if headers.get(cls.GROUPS_HEADER) else []
        
        if not user_id and not email:
            logger.warning("No user information found in request headers")
            return None
        
        logger.debug(f"Extracted user information: user_id={user_id}, email={email}")
        
        return {
            "user_id": user_id,
            "email": email,
            "groups": groups,
            "is_authenticated": bool(user_id or email)
        }
