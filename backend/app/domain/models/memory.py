from pydantic import BaseModel
from typing import List, Dict, Any, Union, Optional
from openai.types.chat import ChatCompletionMessage
from effimemo import ContextManager

class Memory(BaseModel):
    """
    Memory class, defining the basic behavior of memory
    """

    messages: List[Union[Dict[str, Any], ChatCompletionMessage]] = []
    file: List[Dict[str, Any]] = []
    web: List[Dict[str, Any]] = []
    # 工具使用历史
    tool_usage_history: List[Dict[str, Any]] = []
    # 上下文管理配置
    auto_optimize: bool = True  # 是否自动优化上下文长度
    max_total_tokens: int = 1000000  # 最大总token数
    preserve_recent_messages: int = 10  # 保留最近消息数量

    def to_dict(self) -> Dict[str, Any]:
        """将Memory对象序列化为字典"""
        # 将所有消息转换为字典格式
        serialized_messages = []
        for message in self.messages:
            if isinstance(message, ChatCompletionMessage):
                # 将ChatCompletionMessage转换为字典
                msg_dict = {
                    "role": message.role,
                    "content": message.content
                }
                # 添加其他可能的字段
                if hasattr(message, 'name') and message.name:
                    msg_dict["name"] = message.name
                if hasattr(message, 'function_call') and message.function_call:
                    msg_dict["function_call"] = message.function_call
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    msg_dict["tool_calls"] = message.tool_calls
                serialized_messages.append(msg_dict)
            else:
                # 已经是字典格式
                serialized_messages.append(message)
        
        return {
            "messages": serialized_messages,
            "auto_optimize": self.auto_optimize,
            "max_total_tokens": self.max_total_tokens,
            "preserve_recent_messages": self.preserve_recent_messages
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Memory":
        """从字典反序列化Memory对象"""
        if not data:
            return cls()
        
        return cls(
            messages=data.get("messages", []),
            auto_optimize=data.get("auto_optimize", True),
            max_total_tokens=data.get("max_total_tokens", 1000000),
            preserve_recent_messages=data.get("preserve_recent_messages", 10)
        )

    def get_message_role(self, message: Union[Dict[str, Any], ChatCompletionMessage]) -> str:
        """Get the role of the message"""
        if isinstance(message, dict):
            return message.get("role")
        elif isinstance(message, ChatCompletionMessage):
            return message.role
        return None

    def add_message(self, message: Union[Dict[str, Any], str]) -> None:
        """Add message to memory"""
        # 添加调试日志
        import logging
        logger = logging.getLogger(__name__)
        
        original_type = type(message).__name__
        logger.info(f"[DEBUG 1] 添加消息到内存，原始类型: {original_type}, 消息预览: {str(message)[:200]}")
        
        # 类型检查和自动转换
        if isinstance(message, str):
            # 如果传入的是字符串，自动转换为字典格式
            logger.debug(f"自动转换字符串消息: {message[:100]}...")
            message = {
                "role": "assistant",
                "content": message
            }
        elif not isinstance(message, dict):
            # 如果不是字符串也不是字典，尝试转换
            logger.warning(f"[DEBUG 1] 收到非标准消息类型: {original_type}，尝试转换")
            try:
                if hasattr(message, 'model_dump'):
                    # 处理Pydantic模型
                    message = message.model_dump()
                    logger.debug("使用model_dump转换成功")
                elif hasattr(message, '__dict__'):
                    # 处理普通对象
                    message = message.__dict__
                    logger.debug("使用__dict__转换成功")
                else:
                    # 最后的兜底转换
                    message = {
                        "role": "assistant",
                        "content": str(message)
                    }
                    logger.debug("使用str()兜底转换")
            except Exception as e:
                # 如果所有转换都失败，使用字符串表示
                logger.error(f"[DEBUG 1] 消息转换失败: {e}，使用兜底方案")
                message = {
                    "role": "assistant", 
                    "content": str(message)
                }
        
        # 检查最终消息的content是否为null
        content = message.get('content')
        if content is None:
            logger.error(f"[DEBUG 1] 检测到content为None! 消息: {message}")
            message['content'] = ""  # 设置为空字符串而不是None
        elif not isinstance(content, str):
            logger.warning(f"[DEBUG 1] content不是字符串类型: {type(content)}, 值: {content}")
            message['content'] = str(content)
        
        logger.info(f"[DEBUG 1] 最终消息格式: role={message.get('role')}, content_type={type(message.get('content'))}, content_length={len(str(message.get('content', '')))}")
        self.messages.append(message)
        
        # 自动优化上下文长度
        if self.auto_optimize:
            self._optimize_context_if_needed()
    
    def add_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Add messages to memory"""
        self.messages.extend(messages)
        
        # 自动优化上下文长度
        if self.auto_optimize:
            self._optimize_context_if_needed()

    def add_tool_usage(self, event: Any) -> None:
        """Add tool usage event to history"""
        try:
            # 处理 ToolCallingEvent 和 ToolCalledEvent
            if hasattr(event, 'type') and event.type in ['tool_calling', 'tool_called']:
                tool_usage = {
                    'type': event.type,
                    'tool_name': getattr(event, 'tool_name', ''),
                    'function_name': getattr(event, 'function_name', ''),
                    'function_args': getattr(event, 'function_args', {}),
                }
                
                if event.type == 'tool_called':
                    tool_usage['function_result'] = getattr(event, 'function_result', None)
                
                self.tool_usage_history.append(tool_usage)
        except Exception:
            # 如果出错，静默忽略
            pass

    def get_tool_history(self) -> str:
        """Get formatted tool usage history"""
        if not self.tool_usage_history:
            return "No tool usage history available."
        
        history_lines = []
        for usage in self.tool_usage_history:
            if usage['type'] == 'tool_calling':
                history_lines.append(
                    f"Tool Call: {usage['tool_name']}.{usage['function_name']}({usage['function_args']})"
                )
            elif usage['type'] == 'tool_called':
                history_lines.append(
                    f"Tool Result: {usage['tool_name']}.{usage['function_name']} -> {usage.get('function_result', 'No result')}"
                )
        
        return "\n".join(history_lines)

    def _optimize_context_if_needed(self) -> None:
        """如果需要，优化上下文长度"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[DEBUG 4] 开始上下文优化，当前消息数量: {len(self.messages)}")
        
        try:
            # 在压缩前确保所有消息都是字典格式
            cleaned_messages = []
            for i, msg in enumerate(self.messages):
                logger.debug(f"[DEBUG 4] 处理消息 {i}: type={type(msg)}, preview={str(msg)[:100]}")
                if isinstance(msg, dict):
                    # 检查字典消息的content字段
                    if 'content' in msg and msg['content'] is None:
                        logger.error(f"[DEBUG 4] 在消息 {i} 中发现content为None: {msg}")
                        msg['content'] = ""
                    cleaned_messages.append(msg)
                elif isinstance(msg, str):
                    # 自动转换字符串消息
                    cleaned_messages.append({
                        "role": "assistant",
                        "content": msg
                    })
                else:
                    # 处理其他类型的消息
                    try:
                        if hasattr(msg, 'model_dump'):
                            converted = msg.model_dump()
                            logger.debug(f"[DEBUG 4] 使用model_dump转换消息 {i}")
                        elif hasattr(msg, '__dict__'):
                            converted = msg.__dict__
                            logger.debug(f"[DEBUG 4] 使用__dict__转换消息 {i}")
                        else:
                            converted = {
                                "role": "assistant",
                                "content": str(msg)
                            }
                            logger.debug(f"[DEBUG 4] 使用str()转换消息 {i}")
                        
                        # 检查转换后的content
                        if 'content' in converted and converted['content'] is None:
                            logger.error(f"[DEBUG 4] 转换后的消息 {i} content为None: {converted}")
                            converted['content'] = ""
                        
                        cleaned_messages.append(converted)
                    except Exception as e:
                        # 最后的兜底处理
                        logger.error(f"[DEBUG 4] 消息 {i} 转换失败: {e}")
                        cleaned_messages.append({
                            "role": "assistant",
                            "content": str(msg)
                        })
            
            # 更新消息列表
            logger.info(f"[DEBUG 4] 消息清理完成，清理前: {len(self.messages)}, 清理后: {len(cleaned_messages)}")
            self.messages = cleaned_messages
            
            # 进行压缩
            manager = ContextManager(
                max_tokens=self.max_total_tokens,
                model_name="gpt-4.1",
                strategy="first",
                preserve_system=True
            )
            logger.info(f"[DEBUG 4] 开始压缩，压缩前消息数量: {len(self.messages)}")
            self.messages = manager.compress(self.messages)
            logger.info(f"[DEBUG 4] 压缩完成，压缩后消息数量: {len(self.messages)}")
            
            # 最终验证所有消息的content字段
            for i, msg in enumerate(self.messages):
                if isinstance(msg, dict) and 'content' in msg and msg['content'] is None:
                    logger.error(f"[DEBUG 4] 压缩后消息 {i} content仍为None: {msg}")
                    msg['content'] = ""
            
        except Exception as e:
            # 如果压缩失败，记录错误但不中断程序
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"上下文优化失败，跳过压缩: {e}")
            logger.warning(f"[DEBUG 4] 上下文优化失败，跳过压缩: {e}")
            # 确保消息格式正确
            cleaned_messages = []
            for msg in self.messages:
                if isinstance(msg, dict):
                    if 'content' in msg and msg['content'] is None:
                        logger.error(f"[DEBUG 4] 兜底处理中发现content为None: {msg}")
                        msg['content'] = ""
                    cleaned_messages.append(msg)
                else:
                    cleaned_messages.append({
                        "role": "assistant",
                        "content": str(msg)
                    })
            self.messages = cleaned_messages
            logger.info(f"[DEBUG 4] 兜底处理完成，最终消息数量: {len(self.messages)}")

    def get_messages(self) -> List[Dict[str, Any]]:
        """Get all message history"""
        import logging
        logger = logging.getLogger(__name__)
        
        # [DEBUG 3] 最终验证所有消息
        logger.info(f"[DEBUG 3] get_messages调用，消息总数: {len(self.messages)}")
        validated_messages = []
        
        for i, msg in enumerate(self.messages):
            if isinstance(msg, dict):
                content = msg.get('content')
                if content is None:
                    logger.error(f"[DEBUG 3] get_messages中检测到消息 {i} content为None: {msg}")
                    # 修复None content
                    msg = msg.copy()  # 避免修改原始消息
                    msg['content'] = ""
                elif not isinstance(content, str):
                    logger.warning(f"[DEBUG 3] get_messages中消息 {i} content不是字符串: {type(content)}")
                    msg = msg.copy()
                    msg['content'] = str(content)
                validated_messages.append(msg)
            else:
                logger.error(f"[DEBUG 3] get_messages中检测到非字典消息 {i}: {type(msg)}, 内容: {msg}")
                # 转换为标准格式
                validated_messages.append({
                    "role": "assistant",
                    "content": str(msg)
                })
        
        logger.info(f"[DEBUG 3] get_messages完成验证，返回 {len(validated_messages)} 条消息")
        return validated_messages

    def get_latest_system_message(self) -> Dict[str, Any]:
        """Get the latest system message"""
        for message in reversed(self.messages):
            if self.get_message_role(message) == "system":
                return message
        return {}

    def get_non_system_messages(self) -> List[Dict[str, Any]]:
        """Get all non-system messages"""
        return [message for message in self.messages if self.get_message_role(message) != "system"]

    def get_messages_with_latest_system(self) -> List[Dict[str, Any]]:
        """Get all non-system messages plus the latest system message"""
        latest_system = self.get_latest_system_message()
        non_system_messages = self.get_non_system_messages()
        if latest_system:
            return [latest_system] + non_system_messages
        return non_system_messages
    
    def clear_messages(self) -> None:
        """Clear memory"""
        self.messages = []
    
    def get_filtered_messages(self) -> List[Dict[str, Any]]:
        """Get all non-system and non-tool response messages, plus the latest system message"""
        latest_system = self.get_latest_system_message()
        messages = [message for message in self.messages 
                  if self.get_message_role(message) != "system"]
                  #and self.get_message_role(message) != "tool"]
        if latest_system:
            return [latest_system] + messages
        return messages

    def roll_back(self) -> None:
        """Roll back memory"""
        if len(self.messages) > 1 and \
                self.get_message_role(self.messages[-1]) == "tool" and \
                self.get_message_role(self.messages[-2]) != "tool":
            self.messages.pop()
        elif len(self.messages) > 0 and self.get_message_role(self.messages[-1]) == "user":
            self.messages.pop()
    
    def set_context_config(self, 
                          auto_optimize: Optional[bool] = None,
                          max_total_tokens: Optional[int] = None,
                          preserve_recent_messages: Optional[int] = None) -> None:
        """
        设置上下文管理配置
        
        Args:
            auto_optimize: 是否自动优化上下文长度
            max_total_tokens: 最大总token数
            preserve_recent_messages: 保留最近消息数量
        """
        if auto_optimize is not None:
            self.auto_optimize = auto_optimize
        if max_total_tokens is not None:
            self.max_total_tokens = max_total_tokens
        if preserve_recent_messages is not None:
            self.preserve_recent_messages = preserve_recent_messages

    def add_file(self, file_info: Optional[List[Dict[str, Any]]]) -> None:
        """Add file information to memory"""
        if file_info is None:
            return
        self.file.extend(file_info)

    def add_web(self, web_info: Optional[List[Dict[str, Any]]]) -> None:
        """Add web information to memory"""
        if web_info is None:
            return
        self.web.extend(web_info)