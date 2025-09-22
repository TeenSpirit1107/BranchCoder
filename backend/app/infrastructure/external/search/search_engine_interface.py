from abc import abstractmethod
from typing import Optional, Protocol

from app.domain.models.tool_result import ToolResult


class SearchEngineInterface(Protocol):
    """Interface for search engine implementations"""
    
    @abstractmethod
    async def search(
        self, 
        query: str, 
        date_range: Optional[str] = None
    ) -> ToolResult:
        """Search web pages using search engine
        
        Args:
            query: Search query
            date_range: (Optional) Time range filter for search results
            
        Returns:
            Search results wrapped in ToolResult
        """
        pass 