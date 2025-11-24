#!/usr/bin/env python3
"""
Fetch URL Tool - Fetch and extract text content from a webpage
"""

import re
from typing import Dict, Any, Optional

import aiohttp
from bs4 import BeautifulSoup
from utils.logger import Logger
from tools.base_tool import MCPTool

logger = Logger('fetch_url_tool', log_to_file=False)


class FetchUrlTool(MCPTool):
    """Tool for fetching and extracting text content from webpages."""
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "fetch_url"
    
    def __init__(self):
        """Initialize fetch URL tool."""
        pass
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "Fetch and extract text content from a webpage. Use this to get the actual content of a URL after searching the web.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to fetch and extract content from"
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "Maximum number of characters to extract (default: 8000)",
                            "default": 8000
                        }
                    },
                    "required": ["url"]
                }
            }
        }
    
    def get_call_notification(self, tool_args: Dict[str, Any]) -> Optional[str]:
        """
        Get custom notification for fetch URL tool call.
        
        Args:
            tool_args: Tool arguments containing 'url'
        
        Returns:
            Custom notification message string
        """
        url = tool_args.get("url", "")
        # Truncate long URLs for display
        display_url = url[:60] + "..." if len(url) > 60 else url
        return f"正在获取网页内容: {display_url}"
    
    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[str]:
        """
        Get custom notification for fetch URL tool result.
        
        Args:
            tool_result: Tool execution result
        
        Returns:
            Custom notification message string
        """
        if "error" in tool_result:
            error = tool_result.get("error", "未知错误")
            return f"获取网页内容失败: {error}"
        
        length = tool_result.get("length", 0)
        if length > 0:
            return f"成功获取网页内容，共{length}个字符"
        else:
            return "获取网页内容完成，但内容为空"
    
    async def execute(self, url: str, max_chars: int = 8000) -> Dict[str, Any]:
        """
        Fetch and extract text content from a webpage.
        
        Args:
            url: URL to fetch
            max_chars: Maximum number of characters to extract
        
        Returns:
            Dictionary with URL and extracted content
        """
        logger.info(f"Fetching URL: {url}")
        
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        }
        
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        logger.warning(f"HTTP {resp.status} for URL: {url}")
                        return {"url": url, "error": f"HTTP {resp.status}"}
                    
                    html = await resp.text(errors="ignore")
        
        except Exception as e:
            logger.error(f"Request failed for URL {url}: {e}", exc_info=True)
            return {"url": url, "error": f"Request failed: {e}"}
        
        # Parse HTML and extract text content
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Remove script, style, and navigation elements
            for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
                tag.decompose()
            
            # Extract text
            text = soup.get_text(separator="\n")
            
            # Clean up whitespace
            text = re.sub(r"\n{2,}", "\n", text)
            text = re.sub(r"[ \t]{2,}", " ", text)
            text = text.strip()
            
            # Truncate if needed
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
            
            logger.info(f"Extracted {len(text)} characters from URL: {url}")
            
            return {
                "url": url,
                "content": text,
                "length": len(text)
            }
        except Exception as e:
            logger.error(f"Error parsing HTML for URL {url}: {e}", exc_info=True)
            return {
                "url": url,
                "error": f"HTML parsing failed: {e}"
            }

