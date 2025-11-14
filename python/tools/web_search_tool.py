#!/usr/bin/env python3
"""
Web search tools for ToolUniverse using DDGS (Dux Distributed Global Search).

This module provides web search capabilities using the ddgs library,
which supports multiple search engines including DuckDuckGo, Google, Bing, etc.
"""

import asyncio
from typing import Dict, Any, List, Optional

from duckduckgo_search import DDGS
from utils.logger import Logger
from tools.base_tool import MCPTool

logger = Logger('web_search_tool', log_to_file=False)


class WebSearchTool(MCPTool):
    """
    Web search tool using DDGS library.
    
    This tool performs web searches using the DDGS library which supports
    multiple search engines including Google, Bing, Brave, Yahoo, DuckDuckGo, etc.
    """
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "web_search"
    
    def __init__(self):
        """Initialize web search tool."""
        pass
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for information using DDGS. Use this to find current information, documentation, examples, or answers to questions that require up-to-date knowledge. Supports multiple search engines including Google, Bing, Brave, Yahoo, DuckDuckGo, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query string"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 10, max: 50)",
                            "default": 10
                        },
                        "search_type": {
                            "type": "string",
                            "description": "Type of search: 'general', 'api_documentation', 'python_packages', 'github' (default: 'general')",
                            "enum": ["general", "api_documentation", "python_packages", "github"],
                            "default": "general"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    
    def _search_with_ddgs(
        self,
        query: str,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Perform a web search using DDGS library and return formatted results.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
        
        Returns:
            List of search results with title, url, and snippet
        """
        try:
            # Create DDGS instance
            ddgs = DDGS()
            
            # Perform search using DDGS with fixed settings
            search_results = list(
                ddgs.text(
                    query=query,
                    max_results=max_results,
                    backend="google",
                    region="us-en",
                    safesearch="moderate",
                )
            )
            
            # Convert DDGS results to our expected format
            results = []
            for i, result in enumerate(search_results):
                results.append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("href", ""),
                        "snippet": result.get("body", ""),
                        "rank": i + 1,
                    }
                )
            
            return results
        except Exception as e:
            logger.error(f"Error in DDGS search: {e}", exc_info=True)
            return [
                {
                    "title": "Search Error",
                    "url": "",
                    "snippet": f"Failed to perform search: {str(e)}",
                    "rank": 0,
                }
            ]
    
    async def execute(
        self,
        query: str,
        max_results: int = 10,
        search_type: str = "general",
    ) -> Dict[str, Any]:
        """
        Execute web search using DDGS.
        
        Args:
            query: Search query string
            max_results: Maximum number of results (default: 10)
            search_type: Type of search (default: 'general')
        
        Returns:
            Dictionary containing search results
        """
        logger.info(f"Web search: {query} (type: {search_type})")
        
        try:
            query = query.strip()
            
            if not query:
                return {
                    "status": "error",
                    "error": "Query parameter is required",
                    "results": [],
                }
            
            # Validate max_results
            max_results = max(1, min(max_results, 50))  # Limit between 1-50
            
            # Modify query based on search type with enhanced formatting
            if search_type == "api_documentation":
                query = f'"{query}" API documentation official docs'
            elif search_type == "python_packages":
                query = f'"{query}" python package pypi install pip'
            elif search_type == "github":
                query = f"{query} site:github.com"
            
            # Run DDGS search in executor to avoid blocking
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self._search_with_ddgs,
                query,
                max_results,
            )
            
            # Filter results based on search type for better relevance
            if search_type == "python_packages":
                results = [
                    r
                    for r in results
                    if (
                        "pypi.org" in r.get("url", "")
                        or "python" in r.get("title", "").lower()
                    )
                ]
            elif search_type == "github":
                results = [
                    r for r in results if "github.com" in r.get("url", "")
                ]
            
            # Add rate limiting to be respectful
            await asyncio.sleep(0.5)
            
            return {
                "status": "success",
                "query": query,
                "search_type": search_type,
                "total_results": len(results),
                "results": results,
            }
        except Exception as e:
            logger.error(f"Error in web search: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "results": [],
            }
