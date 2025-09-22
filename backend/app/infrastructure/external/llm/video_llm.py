import logging
import mimetypes
import os

import httpx

from app.infrastructure.config import get_settings

# 设置模块级别的日志记录器
logger = logging.getLogger(__name__)

class GeminiVideoLLM:
    """基于Gemini API的视频分析服务"""
    
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.video_api_key
        self.api_base = settings.video_api_base
        self.model_name = settings.video_model_name
        
        if not self.api_key:
            raise ValueError("Video API key is required")
        
        self.client = httpx.AsyncClient(
            timeout=300.0  # 视频处理需要更长时间
        )
        
        logger.info(f"Initialized Video LLM with model: {self.model_name}")
    
    async def upload_file_to_gemini(self, file_path: str) -> str:
        """上传文件到Gemini API并返回文件URI"""
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 获取文件MIME类型
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "video/mp4"  # 默认为mp4
            
            logger.info(f"正在上传文件: {file_path}, 类型: {mime_type}")
            
            # 读取文件
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # 准备上传请求
            upload_url = f"{self.api_base}/upload/v1beta/files?key={self.api_key}"
            
            # 第一步：开始上传
            headers = {
                'X-Goog-Upload-Protocol': 'resumable',
                'X-Goog-Upload-Command': 'start',
                'X-Goog-Upload-Header-Content-Length': str(len(file_data)),
                'X-Goog-Upload-Header-Content-Type': mime_type,
                'Content-Type': 'application/json'
            }
            
            metadata = {
                'file': {
                    'display_name': os.path.basename(file_path)
                }
            }
            
            response = await self.client.post(upload_url, headers=headers, json=metadata)
            
            if response.status_code != 200:
                logger.error(f"开始上传失败: {response.status_code}, {response.text}")
                raise Exception(f"API request failed: {response.status_code}")
            
            # 获取上传URL
            upload_session_url = response.headers.get('X-Goog-Upload-URL')
            if not upload_session_url:
                raise Exception("未获取到上传URL")
            
            # 第二步：上传文件数据
            upload_headers = {
                'Content-Length': str(len(file_data)),
                'X-Goog-Upload-Offset': '0',
                'X-Goog-Upload-Command': 'upload, finalize'
            }
            
            upload_response = await self.client.post(
                upload_session_url, 
                headers=upload_headers, 
                content=file_data
            )
            
            if upload_response.status_code != 200:
                logger.error(f"文件上传失败: {upload_response.status_code}, {upload_response.text}")
                raise Exception(f"File upload failed: {upload_response.status_code}")
            
            # 解析响应获取文件URI
            file_info = upload_response.json()
            file_uri = file_info.get('file', {}).get('uri')
            
            if file_uri:
                logger.info(f"文件上传成功! URI: {file_uri}")
                return file_uri
            else:
                raise Exception("上传成功但未获取到文件URI")
                
        except Exception as e:
            logger.exception(f"上传文件时出错: {e}")
            raise
    
    async def analyze_video_with_gemini_api(self, file_uri: str, query: str) -> str:
        """使用Gemini API分析视频"""
        try:
            url = f"{self.api_base}/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            data = {
                "contents": [
                    {
                        "parts": [
                            {
                                "fileData": {
                                    "mimeType": "video/mp4",
                                    "fileUri": file_uri
                                }
                            },
                            {
                                "text": query
                            }
                        ]
                    }
                ]
            }
            
            logger.info("正在分析视频内容...")
            response = await self.client.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                result = response.json()
                
                if 'candidates' in result and len(result['candidates']) > 0:
                    content = result['candidates'][0]['content']['parts'][0]['text']
                    return content
                else:
                    logger.error("API返回了空结果")
                    raise Exception("API返回了空结果")
            else:
                logger.error(f"API请求失败: {response.status_code}, {response.text}")
                raise Exception(f"API request failed: {response.status_code}")
                
        except Exception as e:
            logger.exception(f"分析视频时出错: {e}")
            raise
    
    async def video_to_text(self, video_uri: str) -> str:
        """将视频转换为文本描述"""
        query = "请详细描述这个视频的内容，包括视觉元素、动作、场景等。"
        return await self.analyze_video_with_gemini_api(video_uri, query)
    
    async def ask_video(self, video_uri: str, query: str) -> str:
        """对视频进行问答分析"""
        return await self.analyze_video_with_gemini_api(video_uri, query)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
