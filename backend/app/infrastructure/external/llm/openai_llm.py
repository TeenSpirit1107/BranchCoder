from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from app.infrastructure.config import get_settings
import logging

# 设置模块级别的日志记录器
logger = logging.getLogger(__name__)

class OpenAILLM:
    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base
        )
        
        self.model_name = settings.model_name
        self.temperature = settings.temperature
        self.max_tokens = settings.max_tokens
        logger.info(f"Initialized OpenAI LLM with model: {self.model_name}")
    
    async def ask(self, messages: List[Dict[str, str]], 
                            tools: Optional[List[Dict[str, Any]]] = None,
                            response_format: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send chat request to OpenAI API"""
        # [DEBUG 3] 验证消息格式
        logger.info(f"[DEBUG 3] 准备发送到OpenAI API，消息数量: {len(messages)}")
        for i, msg in enumerate(messages):
            content = msg.get('content')
            role = msg.get('role')
            logger.info(f"[DEBUG 3] 消息 {i}: role={role}, content_type={type(content)}, content_is_none={content is None}")
            if content is None:
                logger.error(f"[DEBUG 3] 检测到消息 {i} content为None! 完整消息: {msg}")
                # 修复None content
                msg['content'] = ""
                logger.info(f"[DEBUG 3] 已将消息 {i} 的None content修复为空字符串")
            elif not isinstance(content, str):
                logger.warning(f"[DEBUG 3] 消息 {i} content不是字符串: {type(content)}, 值: {content}")
                msg['content'] = str(content)
                logger.info(f"[DEBUG 3] 已将消息 {i} content转换为字符串")
        
        response = None
        try:
            if tools:
                logger.debug(f"Sending request to OpenAI with tools, model: {self.model_name}")
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    messages=messages,
                    tools=tools,
                    # response_format=response_format,
                )
            else:
                logger.debug(f"Sending request to OpenAI without tools, model: {self.model_name}")
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    messages=messages,
                    # response_format=response_format
                )
            logger.info(f"OpenAI response: {response}")
            return response.choices[0].message
        except Exception as e:
            logger.error(f"[DEBUG 3] OpenAI API调用失败: {str(e)}")
            logger.error(f"[DEBUG 3] 发送的消息详情: {messages}")
            raise

    async def custom_ask(
            self,
            messages: List[Dict[str, str]],
            tools: Optional[List[Dict[str, Any]]] = None,
            model: Optional[str] = None,
            temperature: Optional[float] = 0.1,
    ) -> Dict[str, Any]:
        try:
            if tools:
                logger.debug(f"Sending request to OpenAI with tools, model: {self.model_name}")
                response = await self.client.chat.completions.create(
                    model=model,
                    # temperature=temperature,
                    # max_completion_tokens=self.max_tokens,
                    messages=messages,
                    tools=tools,
                    # response_format=response_format,
                )
            else:
                logger.debug(f"Sending request to OpenAI without tools, model: {self.model_name}")
                response = await self.client.chat.completions.create(
                    model=model,
                    # temperature=temperature,
                    # max_completion_tokens=self.max_tokens,
                    messages=messages,
                    # response_format=response_format
                )
            logger.info(f"OpenAI response: {response}")
            return response.choices[0].message
        except Exception as e:
            logger.error(f"[DEBUG 3] OpenAI API调用失败: {str(e)}")
            logger.error(f"[DEBUG 3] 发送的消息详情: {messages}")
            raise

class OpenAIImageLLM(OpenAILLM):
    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.image_api_key,
            base_url=settings.image_api_base
        )
        
        self.model_name = settings.image_model_name
        self.temperature = settings.temperature
        self.max_tokens = settings.max_tokens
        logger.info(f"Initialized OpenAI Image LLM with model: {self.model_name}")
