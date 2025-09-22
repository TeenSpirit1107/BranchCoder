"""Environment variables schemas for requests and responses."""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class EnvironmentVariablesSchema(BaseModel):
    """Schema for environment variables in API requests and responses."""
    
    variables: Dict[str, str] = Field(
        default_factory=dict,
        description="环境变量键值对，用于传递到沙盒容器",
        example={"PYTHON_PATH": "/usr/local/bin/python", "NODE_ENV": "production"}
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "variables": {
                    "PYTHON_PATH": "/usr/local/bin/python",
                    "NODE_ENV": "production",
                    "DEBUG": "true"
                }
            }
        } 