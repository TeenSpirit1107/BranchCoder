from pydantic import BaseModel
from typing import Optional, Dict, Any


class FileViewRequest(BaseModel):
    """File view request schema"""
    file: str


class FileViewResponse(BaseModel):
    """File view response schema"""
    content: str
    file: str


class FileUploadResponse(BaseModel):
    """File upload response schema"""
    file_id: str
    filename: str
    size: int
    upload_date: str
    message: str


class FileInfoResponse(BaseModel):
    """File info response schema"""
    file_id: str
    filename: str
    content_type: Optional[str]
    size: int
    upload_date: str
    metadata: Optional[Dict[str, Any]]
