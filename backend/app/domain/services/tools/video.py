from typing import Dict, Any
import logging
from app.domain.services.tools.base import BaseTool
from app.domain.external.sandbox import Sandbox
from app.domain.external.llm import VideoLLM
from app.domain.services.tools.base import tool

logger = logging.getLogger(__name__)

class VideoTool(BaseTool):
    """视频分析工具"""

    name: str = "video"
    
    def __init__(self, sandbox: Sandbox, video_llm: VideoLLM):
        """Initialize video tool class
        
        Args:
            sandbox: Sandbox service
            video_llm: Video LLM service
        """
        super().__init__()
        self.sandbox = sandbox
        self.video_llm = video_llm
    
    @tool(
        name="analyze_video",
        description="Analyze video content. Use for analyzing Youtube video content.",
        parameters={
            "video_path": {
                "type": "string",
                "description": "Youtube video URL"
            },
            "query": {
                "type": "string",
                "description": "Query for video details or content"
            }
        },
        required=["video_path", "query"]
    )
    async def analyze_video(self, video_path: str, query: str) -> str:
        """
        分析视频内容
        
        Args:
            video_path: 视频文件路径或URL
            query: 关于视频的问题，如果为None则返回视频描述
            
        Returns:
            视频分析结果
        """
        try:
            logger.info(f"开始分析视频: {video_path}")
            
            # 如果没有提供查询，使用默认的描述查询
            if not query:
                query = "请详细描述这个视频的内容，包括视觉元素、动作、场景、人物等。"
            
            # 判断是否为网络URL
            if video_path.startswith('http://') or video_path.startswith('https://'):
                # 网络视频URL，直接传递给VideoLLM
                result = await self.video_llm.ask_video(video_path, query)
            else:
                # 本地文件路径，需要转换为沙盒内的绝对路径
                if not video_path.startswith('/'):
                    # 相对路径，转换为绝对路径
                    video_path = f"/home/ubuntu/{video_path}"
                
                # 检查文件是否存在
                file_exists_result = await self.sandbox.file_exists(video_path)
                if not file_exists_result.success:
                    raise FileNotFoundError(f"视频文件不存在: {video_path}")
                
                # 调用VideoLLM分析视频
                result = await self.video_llm.ask_video(video_path, query)
            
            logger.info(f"视频分析完成，结果长度: {len(result)}")
            return result
            
        except Exception as e:
            error_msg = f"视频分析失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    @tool(
        name="video_to_text",
        description="Transcribe video content. Use for transcribing Youtube video content.",
        parameters={
            "video_path": {
                "type": "string",
                "description": "Youtube video URL"
            },
        },
        required=["video_path"]
    )
    async def video_to_text(self, video_path: str) -> str:
        """
        获取视频的详细描述
        
        Args:
            video_path: 视频文件路径或URL
            
        Returns:
            视频描述
        """
        try:
            logger.info(f"开始描述视频: {video_path}")
            
            # 判断是否为网络URL
            if video_path.startswith('http://') or video_path.startswith('https://'):
                # 网络视频URL
                result = await self.video_llm.video_to_text(video_path)
            else:
                # 本地文件路径
                if not video_path.startswith('/'):
                    video_path = f"/home/ubuntu/{video_path}"
                
                file_exists_result = await self.sandbox.file_exists(video_path)
                if not file_exists_result.success:
                    raise FileNotFoundError(f"视频文件不存在: {video_path}")
                
                result = await self.video_llm.video_to_text(video_path)
            
            logger.info(f"视频描述完成，结果长度: {len(result)}")
            return result
            
        except Exception as e:
            error_msg = f"视频描述失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg) 