"""Code Server WebSocket 代理路由"""

import logging
import asyncio
import re
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from app.application.services.agent import AgentService
from app.infrastructure.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

def extract_agent_id_from_host(host: str) -> str | None:
    """从host头中提取agent_id"""
    if not host:
        return None
    
    settings = get_settings()
    pattern = rf"^code-([a-f0-9]{{16}})\.{re.escape(settings.code_server_origin)}(?::\d+)?$"
    match = re.match(pattern, host)
    
    if match:
        agent_id = match.group(1)
        logger.debug(f"Extracted agent_id: {agent_id} from host: {host}")
        return agent_id
    
    return None

async def _handle_common_code_server_ws(websocket: WebSocket, full_path: str):
    """通用WebSocket处理逻辑的包装器，用于从host头提取agent_id"""
    host = websocket.headers.get('host')
    
    logger.info(f"Code Server direct WebSocket request: host={host}, path=/{full_path}")
    
    agent_id = extract_agent_id_from_host(host)
    
    if not agent_id:
        logger.warning(f"Could not extract agent_id from host: {host}")
        await websocket.close(code=1003, reason="Invalid host")
        return
    
    await code_server_websocket_proxy_logic(websocket, agent_id, full_path)

# --- Parameterized routes (usually for testing or specific integrations) ---
@router.websocket("/api/code-server-ws/{agent_id}")
async def code_server_websocket_proxy_no_path(websocket: WebSocket, agent_id: str):
    await code_server_websocket_proxy_logic(websocket, agent_id, "")

@router.websocket("/api/code-server-ws/{agent_id}/{path:path}")
async def code_server_websocket_proxy_with_path(websocket: WebSocket, agent_id: str, path: str):
    await code_server_websocket_proxy_logic(websocket, agent_id, path)

# --- Stable routes ---
@router.websocket("/stable-{version}")
async def code_server_stable_no_path(websocket: WebSocket, version: str):
    await _handle_common_code_server_ws(websocket, f"stable-{version}")

@router.websocket("/stable-{version}/{path:path}")
async def code_server_stable_with_path(websocket: WebSocket, version: str, path: str):
    await _handle_common_code_server_ws(websocket, f"stable-{version}/{path}")

# --- Static routes ---
@router.websocket("/_static/{path:path}")
async def code_server_static_with_path(websocket: WebSocket, path: str):
    await _handle_common_code_server_ws(websocket, f"_static/{path}")

# --- Remote resource routes ---
@router.websocket("/vscode-remote-resource/{path:path}")
async def code_server_remote_resource_with_path(websocket: WebSocket, path: str):
    await _handle_common_code_server_ws(websocket, f"vscode-remote-resource/{path}")

# --- Catch-all route for any other paths ---
# @router.websocket("/{path:path}")
# async def code_server_catch_all_ws(websocket: WebSocket, path: str):
#     logger.info(f"WebSocket request caught by catch-all route for path: /{path}")
#     await _handle_common_code_server_ws(websocket, path)

async def code_server_websocket_proxy_logic(websocket: WebSocket, agent_id: str, path: str):
    """
    通用的Code Server WebSocket代理逻辑
    
    Args:
        websocket: FastAPI WebSocket连接
        agent_id: Agent ID
        path: 请求路径
    """
    logger.info(f"Processing Code Server WebSocket for agent {agent_id}, path: /{path}")
    
    target_ws_url = ""
    try:
        agent_service = AgentService()
        
        if not await agent_service.agent_exists(agent_id):
            logger.warning(f"Agent {agent_id} not found for WebSocket request")
            await websocket.close(code=1003, reason="Agent not found")
            return
        
        target_base_url = await agent_service.get_code_server_url(agent_id)
        if not target_base_url:
            logger.warning(f"Code Server URL not available for agent {agent_id}")
            await websocket.close(code=1011, reason="Code Server not available")
            return
        
        if target_base_url.startswith('https://'):
            target_ws_url = target_base_url.replace('https://', 'wss://', 1)
        else:
            target_ws_url = target_base_url.replace('http://', 'ws://', 1)
        
        if path:
            target_ws_url = f"{target_ws_url.rstrip('/')}/{path.lstrip('/')}"
        
        if websocket.query_params:
            query_string = str(websocket.query_params)
            target_ws_url = f"{target_ws_url}?{query_string}"
        
        logger.info(f"Connecting to target WebSocket: {target_ws_url}")
        
        await websocket.accept()
        
        async with websockets.connect(target_ws_url) as target_ws:
            logger.info(f"Successfully connected to target WebSocket: {target_ws_url}")
            
            async def forward_to_target():
                try:
                    while websocket.client_state == WebSocketState.CONNECTED:
                        try:
                            data = await websocket.receive()
                            if 'bytes' in data:
                                await target_ws.send(data['bytes'])
                            elif 'text' in data:
                                await target_ws.send(data['text'])
                        except WebSocketDisconnect:
                            logger.info("Client WebSocket disconnected.")
                            break
                except Exception as e:
                    if not isinstance(e, (WebSocketDisconnect, websockets.exceptions.ConnectionClosed)):
                         logger.error(f"Error in forward_to_target: {type(e).__name__} - {e}")

            async def forward_from_target():
                try:
                    async for message in target_ws:
                        try:
                            if isinstance(message, bytes):
                                await websocket.send_bytes(message)
                            else:
                                await websocket.send_text(message)
                        except WebSocketDisconnect:
                            logger.info("Client WebSocket disconnected during forward from target.")
                            break
                except Exception as e:
                    if not isinstance(e, (WebSocketDisconnect, websockets.exceptions.ConnectionClosed)):
                        logger.error(f"Error in forward_from_target: {type(e).__name__} - {e}")

            await asyncio.gather(
                forward_to_target(),
                forward_from_target()
            )
                
    except websockets.exceptions.InvalidURI as e:
        logger.error(f"Invalid target WebSocket URI: {target_ws_url}, error: {str(e)}")
        if websocket.client_state == WebSocketState.CONNECTED: await websocket.close(code=1011, reason="Invalid target URI")
        
    except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK) as e:
        logger.warning(f"Target WebSocket connection closed for {target_ws_url}: {str(e)}")
        if websocket.client_state == WebSocketState.CONNECTED: await websocket.close(code=1001, reason="Target closed connection")

    except websockets.exceptions.WebSocketException as e:
        logger.error(f"A WebSocket error occurred for {target_ws_url}: {str(e)}")
        if websocket.client_state == WebSocketState.CONNECTED: await websocket.close(code=1011, reason="WebSocket protocol error")

    except Exception as e:
        logger.exception(f"Code Server WebSocket proxy error for agent {agent_id} with path /{path}: {str(e)}")
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close(code=1011, reason="Internal server error")
            except Exception:
                pass 