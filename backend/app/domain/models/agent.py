from pydantic import BaseModel, Field
from typing import Optional
from app.domain.models.memory import Memory
from app.domain.models.environment import Environment
import uuid

class Agent(BaseModel):
    """Agent domain model."""
    
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    planner_memory: Memory
    execution_memory: Memory
    model_name: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    user_id: Optional[str] = None
    environment: Optional[Environment] = None
    
    def __init__(self, id: Optional[str] = None, **data):
        """初始化Agent，支持传入自定义ID
        
        Args:
            id: 可选的自定义ID，如果不提供则自动生成
            **data: 其他Agent属性
        """
        if id is not None:
            data['id'] = id
        super().__init__(**data)
