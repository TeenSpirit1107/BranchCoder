from typing import Optional
import logging
import httpx
from app.domain.models.tool_result import ToolResult
from app.infrastructure.external.search.search_engine_interface import SearchEngineInterface

logger = logging.getLogger(__name__)

class GoogleSearchEngine(SearchEngineInterface):
    """Google API based search engine implementation"""
    
    def __init__(self, api_key: str, cx: str):
        """Initialize Google search engine
        
        Args:
            api_key: Google Custom Search API key
            cx: Google Search Engine ID
        """
        self.api_key = api_key
        self.cx = cx
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        
    async def search(
        self, 
        query: str, 
        date_range: Optional[str] = None
    ) -> ToolResult:
        """Search web pages using Google API
        
        Args:
            query: Search query, Google search style, use 3-5 keywords
            date_range: (Optional) Time range filter for search results
            
        Returns:
            Search results
        """
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query
        }
        
        # Add time range filter
        if date_range and date_range != "all":
            # Convert date_range to time range parameters supported by Google API
            # For example: via dateRestrict parameter (d[number]: day, w[number]: week, m[number]: month, y[number]: year)
            date_mapping = {
                "past_hour": "d1",
                "past_day": "d1", 
                "past_week": "w1",
                "past_month": "m1",
                "past_year": "y1"
            }
            if date_range in date_mapping:
                params["dateRestrict"] = date_mapping[date_range]
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                # Process search results
                search_results = []
                if "items" in data:
                    for item in data["items"]:
                        search_results.append({
                            "title": item.get("title", ""),
                            "link": item.get("link", ""),
                            "snippet": item.get("snippet", ""),
                        })
                
                # Build return result
                results = {
                    "query": query,
                    "date_range": date_range,
                    "search_info": data.get("searchInformation", {}),
                    "results": search_results,
                    "total_results": data.get("searchInformation", {}).get("totalResults", "0")
                }
                
                return ToolResult(success=True, data=results)
                
        except Exception as e:
            logger.error(f"Google Search API call failed: {e}")
            return ToolResult(
                success=False,
                message=f"Google Search API call failed: {e}",
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
        # Get API key and search engine ID from environment variables
        # Make sure these environment variables are set
        api_key = os.environ.get("GOOGLE_API_KEY")
        cx = os.environ.get("GOOGLE_SEARCH_ENGINE_ID")
        
        if not api_key or not cx:
            print("Error: Please set environment variables GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID")
            return
        
        # Initialize search engine
        search_engine = GoogleSearchEngine(api_key=api_key, cx=cx)
        
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