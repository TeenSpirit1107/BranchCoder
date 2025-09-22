"""User-related schemas."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime


class UserFileSchema(BaseModel):
    """Schema for user file."""
    
    id: str
    filename: str
    path: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = {}
    
    class Config:
        from_attributes = True


class UserFileMetadataSchema(BaseModel):
    """Schema for user file metadata."""
    
    id: str
    filename: str
    path: str
    metadata: Dict[str, Any] = {}


class UserTaskSchema(BaseModel):
    """Schema for user task."""
    
    id: str
    agent_id: str
    title: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}
    
    class Config:
        from_attributes = True


class UserSchema(BaseModel):
    """Schema for user information."""
    
    id: str
    email: str
    name: Optional[str] = None
    groups: List[str] = []
    created_at: datetime
    last_login: datetime
    
    class Config:
        from_attributes = True
