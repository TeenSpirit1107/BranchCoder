import logging
from typing import Optional

from openai import AsyncOpenAI

from app.infrastructure.config import get_settings

# 设置模块级别的日志记录器
logger = logging.getLogger(__name__)

class DeepSeekReasonLLM:
    """基于DeepSeek Reasoner的深度推理服务"""
    
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.reason_api_key
        self.api_base = settings.reason_api_base
        self.model_name = settings.reason_model_name
        
        if not self.api_key:
            raise ValueError("Reason API key is required")
        
        self.client = AsyncOpenAI(
            api_key=settings.reason_api_key,
            base_url=settings.reason_api_base
        )
        
        logger.info(f"Initialized Reason LLM with model: {self.model_name}")
    
    async def deep_reasoning(self, problem: str, context: Optional[str] = None) -> str:
        """
        进行深度推理分析
        
        Args:
            problem: 需要推理的问题
            context: 可选的上下文信息
            
        Returns:
            推理结果
        """
        try:
            # 构建推理提示词
            messages = [
                {"role": "system", "content": "你是一个有用的AI助手。请回答用户的问题。/think"},
                {"role": "user", "content": f"问题: {problem}\n上下文: {context}"},
            ]
            
            # 调用API
            response = await self.client.chat.completions.create(
                model=self.model_name,
                temperature=0.0,
                max_tokens=8000,
                messages=messages,
                extra_body={"enable_thinking": False},
                # response_format=response_format,
            )
            
            return response.choices[0].message
            
        except Exception as e:
            logger.exception(f"深度推理失败: {e}")
            raise
    