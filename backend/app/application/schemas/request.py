from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import time

class CreateAgentRequest(BaseModel):
    """Request model for creating an agent."""
    
    flow_id: str = Field(
        default="plan_act",
        description="要使用的flow类型ID",
        example="plan_act"
    )
    
    environment_variables: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="要传递到沙盒环境的环境变量",
        example={"PYTHON_PATH": "/usr/local/bin/python", "NODE_ENV": "production"}
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "flow_id": "plan_act",
                "environment_variables": {
                    "PYTHON_PATH": "/usr/local/bin/python",
                    "NODE_ENV": "production"
                }
            }
        }

class FileViewRequest(BaseModel):
    file: str

class ShellViewRequest(BaseModel):
    """Request model for viewing shell state."""
    
    session_id: str

class FileDownloadRequest(BaseModel):
    """请求模型，用于从沙箱下载文件"""
    file: str = Field(..., description="沙箱中的文件路径")

class FileUploadResponse(BaseModel):
    """响应模型，用于文件上传后返回文件ID和相关信息"""
    id: str
    filename: str
    path: str

class FileListRequest(BaseModel):
    """请求模型，用于列出沙箱中的文件"""
    path: Optional[str] = Field(
        default="/home/ubuntu",
        description="要列出文件的目录路径",
        examples=["/home/ubuntu", "/home/ubuntu/project", "/etc"]
    )

    class Config:
        json_schema_extra = {
            "example": {
                "path": "/home/ubuntu"
            }
        }

# 会话历史相关请求模型
class ReplayConversationRequest(BaseModel):
    """重放会话请求模型"""
    from_sequence: int = Field(default=1, ge=1, description="从第几个事件开始重放")

class ListConversationsRequest(BaseModel):
    """列出会话请求模型"""
    user_id: Optional[str] = Field(default=None, description="用户ID，用于过滤")
    limit: int = Field(default=50, ge=1, le=100, description="每页数量")
    offset: int = Field(default=0, ge=0, description="偏移量")

class SendMessageRequest(BaseModel):
    """发送消息请求模型（用于分离的消息发送接口）"""
    
    message: str = Field(..., description="消息内容")
    timestamp: int = Field(default_factory=lambda: int(time.time()), description="消息时间戳")
    file_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="附件文件ID列表，这些文件将被自动传输到沙盒中的/home/ubuntu目录",
        example=["f8e7d456-9c1a-4b5e-8e7d-456f9c1a4b5e"]
    )

# Agent上下文管理相关请求模型
class ListAgentContextsRequest(BaseModel):
    """列出Agent上下文请求模型"""
    user_id: Optional[str] = Field(default=None, description="用户ID，用于过滤")
    status: Optional[str] = Field(default=None, description="状态过滤")
    limit: int = Field(default=50, ge=1, le=100, description="每页数量")
    offset: int = Field(default=0, ge=0, description="偏移量")

class UpdateAgentStatusRequest(BaseModel):
    """更新Agent状态请求模型"""
    status: str = Field(..., description="新状态", example="active")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "active"
            }
        }