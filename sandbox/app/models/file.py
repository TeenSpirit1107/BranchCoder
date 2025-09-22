"""
File operation related models
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class FileReadResult(BaseModel):
    """File read result"""
    content: str = Field(..., description="File content")
    file: str = Field(..., description="Path of the read file")


class FileWriteResult(BaseModel):
    """File write result"""
    file: str = Field(..., description="Path of the written file")
    bytes_written: int = Field(..., description="Number of bytes written")


class FileReplaceResult(BaseModel):
    """File replace result"""
    file: str = Field(..., description="Path of the modified file")
    replaced_count: int = Field(..., description="Number of replacements made")


class FileSearchResult(BaseModel):
    """File search result"""
    file: str = Field(..., description="Path of the searched file")
    matches: List[str] = Field(..., description="Lines matched")
    line_numbers: List[int] = Field(..., description="Line numbers with matches")


class FileFindResult(BaseModel):
    """File find result"""
    path: str = Field(..., description="Path that was searched")
    files: List[str] = Field(..., description="Files found")


class FileUploadResponse(BaseModel):
    """File upload response"""
    file: str = Field(..., description="Absolute path of the uploaded file")
    size: int = Field(..., description="Size of the uploaded file in bytes")
    is_executable: bool = Field(False, description="Whether the file is executable")


class FileExistsResult(BaseModel):
    """File exists result"""
    path: str = Field(..., description="Path of the checked file")
    exists: bool = Field(..., description="Whether the file exists")
    is_file: Optional[bool] = Field(None, description="Whether it is a file (if exists)")
    is_dir: Optional[bool] = Field(None, description="Whether it is a directory (if exists)")
