import json
import time
import asyncio
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from app.domain.external.llm import LLM
from app.domain.models.memory import Memory
from app.domain.services.tools.base import BaseTool
from app.domain.models.tool_result import ToolResult
from app.domain.models.event import (
    AgentEvent,
    ToolCallingEvent,
    ToolCalledEvent,
    ErrorEvent,
    MessageEvent,
    PauseEvent
)

import logging
from app.infrastructure.logging import setup_agent_logger
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base agent class, defining the basic behavior of the agent
    """

    system_prompt: str = ""
    format: Optional[str] = None
    max_iterations: int = 30
    max_retries: int = 3
    retry_interval: float = 2.0

    def __init__(self, memory: Memory, llm: LLM, tools: List[BaseTool] = []):
        self.memory = memory
        self.llm = llm
        self.memory.add_message({
            "role": "system", "content": self.system_prompt,
        })
        self.tools = tools
        self.logger = setup_agent_logger(self.__class__.__name__)
    
    async def get_available_tools(self) -> Optional[List[Dict[str, Any]]]:
        """Get all available tools list"""
        available_tools = []
        for tool in self.tools:
            available_tools.extend(await tool.get_tools())
        return available_tools
    
    async def get_tool(self, function_name: str) -> BaseTool:
        """Get specified tool"""
        for tool in self.tools:
            if await tool.has_function(function_name):
                return tool
        raise ValueError(f"Unknown tool: {function_name}")

    async def execute_tool(self, tool: BaseTool, function_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute specified tool, with retry mechanism and content length limiting"""

        retries = 0
        while retries <= self.max_retries:
            try:
                self.logger.info(f"Executing tool: {tool.name}, function: {function_name}, arguments: {arguments}")
                result = await tool.invoke_function(function_name, **arguments)
                
                # 限制工具结果内容长度
                try:
                    from app.domain.services.tools.context_manager import limit_tool_result_content
                    limited_result = limit_tool_result_content(result)
                    
                    # 如果内容被截断，记录日志
                    if limited_result != result:
                        self.logger.info(f"工具结果内容被截断以控制上下文长度: {tool.name}.{function_name}")
                    
                    return limited_result
                except ImportError:
                    # 如果上下文管理器不可用，返回原始结果
                    self.logger.warning("上下文管理器不可用，跳过工具结果长度限制")
                    return result
                    
            except Exception as e:
                last_error = str(e)
                retries += 1
                if retries <= self.max_retries:
                    await asyncio.sleep(self.retry_interval * retries)
                else:
                    break
        
        raise ValueError(f"Tool execution failed, retried {self.max_retries} times: {last_error}")
    
    async def execute(self, request: str) -> AsyncGenerator[AgentEvent, None]:
        self.logger.info(f"Executing request: {request}")
        message = await self.ask(request, self.format)
        for _ in range(self.max_iterations):
            if not message.tool_calls:
                break
            tool_responses = []
            logger.info(f"Tool calls: {message.tool_calls}")
            # 暂停：1. 向用户请求澄清 2. 向用户请求交付产物
            pause = False
            
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                tool_call_id = tool_call.id
                
                try:
                    tool = await self.get_tool(function_name)
                except ValueError as e:
                    self.logger.error(f"Error getting tool: {e}")
                    tool_response = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": f"Error getting tool: {e}. Review your avaliable tools and DO NOT use this tool again."
                    }
                    tool_responses.append(tool_response)
                    continue

                # Generate event before tool call
                yield ToolCallingEvent(
                    tool_name=tool.name,
                    function_name=function_name,
                    function_args=function_args
                )

                if function_name in [
                    "message_request_user_clarification", 
                    "message_done"
                ]:
                    pause = True

                try:
                    result = await self.execute_tool(tool, function_name, function_args)
                except Exception as e:
                    self.logger.exception(f"Tool execution failed: {e}")
                    tool_response = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": f"Tool execution failed: {e}."
                    }
                    tool_responses.append(tool_response)
                    continue

                # Generate event after tool call
                yield ToolCalledEvent(
                    tool_name=tool.name,
                    function_name=function_name,
                    function_args=function_args,
                    function_result=result
                )

                tool_response = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result.model_dump_json()
                }
                tool_responses.append(tool_response)

            # 确保所有工具响应都被添加到内存中
            if tool_responses:
                self.memory.add_messages(tool_responses)
            
            # 如果需要暂停，则暂停，不需要继续问LLM
            if pause:
                # 在暂停前，先返回工具执行结果
                if len(tool_responses) > 0:
                    last_response = tool_responses[-1]
                    try:
                        result_data = json.loads(last_response["content"])
                        if result_data.get("data"):
                            yield MessageEvent(message=str(result_data["data"]))
                    except:
                        pass
                yield PauseEvent()
                return
                
            # 继续询问LLM（不重复添加工具响应）
            if tool_responses:
                message = await self.ask_continue()
        
        if message.content:
            yield MessageEvent(message=message.content)
    
    async def ask_continue(self, format: Optional[str] = None) -> Dict[str, Any]:
        """继续对话，不添加新消息到内存"""
        response_format = None
        if format:
            response_format = {"type": format}

        self.logger.info(f"Asking LLM with messages: {self.memory.get_messages()}")
        message = await self.llm.ask(self.memory.get_messages(), 
                                     tools=(await self.get_available_tools()), 
                                     response_format=response_format)
        self.logger.info(f"Response: {message}")
        
        # [DEBUG 1] 检查OpenAI响应消息
        logger = logging.getLogger(__name__)
        logger.info(f"[DEBUG 1] BaseAgent收到LLM响应: type={type(message)}, content={getattr(message, 'content', 'N/A')}")
        logger.info(f"[DEBUG 1] 响应是否有工具调用: {bool(getattr(message, 'tool_calls', None))}")
        
        # 处理工具调用响应中的None content问题
        if hasattr(message, 'content') and message.content is None and hasattr(message, 'tool_calls') and message.tool_calls:
            logger.info(f"[DEBUG 1] 检测到工具调用响应，content为None，这是正常情况")
            # 为工具调用响应设置空的content，避免在Memory中产生错误
            if hasattr(message, '__dict__'):
                message.content = ""
                logger.info(f"[DEBUG 1] 已将工具调用响应的content从None修复为空字符串")
        
        if message.tool_calls:
            message.tool_calls = message.tool_calls[:1]
        self.memory.add_message(message)
        return message

    async def ask_with_messages(self, messages: List[Dict[str, Any]], format: Optional[str] = None) -> Dict[str, Any]:
        """添加消息到内存并继续对话"""
        self.memory.add_messages(messages)
        return await self.ask_continue(format)

    async def ask(self, request: str, format: Optional[str] = None) -> Dict[str, Any]:
        return await self.ask_with_messages([
            {
                "role": "user", "content": request
            }
        ], format)
    
    def roll_back(self):
        self.memory.roll_back()
    

