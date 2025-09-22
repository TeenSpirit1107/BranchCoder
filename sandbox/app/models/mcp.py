"""
MCP Service Models
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum


class Language(str, Enum):
    """Supported MCP server languages"""
    PYTHON = "python"
    NODE = "node"


class McpInstallRequest(BaseModel):
    """Request model for installing MCP server"""
    pkg: str = Field(..., description="Package name from PyPI or npm")
    lang: Language = Field(default=Language.PYTHON, description="Programming language")
    args: Optional[List[str]] = Field(default=None, description="Additional installation arguments")


class McpInstallResponse(BaseModel):
    """Response model for MCP server installation"""
    status: Literal["ok", "error"] = Field(..., description="Installation status")
    message: Optional[str] = Field(None, description="Additional message")


class McpServerInfo(BaseModel):
    """Information about an MCP server"""
    pkg: str = Field(..., description="Package name")
    lang: Language = Field(..., description="Programming language")
    alive: bool = Field(..., description="Whether the server is alive")
    pid: Optional[int] = Field(None, description="Process ID")


class McpListResponse(BaseModel):
    """Response model for listing MCP servers"""
    servers: List[McpServerInfo] = Field(..., description="List of MCP servers")


class McpUninstallResponse(BaseModel):
    """Response model for uninstalling MCP server"""
    status: str = Field(..., description="Uninstallation status")
    message: Optional[str] = Field(None, description="Additional message")


class McpProxyResponse(BaseModel):
    """Response model for MCP proxy requests"""
    content: bytes = Field(..., description="Raw response content")
    media_type: str = Field(default="application/json", description="Media type")


class McpHealthResponse(BaseModel):
    """Response model for MCP server health check"""
    pkg: str = Field(..., description="Package name")
    alive: bool = Field(..., description="Whether the server is alive")
    uptime: Optional[float] = Field(None, description="Server uptime in seconds") 