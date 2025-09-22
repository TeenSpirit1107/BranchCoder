"""
FastMCP-based MCP API Routes

Provides HTTP endpoints for managing MCP servers using FastMCP Client.
Compatible with existing MCP API but uses FastMCP for improved reliability.
"""
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from typing import Dict, Any

from app.services.mcp_fastmcp import fastmcp_service
from app.models.mcp import (
    McpInstallRequest, McpInstallResponse,
    McpListResponse, McpUninstallResponse,
    McpHealthResponse
)
from app.core.exceptions import AppException, ResourceNotFoundException


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/install", response_model=McpInstallResponse)
async def install_mcp_server(request: McpInstallRequest) -> McpInstallResponse:
    """
    Install and start an MCP server using FastMCP.
    
    Args:
        request: Installation request with package name and language
        
    Returns:
        Installation response with status
        
    Raises:
        HTTPException: If installation fails
    """
    try:
        logger.info(f"Installing MCP server with FastMCP: {request.pkg} ({request.lang})")
        response = await fastmcp_service.install(request)
        logger.info(f"FastMCP server installation completed: {request.pkg}")
        return response
        
    except AppException as e:
        logger.error(f"FastMCP server installation failed: {e.message}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error during FastMCP installation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/uninstall/{pkg}", response_model=McpUninstallResponse)
async def uninstall_mcp_server(pkg: str) -> McpUninstallResponse:
    """
    Stop and remove an MCP server.
    
    Args:
        pkg: Package name to uninstall
        
    Returns:
        Uninstallation response with status
        
    Raises:
        HTTPException: If server not found or uninstallation fails
    """
    try:
        logger.info(f"Uninstalling FastMCP server: {pkg}")
        response = await fastmcp_service.uninstall(pkg)
        logger.info(f"FastMCP server uninstallation completed: {pkg}")
        return response
        
    except ResourceNotFoundException as e:
        logger.warning(f"FastMCP server not found: {e.message}")
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        logger.error(f"FastMCP server uninstallation failed: {e.message}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error during FastMCP uninstallation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/list", response_model=McpListResponse)
async def list_mcp_servers() -> McpListResponse:
    """
    List all registered MCP servers.
    
    Returns:
        List response with server information
        
    Raises:
        HTTPException: If listing fails
    """
    try:
        logger.debug("Listing FastMCP servers")
        response = await fastmcp_service.list_servers()
        logger.debug(f"Found {len(response.servers)} FastMCP servers")
        return response
        
    except Exception as e:
        logger.error(f"Failed to list FastMCP servers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/proxy/{pkg}")
async def proxy_mcp_request(pkg: str, request: Request) -> Response:
    """
    Proxy JSON-RPC request to MCP server using FastMCP.
    
    Args:
        pkg: Package name of target server
        request: HTTP request with JSON-RPC payload
        
    Returns:
        Raw JSON-RPC response
        
    Raises:
        HTTPException: If server not found or proxy fails
    """
    try:
        # Get raw request body
        payload = await request.body()
        
        if not payload:
            raise HTTPException(status_code=400, detail="Empty request body")
        
        logger.debug(f"Proxying request to FastMCP server: {pkg}")
        
        # Proxy to MCP server using FastMCP
        response_data = await fastmcp_service.proxy_request(pkg, payload)
        
        logger.debug(f"Received response from FastMCP server: {pkg}")
        
        # Return raw response with JSON content type
        return Response(
            content=response_data,
            media_type="application/json"
        )
        
    except ResourceNotFoundException as e:
        logger.warning(f"FastMCP server not found: {e.message}")
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        if "timeout" in e.message.lower():
            logger.error(f"FastMCP server timeout: {e.message}")
            raise HTTPException(status_code=504, detail=e.message)
        else:
            logger.error(f"FastMCP server error: {e.message}")
            raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error during FastMCP proxy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health/{pkg}", response_model=McpHealthResponse)
async def check_mcp_health(pkg: str) -> McpHealthResponse:
    """
    Check health of specific MCP server.
    
    Args:
        pkg: Package name to check
        
    Returns:
        Health response with status
        
    Raises:
        HTTPException: If server not found
    """
    try:
        logger.debug(f"Checking health of FastMCP server: {pkg}")
        response = await fastmcp_service.health_check(pkg)
        logger.debug(f"FastMCP server {pkg} health: alive={response.alive}")
        return response
        
    except ResourceNotFoundException as e:
        logger.warning(f"FastMCP server not found: {e.message}")
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        logger.error(f"Failed to check FastMCP server health: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/shutdown")
async def shutdown_all_mcp_servers() -> Dict[str, str]:
    """
    Shutdown all MCP servers.
    
    Returns:
        Shutdown status
        
    Raises:
        HTTPException: If shutdown fails
    """
    try:
        logger.info("Shutting down all FastMCP servers")
        await fastmcp_service.shutdown_all()
        logger.info("All FastMCP servers shutdown completed")
        return {"status": "ok", "message": "All FastMCP servers have been shutdown"}
        
    except Exception as e:
        logger.error(f"Failed to shutdown FastMCP servers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Additional FastMCP-specific endpoints

@router.get("/capabilities/{pkg}")
async def get_mcp_capabilities(pkg: str) -> Dict[str, Any]:
    """
    Get capabilities of specific MCP server using FastMCP.
    
    Args:
        pkg: Package name to check
        
    Returns:
        Server capabilities
        
    Raises:
        HTTPException: If server not found or capabilities check fails
    """
    try:
        logger.debug(f"Getting capabilities of FastMCP server: {pkg}")
        
        capabilities = await fastmcp_service.get_capabilities(pkg)
        
        return {
            "pkg": pkg,
            **capabilities
        }
        
    except ResourceNotFoundException as e:
        logger.warning(f"FastMCP server not found: {e.message}")
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        logger.error(f"Failed to get FastMCP server capabilities: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") 