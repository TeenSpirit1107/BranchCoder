"""Environment variable domain model."""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class Environment(BaseModel):
    """Environment variables domain model."""
    
    variables: Dict[str, str] = Field(default_factory=dict, description="环境变量键值对")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, str]:
        """
        Convert environment variables to dictionary.
        
        Returns:
            Dictionary of environment variables
        """
        return self.variables.copy()
    
    @classmethod
    def from_dict(cls, variables: Dict[str, str], user_id: Optional[str] = None, agent_id: Optional[str] = None) -> "Environment":
        """
        Create Environment instance from dictionary.
        
        Args:
            variables: Dictionary of environment variables
            user_id: Optional user ID associated with these environment variables
            agent_id: Optional agent ID associated with these environment variables
            
        Returns:
            Environment instance
        """
        return cls(variables=variables, user_id=user_id, agent_id=agent_id) 