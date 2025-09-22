from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator, Dict, Any, List, Optional
from sse_starlette.event import ServerSentEvent
import asyncio
import websockets
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Response
from fastapi.responses import StreamingResponse
from app.application.services.agent import AgentService
from app.application.schemas.request import FileViewRequest, ShellViewRequest, FileDownloadRequest, FileListRequest, CreateAgentRequest, SendMessageRequest, UpdateAgentStatusRequest
from app.application.schemas.response import APIResponse, AgentResponse, ShellViewResponse, FileViewResponse, FileListResponse, SendMessageResponse
from urllib.parse import quote
import re

__all__ = ["router"]

router = APIRouter(prefix="/agents", tags=["agents"])

agent_service = AgentService()
logger = logging.getLogger(__name__)

@router.get("/flows", response_model=APIResponse[List[Dict[str, str]]])
async def get_available_flows() -> APIResponse[List[Dict[str, str]]]:
    """获取所有可用的flow类型"""
    flows = agent_service.agent_domain_service.get_available_flows()
    return APIResponse.success(flows)

@router.post("/", response_model=APIResponse[AgentResponse])
@router.post("", response_model=APIResponse[AgentResponse])
async def create_agent(request: CreateAgentRequest = None) -> APIResponse[AgentResponse]:
    if request is None:
        request = CreateAgentRequest()
    agent = await agent_service.create_agent(request)
    return APIResponse.success(
        AgentResponse(
            agent_id=agent.id,
            status="created",
            message="Agent created successfully"
        )
    )

@router.post("/{agent_id}/shell", response_model=APIResponse[ShellViewResponse])
async def view_shell(agent_id: str, request: ShellViewRequest) -> APIResponse[ShellViewResponse]:
    """View shell session output
    
    If the agent does not exist or fails to get shell output, an appropriate exception will be thrown and handled by the global exception handler
    """
    result = await agent_service.shell_view(agent_id, request.session_id)
    return APIResponse.success(result)


@router.post("/{agent_id}/file", response_model=APIResponse[FileViewResponse])
async def view_file(agent_id: str, request: FileViewRequest) -> APIResponse[FileViewResponse]:
    """View file content
    
    If the agent does not exist or fails to get file content, an appropriate exception will be thrown and handled by the global exception handler
    
    Args:
        agent_id: Agent ID
        file: File path
        
    Returns:
        APIResponse containing file content
    """
    result = await agent_service.file_view(agent_id, request.file)
    return APIResponse.success(result)


@router.post("/{agent_id}/list-files", response_model=APIResponse[FileListResponse])
async def list_files(agent_id: str, request: FileListRequest) -> APIResponse[FileListResponse]:
    """
    列出沙箱中的文件
    
    Args:
        agent_id: Agent ID
        request: 包含目录路径的请求
        
    Returns:
        包含文件列表的响应
    """
    logger.info(f"List files request for agent {agent_id}, path: {request.path}")
    
    # 确保路径是有效的
    path = request.path if request.path else "/home/ubuntu"
    
    try:
        result = await agent_service.list_files(agent_id, path)
        return APIResponse.success(result)
    except Exception as e:
        logger.error(f"Failed to list files in {path}: {str(e)}")
        return APIResponse.error(code=500, msg=f"Failed to list files: {str(e)}")


@router.get("/{agent_id}/file/download")
async def download_file(agent_id: str, file: str):
    """
    从沙箱下载文件
    
    如果Agent或沙箱不存在，或者文件不存在或无法访问，将抛出相应的异常
    
    Args:
        agent_id: Agent ID
        file: 文件路径（通过查询参数提供）
        
    Returns:
        包含文件二进制内容的流式响应
    """
    logger.info(f"Download file request for agent {agent_id}, file: {file}")
    
    try:
        content, filename, content_type = await agent_service.download_file(agent_id, file)
        
        logger.info(f"Successfully downloaded file {filename}, size: {len(content)} bytes, type: {content_type}")
        
        # RFC 6266 规范处理国际化文件名
        # 检查文件名是否只包含ASCII字符
        is_ascii = all(ord(c) < 128 for c in filename)
        
        if is_ascii:
            # 如果是ASCII文件名，直接使用
            content_disposition = f'attachment; filename="{filename}"'
        else:
            # 对于非ASCII文件名，提供两种形式
            # 1. filename参数使用ASCII文件名（可以是原始名称的简化版或转义版）
            # 2. filename*参数使用UTF-8编码的完整文件名
            
            # 创建一个简单的ASCII文件名版本
            ascii_filename = re.sub(r'[^\x00-\x7F]', '_', filename)
            
            # 为filename*参数编码UTF-8文件名
            utf8_filename = quote(filename)
            
            content_disposition = f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{utf8_filename}'
        
        # 直接返回二进制内容，不进行流式处理，避免大文件内存问题
        response = Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": content_disposition,
                "Content-Length": str(len(content))
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error downloading file {file}: {str(e)}")
        raise e  # 让全局异常处理器处理


