from typing import Optional
import logging
import httpx
from app.domain.models.tool_result import ToolResult
from app.infrastructure.external.search.search_engine_interface import SearchEngineInterface

logger = logging.getLogger(__name__)

class SearXNGSearchEngine(SearchEngineInterface):
    """SearXNG API based search engine implementation"""
    
    def __init__(self, base_url: str):
        """Initialize SearXNG search engine
        
        Args:
            base_url: SearXNG instance URL (e.g., "https://searx.example.org")
        """
        self.base_url = base_url
        self.search_endpoint = f"{self.base_url}/search"
        # google,google scholar,arxiv,wikipedia
        self.engines = ["google", "google scholar", "arxiv", "wikipedia"]
        
    async def search(
        self, 
        query: str, 
        date_range: Optional[str] = None
    ) -> ToolResult:
        """Search web pages using SearXNG
        
        Args:
            query: Search query
            date_range: (Optional) Time range filter for search results
            
        Returns:
            Search results
        """
        params = {
            "q": query,
            "format": "json",
            "engines": ",".join(self.engines)
        }
        
        # Add time range filter if specified
        if date_range and date_range != "all":
            # Convert date_range to the format used by SearXNG
            date_mapping = {
                "past_hour": "hour",
                "past_day": "day", 
                "past_week": "week",
                "past_month": "month",
                "past_year": "year"
            }
            if date_range in date_mapping:
                params["time_range"] = date_mapping[date_range]
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.search_endpoint, params=params)
                response.raise_for_status()
                data = response.json()
                
                # Process search results
                search_results = []
                if "results" in data:
                    for item in data["results"]:
                        search_results.append({
                            "title": item.get("title", ""),
                            "link": item.get("url", ""),
                            "snippet": item.get("content", ""),
                        })
                
                # Build return result
                results = {
                    "query": query,
                    "date_range": date_range,
                    "search_info": {
                        "time": data.get("search_time", 0),
                        "engines": data.get("engines", [])
                    },
                    "results": search_results,
                    "total_results": len(search_results)
                }
                
                return ToolResult(success=True, data=results)
                
        except Exception as e:
            logger.error(f"SearXNG Search API call failed: {e}")
            return ToolResult(
                success=False,
                message=f"SearXNG Search API call failed: {e}",
                data={
                    "query": query,
                    "date_range": date_range,
                    "results": []
                }
            )


# If this file is run directly, execute the test
if __name__ == "__main__":
    import asyncio
    import os
    
    async def main():
        # Get SearXNG instance URL from environment variable
        # Make sure this environment variable is set
        searxng_url = os.environ.get("SEARXNG_URL")
        
        if not searxng_url:
            print("Error: Please set environment variable SEARXNG_URL")
            return
        
        # Initialize search engine
        search_engine = SearXNGSearchEngine(base_url=searxng_url)
        
        # Test query
        query = "artificial intelligence latest developments"
        
        # Execute search
        print(f"Searching: {query}")
        result = await search_engine.search(query=query)
        
        if not result.success:
            print(f"Search failed: {result.message}")
            return
            
        results = result.data
        
        # Print results
        print("\nSearch results summary:")
        print(f"Query: {results['query']}")
        print(f"Total results: {results['total_results']}")
        
        # Print first 3 results
        print("\nFirst 3 search results:")
        for i, result_item in enumerate(results.get('results', [])[:3], 1):
            print(f"\nResult {i}:")
            print(f"Title: {result_item['title']}")
            print(f"Link: {result_item['link']}")
            print(f"Snippet: {result_item['snippet']}")
        
        # Test search with time range
        date_range = "past_week"
        print(f"\n\nSearching with time range: {date_range}")
        time_result = await search_engine.search(query=query, date_range=date_range)
        
        if not time_result.success:
            print(f"Search failed: {time_result.message}")
            return
            
        time_results = time_result.data
        
        # Print time range search results
        print("\nTime range search results summary:")
        print(f"Query: {time_results['query']}")
        print(f"Time range: {time_results['date_range']}")
        print(f"Total results: {time_results['total_results']}")
        
        print("\nFirst 3 time range search results:")
        for i, result_item in enumerate(time_results.get('results', [])[:3], 1):
            print(f"\nResult {i}:")
            print(f"Title: {result_item['title']}")
            print(f"Link: {result_item['link']}")
            print(f"Snippet: {result_item['snippet']}")

    # Run main function
    asyncio.run(main()) 