from typing import Any, Generic, Optional, TypeVar, List, Dict, Union
from pydantic import BaseModel, Field
from datetime import datetime


T = TypeVar('T')


class APIResponse(BaseModel, Generic[T]):
    code: int = 0
    msg: str = "success"
    data: Optional[T] = None 

    @staticmethod
    def success(data: Optional[T] = None, msg: str = "success") -> "APIResponse[T]":
        return APIResponse(code=0, msg=msg, data=data)

    @staticmethod
    def error(code: int, msg: str) -> "APIResponse[T]":
        return APIResponse(code=code, msg=msg, data=None)


class AgentResponse(BaseModel):
    agent_id: str
    status: str = "created"
    message: str = "Agent created successfully" 


class ConsoleRecord(BaseModel):
    ps1: str
    command: str
    output: str

class ShellViewResponse(BaseModel):
    output: str
    session_id: str
    console: Optional[List[ConsoleRecord]] = None

class FileViewResponse(BaseModel):
    """File view response model"""
    content: str
    file: str


class FileDownloadResponse(BaseModel):
    """文件下载响应模型"""
    filename: str
    content_type: str
    # 二进制内容不在此模型中表示，而是通过响应直接返回

class FileListItem(BaseModel):
    """文件列表项模型"""
    name: str
    path: str
    size: int
    is_dir: bool
    modified_time: str

class FileListResponse(BaseModel):
    """文件列表响应模型"""
    current_path: str
    items: List[FileListItem]

# 会话历史相关响应模型
class ConversationEventResponse(BaseModel):
    """会话事件响应模型"""
    id: str
    agent_id: str
    event_type: str
    event_data: Dict[str, Any]
    timestamp: datetime
    sequence: int

class ConversationHistoryResponse(BaseModel):
    """会话历史响应模型"""
    agent_id: str
    user_id: Optional[str] = None
    flow_id: str
    title: Optional[str] = None  # 会话标题
    created_at: datetime
    updated_at: datetime
    events: List[ConversationEventResponse]
    total_events: int

class ConversationListResponse(BaseModel):
    """会话列表响应模型"""
    conversations: List[ConversationHistoryResponse]
    total: int
    limit: int
    offset: int

class SendMessageResponse(BaseModel):
    """发送消息响应模型"""
    
    success: bool = Field(..., description="是否发送成功")
    message_id: Optional[str] = Field(None, description="消息ID")
    timestamp: int = Field(..., description="消息时间戳")
    queued: bool = Field(default=True, description="消息是否已加入处理队列")
