from typing import Dict, Any, List, Callable
import inspect
from app.domain.models.tool_result import ToolResult

def tool(
    name: str, 
    description: str,
    parameters: Dict[str, Dict[str, Any]],
    required: List[str]
) -> Callable:
    """Tool registration decorator
    
    Args:
        name: Tool name
        description: Tool description
        parameters: Tool parameter definitions
        required: List of required parameters
        
    Returns:
        Decorator function
    """
    def decorator(func):
        # Create tool schema directly using provided parameters, without automatic extraction
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object", 
                    "properties": parameters,
                    "required": required
                }
            }
        }
        
        # Store tool information
        func._function_name = name
        func._tool_description = description
        func._tool_schema = schema
        
        return func
    
    return decorator

class BaseTool:
    """Base tool class, providing common tool calling methods"""

    name: str = ""
    
    def __init__(self):
        """Initialize base tool class"""
        self._tools_cache = None
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        """Get all registered tools
        
        Returns:
            List of tools
        """
        if self._tools_cache is not None:
            return self._tools_cache
        
        tools = []
        for _, method in inspect.getmembers(self, inspect.ismethod):
            if hasattr(method, '_tool_schema'):
                tools.append(method._tool_schema)
        
        self._tools_cache = tools
        return tools
    
    async def has_function(self, function_name: str) -> bool:
        """Check if specified function exists
        
        Args:
            function_name: Function name
            
        Returns:
            Whether the tool exists
        """
        for _, method in inspect.getmembers(self, inspect.ismethod):
            if hasattr(method, '_function_name') and method._function_name == function_name:
                return True
        return False
    
    async def invoke_function(self, function_name: str, **kwargs) -> ToolResult:
        """Invoke specified tool
        
        Args:
            function_name: Function name
            **kwargs: Parameters
            
        Returns:
            Invocation result
            
        Raises:
            ValueError: Raised when tool doesn't exist
        """
        for _, method in inspect.getmembers(self, inspect.ismethod):
            if hasattr(method, '_function_name') and method._function_name == function_name:
                return await method(**kwargs)
        
        raise ValueError(f"Tool '{function_name}' not found") 