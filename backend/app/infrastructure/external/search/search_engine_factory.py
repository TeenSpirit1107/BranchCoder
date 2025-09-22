import logging
from app.infrastructure.config import get_settings
from app.infrastructure.external.search.search_engine_interface import SearchEngineInterface
from app.infrastructure.external.search.google_search import GoogleSearchEngine
from app.infrastructure.external.search.searxng_search import SearXNGSearchEngine

logger = logging.getLogger(__name__)

def create_search_engine() -> SearchEngineInterface:
    """创建搜索引擎实例
    
    根据配置选择合适的搜索引擎实现。
    
    Returns:
        SearchEngineInterface: 搜索引擎实例
        
    Raises:
        ValueError: 配置错误或缺少必要的配置项
    """
    settings = get_settings()
    
    # 根据配置选择搜索引擎类型
    if settings.search_engine_type == "google":
        # 检查必要的Google搜索配置项
        if not settings.google_search_api_key or not settings.google_search_engine_id:
            raise ValueError("使用Google搜索引擎需要设置google_search_api_key和google_search_engine_id")
        
        logger.info("使用Google搜索引擎")
        return GoogleSearchEngine(
            api_key=settings.google_search_api_key,
            cx=settings.google_search_engine_id
        )
    
    elif settings.search_engine_type == "searxng":
        # 检查必要的SearXNG搜索配置项
        if not settings.searxng_url:
            raise ValueError("使用SearXNG搜索引擎需要设置searxng_url")
        
        logger.info("使用SearXNG搜索引擎")
        return SearXNGSearchEngine(
            base_url=settings.searxng_url
        )
    
    else:
        raise ValueError(f"不支持的搜索引擎类型: {settings.search_engine_type}") 