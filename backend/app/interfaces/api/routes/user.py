"""User-related API routes."""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import List, Optional, Dict, Any
import json

from app.application.schemas.user import (
    UserSchema, 
    UserTaskSchema, 
    UserFileSchema,
    UserFileMetadataSchema,
)
from app.application.schemas.request import FileUploadResponse
from app.application.services.user_context import get_required_user
from app.domain.models.user import User
from app.domain.services.user_service import UserService
from app.infrastructure.file_utils import save_uploaded_file
from app.interfaces.api.dependencies import get_user_service

__all__ = ["router"]

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserSchema)
async def get_current_user_info(user: User = Depends(get_required_user)):
    """Get current user information."""
    return user


@router.get("/me/tasks", response_model=List[UserTaskSchema])
async def get_current_user_tasks(user: User = Depends(get_required_user)):
    """Get current user tasks."""
    return UserService.get_user_tasks(user.id)


@router.get("/me/files", response_model=List[UserFileSchema])
async def get_current_user_files(user: User = Depends(get_required_user)):
    """Get current user files."""
    return UserService.get_user_files(user.id)


@router.post("/me/files", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    user: User = Depends(get_required_user),
    user_service: UserService = Depends(get_user_service)
):
    """
    上传文件并将其关联到当前用户。
    
    Args:
        file: 要上传的文件
        metadata: 可选的文件元数据（JSON 字符串）
        user: 当前用户（通过依赖项注入）
        
    Returns:
        上传的文件信息，包括 ID
    """
    # 解析元数据
    file_metadata: Dict[str, Any] = {}
    if metadata:
        try:
            file_metadata = json.loads(metadata)
        except json.JSONDecodeError:
            file_metadata = {"raw_metadata": metadata}
    
    # 保存文件
    file_info = save_uploaded_file(
        file.file,
        file.filename,
        user.id,
        file_metadata
    )
    
    # 创建文件记录并关联到用户
    user_file = await user_service.create_file(
        user_id=user.id,
        filename=file.filename,
        path=file_info["path"],
        metadata={
            "size": file_info.get("size"),
            "content_type": file.content_type,
            **file_metadata
        }
    )
    
    # 返回文件信息
    return {
        "id": user_file.id,
        "filename": user_file.filename,
        "path": user_file.path
    }

@router.get("/me/files/{file_id}", response_model=UserFileMetadataSchema)
async def get_file_metadata(
    file_id: str,
    user: User = Depends(get_required_user),
    user_service: UserService = Depends(get_user_service)
):
    """Get file metadata by file ID."""
    file = await user_service.get_file_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "id": file.id,
        "filename": file.filename,
        "path": file.path,
        "metadata": file.metadata
    }