@router.websocket("/{agent_id}/vnc")
async def vnc_websocket(websocket: WebSocket, agent_id: str):
    """VNC WebSocket endpoint (binary mode)
    
    Establishes a connection with the VNC WebSocket service in the sandbox environment and forwards data bidirectionally
    
    Args:
        websocket: WebSocket connection
        agent_id: Agent ID
    """
    logger.info(f"VNC WebSocket connection accepted for agent {agent_id}")
    await websocket.accept(subprotocol="binary")
    
    try:
    
        # Get sandbox environment address
        sandbox_ws_url = await agent_service.get_vnc_url(agent_id)

        logger.info(f"Connecting to VNC WebSocket at {sandbox_ws_url}")
    
        # Connect to sandbox WebSocket
        async with websockets.connect(sandbox_ws_url) as sandbox_ws:
            logger.info(f"Connected to VNC WebSocket at {sandbox_ws_url}")
            # Create two tasks to forward data bidirectionally
            async def forward_to_sandbox():
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        # logger.debug(f"Forwarding data to sandbox: {data}")
                        await sandbox_ws.send(data)
                except WebSocketDisconnect:
                    logger.info("Web -> VNC connection closed")
                    pass
                except Exception as e:
                    logger.error(f"Error forwarding data to sandbox: {e}")
            
            async def forward_from_sandbox():
                try:
                    while True:
                        data = await sandbox_ws.recv()
                        await websocket.send_bytes(data)
                except websockets.exceptions.ConnectionClosed:
                    logger.info("VNC -> Web connection closed")
                    pass
                except Exception as e:
                    logger.error(f"Error forwarding data from sandbox: {e}")
            
            # Run two forwarding tasks concurrently
            forward_task1 = asyncio.create_task(forward_to_sandbox())
            forward_task2 = asyncio.create_task(forward_from_sandbox())
            
            # Wait for either task to complete (meaning connection has closed)
            done, pending = await asyncio.wait(
                [forward_task1, forward_task2],
                return_when=asyncio.FIRST_COMPLETED
            )

            logger.info("WebSocket connection closed")
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
    
    except ConnectionError as e:
        logger.error(f"Unable to connect to sandbox environment: {str(e)}")
        await websocket.close(code=1011, reason=f"Unable to connect to sandbox environment: {str(e)}")
    except Exception as e:
        logger.error(f"VNC WebSocket error: {str(e)}")
        await websocket.close()


@router.get("/{agent_id}/events")
async def get_event_stream(agent_id: str, from_sequence: int = 1) -> EventSourceResponse:
    """
    获取Agent的事件流，支持断连重连
    
    这个端点允许客户端在断连后重新连接，并从指定序号开始接收事件。
    Agent会继续在后台运行，即使没有客户端连接。
    
    Args:
        agent_id: Agent ID
        from_sequence: 从指定序号开始获取事件（默认为1，即从头开始）
    
    Returns:
        EventSourceResponse: 服务器发送事件流
    """
    logger.info(f"Event stream request for agent {agent_id} from sequence {from_sequence}")
    
    async def event_generator() -> AsyncGenerator[ServerSentEvent, None]:
        async for event in agent_service.get_event_stream(agent_id, from_sequence):
            yield ServerSentEvent(
                event=event.event,
                data=event.data.model_dump_json() if event.data else None
            )

    return EventSourceResponse(event_generator())

@router.post("/{agent_id}/send-message", response_model=APIResponse[SendMessageResponse])
async def send_message(agent_id: str, request: SendMessageRequest) -> APIResponse[SendMessageResponse]:
    """
    发送消息到Agent（不返回事件流）
    
    这个接口只负责将消息放入Agent的处理队列，不返回事件流。
    客户端需要通过 GET /{agent_id}/events 接口来接收事件流。
    
    如果提供了文件ID列表，将自动将这些文件传输到沙箱的/home/ubuntu目录
    
    Args:
        agent_id: Agent ID
        request: 消息发送请求，包含消息和可选的文件ID列表
    
    Returns:
        APIResponse[SendMessageResponse]: 发送结果
    """
    logger.info(f"Send message request for agent {agent_id}: {request.message[:50]}...")
    
    # 检查是否有附件
    if request.file_ids and len(request.file_ids) > 0:
        logger.info(f"Request includes {len(request.file_ids)} file attachments")
    
    try:
        success = await agent_service.send_message(
            agent_id=agent_id,
            message=request.message,
            timestamp=request.timestamp,
            file_ids=request.file_ids
        )
        
        response = SendMessageResponse(
            success=success,
            timestamp=request.timestamp,
            queued=True
        )
        
        return APIResponse.success(data=response, msg="Message sent successfully")
        
    except Exception as e:
        logger.error(f"Failed to send message to agent {agent_id}: {str(e)}")
        return APIResponse.error(code=500, msg=f"Failed to send message: {str(e)}")


@router.get("/flows")
async def get_flows() -> APIResponse[List[Dict[str, str]]]:
    """
    获取所有可用的flow类型
    
    Returns:
        APIResponse[List[Dict[str, str]]]: 包含所有可用flow类型的列表
    """
    flows = await agent_service.get_available_flows()
    return APIResponse.success(flows)


@router.get("/{agent_id}/code-server-url")
async def get_code_server_subdomain_url(agent_id: str) -> APIResponse[Dict[str, str]]:
    """
    获取Agent的Code Server子域名URL
    
    Args:
        agent_id: Agent ID
        
    Returns:
        APIResponse[Dict[str, str]]: 包含Code Server子域名URL的响应
    """
    logger.info(f"Getting Code Server subdomain URL for agent {agent_id}")
    
    try:
        subdomain_url = await agent_service.get_code_server_subdomain_url(agent_id)
        return APIResponse.success({
            "agent_id": agent_id,
            "code_server_url": subdomain_url
        })
    except Exception as e:
        logger.error(f"Failed to get Code Server URL for agent {agent_id}: {str(e)}")
        return APIResponse.error(code=500, msg=f"Failed to get Code Server URL: {str(e)}")
