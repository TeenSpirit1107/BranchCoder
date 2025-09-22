"""API middlewares."""

from fastapi import Request
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
from app.application.services.user_context import UserContext
import httpx
import re
import asyncio
from urllib.parse import urlparse
from starlette.responses import StreamingResponse
from starlette.websockets import WebSocket
from app.infrastructure.config import get_settings
from app.application.schemas.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class UserContextMiddleware(BaseHTTPMiddleware):
    """Middleware for setting up user context."""
    
    async def dispatch(self, request: Request, call_next):
        """
        Process the request and load user information.
        
        Args:
            request: The incoming request
            call_next: The next middleware or endpoint

        Returns:
            The response
        """
        try:
            # 尝试获取用户信息
            await UserContext.get_current_user_info(request)
            logger.debug("User context loaded")
        except Exception as e:
            logger.warning(f"Failed to load user context: {e}")
        
        response = await call_next(request)
        return response

class CodeServerSubdomainMiddleware(BaseHTTPMiddleware):
    """Code Server子域名代理中间件"""
    
    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        self.agent_service = None  # 将在__call__中获取
        
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'client') and self.client:
            asyncio.create_task(self.client.aclose())
    
    async def dispatch(self, request: Request, call_next):
        """处理请求分发"""
        host = request.headers.get("host", "")
        
        # 检查是否是Code Server子域名请求
        agent_id = self._extract_agent_id_from_subdomain(host)
        if agent_id:
            logger.info(f"Detected Code Server subdomain request for agent {agent_id}, host: {host}")
            
            # 只处理HTTP请求，WebSocket请求由专门的路由处理
            if not self._is_websocket_request(request):
                return await self._handle_code_server_request(request, agent_id)
            else:
                logger.info(f"WebSocket request detected, will be handled by dedicated WebSocket route")
        
        # 不是子域名请求，或者是WebSocket请求
        return await call_next(request)
    
    def _extract_agent_id_from_subdomain(self, host: str) -> str | None:
        """从子域名中提取agent_id
        
        Args:
            host: 请求的Host头值
            
        Returns:
            提取的agent_id，如果不匹配则返回None
        """
        if not host:
            return None
        
        # 构建正则表达式匹配模式：code-{agent_id}.localhost.betterspace.top
        pattern = rf"^code-([a-f0-9]{{16}})\.{re.escape(self.settings.code_server_origin)}(?::\d+)?$"
        match = re.match(pattern, host)
        
        if match:
            agent_id = match.group(1)
            logger.debug(f"Extracted agent_id: {agent_id} from host: {host}")
            return agent_id
        
        return None
    
    async def _handle_code_server_request(self, request: Request, agent_id: str) -> Response:
        """处理Code Server请求
        
        Args:
            request: 原始请求
            agent_id: 提取的agent_id
            
        Returns:
            代理响应
        """
        try:
            # 懒加载AgentService，避免循环导入
            if not self.agent_service:
                from app.application.services.agent import AgentService
                self.agent_service = AgentService()
            
            # 检查Agent是否存在
            if not await self.agent_service.agent_exists(agent_id):
                logger.warning(f"Agent {agent_id} not found for Code Server request")
                return JSONResponse(
                    status_code=404,
                    content={"error": f"Agent {agent_id} not found or expired"}
                )
            
            # 获取沙箱的Code Server URL
            target_url = await self.agent_service.get_code_server_url(agent_id)
            if not target_url:
                logger.warning(f"target_url for agent {agent_id} not found")
                return JSONResponse(
                    status_code=502,
                    content={"error": "Code Server service temporarily unavailable"}
                )
            logger.info(f"Proxying Code Server request to: {target_url}")
            
            # 处理HTTP请求代理
            return await self._handle_http_proxy(request, target_url)
        
        except NotFoundError as e:
            logger.warning(f"Agent {agent_id} not found for Code Server request")
            return JSONResponse(
                status_code=404,
                content={"error": f"Agent {agent_id} not found or expired"}
            )

        except Exception as e:
            logger.exception(f"Error handling Code Server request for agent {agent_id}: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error"}
            )
    
    def _is_websocket_request(self, request: Request) -> bool:
        """检查是否是WebSocket升级请求"""
        connection = request.headers.get("connection", "").lower()
        upgrade = request.headers.get("upgrade", "").lower()
        return "upgrade" in connection and upgrade == "websocket"
    
    async def _handle_http_proxy(self, request: Request, target_base_url: str) -> Response:
        """处理HTTP请求代理
        
        Args:
            request: 原始请求
            target_base_url: 目标服务的基础URL
            
        Returns:
            代理响应
        """
        # 获取原始路径（不使用urljoin，直接拼接）
        request_path = str(request.url.path)
        request_query = str(request.url.query) if request.url.query else ""
        
        # 确保target_base_url不以斜杠结尾，request_path以斜杠开头
        target_base_clean = target_base_url.rstrip('/')
        request_path_clean = request_path if request_path.startswith('/') else '/' + request_path
        
        # 直接拼接URL，避免urljoin的路径替换问题
        target_url = target_base_clean + request_path_clean
        if request_query:
            target_url += f"?{request_query}"
        
        # 添加详细的调试日志
        logger.info(f"Proxying {request.method} request:")
        logger.info(f"  Original path: {request_path}")
        logger.info(f"  Target base: {target_base_url}")
        logger.info(f"  Final URL: {target_url}")
        
        # 准备请求头 - 保留大部分头信息，只移除可能导致问题的头
        headers = dict(request.headers)
        
        # 移除可能导致冲突的头
        headers_to_remove = [
            "host",  # 避免host头冲突
            "referer",
            "content-length",  # httpx会自动设置
            "transfer-encoding",  # httpx会自动处理
        ]
        
        for header in headers_to_remove:
            headers.pop(header, None)
            headers.pop(header.lower(), None)  # 确保大小写都处理
            headers.pop(header.upper(), None)
        
        # 保留重要的头信息，包括但不限于：
        # - cookies (Cookie)
        # - authorization (Authorization) 
        # - content-type (Content-Type)
        # - accept-* 系列头
        # - user-agent (User-Agent)
        # - referer (Referer)
        # - cache-control (Cache-Control)
        # - if-* 条件头
        
        logger.debug(f"Forwarding headers: {list(headers.keys())}")
        
        # 读取请求体
        body = await request.body() if request.method in ["POST", "PUT", "PATCH"] else None
        
        try:
            # 发送代理请求
            response = await self.client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=False
            )
            
            logger.debug(f"Proxy response: {response.status_code} for {target_url}")
            
            # 准备响应头
            response_headers = dict(response.headers)
            # 移除可能导致问题的头
            response_headers.pop("content-encoding", None)
            response_headers.pop("transfer-encoding", None)
            
            # 处理流式响应
            if response.headers.get("content-type", "").startswith("text/") or \
               response.headers.get("content-type", "").startswith("application/json"):
                # 对于文本内容，直接返回
                content = response.content
                return Response(
                    content=content,
                    status_code=response.status_code,
                    headers=response_headers
                )
            else:
                # 对于其他内容（如二进制文件），使用流式响应
                async def stream_response():
                    async for chunk in response.aiter_bytes():
                        yield chunk
                
                return StreamingResponse(
                    stream_response(),
                    status_code=response.status_code,
                    headers=response_headers
                )
                
        except httpx.RequestError as e:
            logger.error(f"Proxy request failed for {target_url}: {str(e)}")
            return JSONResponse(
                status_code=502,
                content={"error": "Proxy request failed"}
            )
        except Exception as e:
            logger.exception(f"Unexpected error in HTTP proxy for {target_url}: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"error": "Internal proxy error"}
            ) 