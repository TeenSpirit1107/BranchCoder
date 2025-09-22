import json
import logging
from typing import Dict, Any, List, Union

from app.domain.models.memory import Memory
from app.domain.models.tool_result import ToolResult

logger = logging.getLogger(__name__)

class ContextManager:
    """上下文长度管理器，用于控制消息和工具结果的长度"""
    
    # 默认配置
    DEFAULT_MAX_TOOL_CONTENT_TOKENS = 16000  # 工具返回内容最大token数
    DEFAULT_MAX_TOTAL_TOKENS = 128000  # 总上下文最大token数
    DEFAULT_PRESERVE_RECENT_MESSAGES = 10  # 保留最近消息数量
    
    # 估算token数的简单方法：1 token ≈ 4 字符（英文）或 1.5 字符（中文）
    CHARS_PER_TOKEN_EN = 4
    CHARS_PER_TOKEN_ZH = 1.5
    
    def __init__(self, 
                 max_tool_content_tokens: int = DEFAULT_MAX_TOOL_CONTENT_TOKENS,
                 max_total_tokens: int = DEFAULT_MAX_TOTAL_TOKENS,
                 preserve_recent_messages: int = DEFAULT_PRESERVE_RECENT_MESSAGES):
        """
        初始化上下文管理器
        
        Args:
            max_tool_content_tokens: 工具返回内容最大token数
            max_total_tokens: 总上下文最大token数
            preserve_recent_messages: 保留最近消息数量
        """
        self.max_tool_content_tokens = max_tool_content_tokens
        self.max_total_tokens = max_total_tokens
        self.preserve_recent_messages = preserve_recent_messages
        
    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的token数量
        
        Args:
            text: 要估算的文本
            
        Returns:
            估算的token数量
        """
        if not text:
            return 0
            
        # 简单的token估算：根据中英文字符比例
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        english_chars = len(text) - chinese_chars
        
        estimated_tokens = (
            chinese_chars / self.CHARS_PER_TOKEN_ZH + 
            english_chars / self.CHARS_PER_TOKEN_EN
        )
        
        return int(estimated_tokens)
    
    def truncate_text(self, text: str, max_tokens: int) -> str:
        """
        截断文本到指定token数量
        
        Args:
            text: 要截断的文本
            max_tokens: 最大token数
            
        Returns:
            截断后的文本
        """
        if not text:
            return text
            
        current_tokens = self.estimate_tokens(text)
        if current_tokens <= max_tokens:
            return text
            
        # 省略标记的token数
        ellipsis_text = "\n\n[内容因长度限制被截断...]"
        ellipsis_tokens = self.estimate_tokens(ellipsis_text)
        
        # 如果最大token数太小，无法容纳省略标记
        if max_tokens <= ellipsis_tokens:
            return ellipsis_text[:max(1, int(max_tokens * self.CHARS_PER_TOKEN_ZH))]
            
        # 计算实际可用于内容的token数
        available_tokens = max_tokens - ellipsis_tokens
        
        # 计算需要保留的字符比例
        ratio = available_tokens / current_tokens
        target_length = int(len(text) * ratio * 0.8)  # 留更多余量确保不超限
        
        if target_length <= 0:
            return ellipsis_text
            
        # 截断文本
        truncated = text[:target_length]
        
        # 尝试在合适的位置截断（避免截断到单词中间）
        if target_length < len(text):
            # 寻找最近的换行符或句号
            for delimiter in ['\n', '。', '.', '!', '?', '！', '？']:
                last_pos = truncated.rfind(delimiter)
                if last_pos > target_length * 0.6:  # 如果找到的位置不太远
                    truncated = truncated[:last_pos + 1]
                    break
        
        result = truncated + ellipsis_text
        
        # 确保结果不超过限制（如果仍然超过，进一步截断）
        result_tokens = self.estimate_tokens(result)
        if result_tokens > max_tokens:
            # 进一步减少内容长度
            excess_ratio = result_tokens / max_tokens
            new_target_length = int(len(truncated) / excess_ratio * 0.9)
            if new_target_length > 0:
                truncated = truncated[:new_target_length]
                result = truncated + ellipsis_text
        
        return result
    
    def limit_tool_result_content(self, tool_result: ToolResult) -> ToolResult:
        """
        限制工具结果内容的长度
        
        Args:
            tool_result: 工具执行结果
            
        Returns:
            长度受限的工具结果
        """
        if not tool_result:
            return tool_result
            
        # 创建新的工具结果对象
        limited_result = ToolResult(
            success=tool_result.success,
            message=tool_result.message,
            data=tool_result.data
        )
        
        # 限制message字段长度
        if limited_result.message:
            message_tokens = self.estimate_tokens(limited_result.message)
            if message_tokens > self.max_tool_content_tokens:
                limited_result.message = self.truncate_text(
                    limited_result.message, 
                    self.max_tool_content_tokens
                )
                logger.info(f"工具结果message被截断: {message_tokens} -> {self.estimate_tokens(limited_result.message)} tokens")
        
        # 限制data字段长度（如果是字符串类型）
        if limited_result.data:
            if isinstance(limited_result.data, str):
                data_tokens = self.estimate_tokens(limited_result.data)
                if data_tokens > self.max_tool_content_tokens:
                    limited_result.data = self.truncate_text(
                        limited_result.data,
                        self.max_tool_content_tokens
                    )
                    logger.info(f"工具结果data被截断: {data_tokens} -> {self.estimate_tokens(limited_result.data)} tokens")
            elif isinstance(limited_result.data, dict):
                # 对字典中的字符串值进行限制
                limited_result.data = self._limit_dict_content(limited_result.data)
            elif isinstance(limited_result.data, list):
                # 对列表中的内容进行限制
                limited_result.data = self._limit_list_content(limited_result.data)
        
        return limited_result
    
    def _limit_dict_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """限制字典内容的长度"""
        limited_data = {}
        total_tokens = 0
        
        for key, value in data.items():
            if isinstance(value, str):
                value_tokens = self.estimate_tokens(value)
                if value_tokens > self.max_tool_content_tokens // 4:  # 单个字段不超过总限制的1/4
                    value = self.truncate_text(value, self.max_tool_content_tokens // 4)
                    value_tokens = self.estimate_tokens(value)
                
                total_tokens += value_tokens
                if total_tokens > self.max_tool_content_tokens:
                    limited_data[key] = "[内容因长度限制被省略...]"
                    break
                else:
                    limited_data[key] = value
            elif isinstance(value, dict):
                limited_data[key] = self._limit_dict_content(value)
            elif isinstance(value, list):
                limited_data[key] = self._limit_list_content(value)
            else:
                limited_data[key] = value
        
        return limited_data
    
    def _limit_list_content(self, data: List[Any]) -> List[Any]:
        """限制列表内容的长度"""
        limited_data = []
        total_tokens = 0
        
        for item in data:
            if isinstance(item, str):
                item_tokens = self.estimate_tokens(item)
                if item_tokens > self.max_tool_content_tokens // 10:  # 单个列表项不超过总限制的1/10
                    item = self.truncate_text(item, self.max_tool_content_tokens // 10)
                    item_tokens = self.estimate_tokens(item)
                
                total_tokens += item_tokens
                if total_tokens > self.max_tool_content_tokens:
                    limited_data.append("[后续内容因长度限制被省略...]")
                    break
                else:
                    limited_data.append(item)
            elif isinstance(item, dict):
                limited_data.append(self._limit_dict_content(item))
            elif isinstance(item, list):
                limited_data.append(self._limit_list_content(item))
            else:
                limited_data.append(item)
        
        return limited_data
    
    def optimize_memory_context(self, memory: Memory) -> None:
        """
        优化Memory中的上下文长度
        
        Args:
            memory: 要优化的Memory对象
        """
        messages = memory.get_messages()
        if not messages:
            return
            
        # 计算当前总token数
        total_tokens = sum(self.estimate_tokens(self._message_to_text(msg)) for msg in messages)
        
        # 如果消息数量很多（超过20条）或者token数超限，都需要优化
        needs_optimization = total_tokens > self.max_total_tokens
        
        if not needs_optimization:
            return
            
        logger.info(f"上下文长度超限，开始优化: {total_tokens} tokens, {len(messages)} messages > {self.max_total_tokens} tokens")
        
        # 获取最新的系统消息
        latest_system = memory.get_latest_system_message()
        non_system_messages = memory.get_non_system_messages()
        
        # 如果非系统消息数量少于等于保留数量，不需要优化
        if len(non_system_messages) <= self.preserve_recent_messages:
            return
        
        # 保留最近的消息
        preserved_messages = non_system_messages[-self.preserve_recent_messages:]
        older_messages = non_system_messages[:-self.preserve_recent_messages]
        
        # 计算保留消息的token数
        preserved_tokens = sum(self.estimate_tokens(self._message_to_text(msg)) for msg in preserved_messages)
        system_tokens = self.estimate_tokens(self._message_to_text(latest_system)) if latest_system else 0
        
        # 计算可用于旧消息的token数
        available_tokens = max(100, self.max_total_tokens - preserved_tokens - system_tokens)
        
        # 压缩旧消息
        compressed_older = self._compress_messages(older_messages, available_tokens)
        
        # 重建消息列表
        new_messages = []
        if latest_system:
            new_messages.append(latest_system)
        new_messages.extend(compressed_older)
        new_messages.extend(preserved_messages)
        
        # 临时禁用自动优化，避免递归调用
        original_auto_optimize = memory.auto_optimize
        memory.auto_optimize = False
        
        try:
            # 更新Memory
            memory.clear_messages()
            memory.add_messages(new_messages)
        finally:
            # 恢复原始的自动优化设置
            memory.auto_optimize = original_auto_optimize
        
        new_total_tokens = sum(self.estimate_tokens(self._message_to_text(msg)) for msg in new_messages)
        logger.info(f"上下文优化完成: {len(messages)} -> {len(new_messages)} messages, {total_tokens} -> {new_total_tokens} tokens")
    
    def _message_to_text(self, message: Union[Dict[str, Any], Any]) -> str:
        """将消息转换为文本用于token计算"""
        if isinstance(message, dict):
            content = message.get('content', '')
            if isinstance(content, str):
                return content
            else:
                return json.dumps(content, ensure_ascii=False)
        else:
            # 处理ChatCompletionMessage等对象
            if hasattr(message, 'content'):
                content = message.content
                if isinstance(content, str):
                    return content
                else:
                    return json.dumps(content, ensure_ascii=False) if content else ""
            else:
                return str(message)
    
    def _get_message_role(self, message: Union[Dict[str, Any], Any]) -> str:
        """安全地获取消息的role"""
        if isinstance(message, dict):
            return message.get('role', '')
        else:
            # 处理ChatCompletionMessage等对象
            if hasattr(message, 'role'):
                return message.role
            else:
                return ''

    def _compress_messages(self, messages: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
        """
        压缩消息列表到指定token数内
        
        Args:
            messages: 要压缩的消息列表
            max_tokens: 最大token数
            
        Returns:
            压缩后的消息列表
        """
        if not messages or max_tokens <= 0:
            return []
        
        # 如果消息很少，直接返回
        if len(messages) <= 3:
            return messages
        
        # 计算当前token数
        current_tokens = sum(self.estimate_tokens(self._message_to_text(msg)) for msg in messages)
        
        if current_tokens <= max_tokens:
            return messages
        
        # 创建摘要消息
        summary_content = f"[历史对话摘要: 共{len(messages)}条消息被压缩，原始长度约{current_tokens}个token]"
        
        # 尝试保留一些关键消息（用户消息和重要的助手回复）
        key_messages = []
        for msg in messages[-6:]:  # 保留最后6条消息
            if self._get_message_role(msg) in ['user', 'assistant']:
                key_messages.append(msg)
        
        # 如果关键消息的token数仍然超限，进一步压缩
        key_tokens = sum(self.estimate_tokens(self._message_to_text(msg)) for msg in key_messages)
        summary_tokens = self.estimate_tokens(summary_content)
        
        if key_tokens + summary_tokens > max_tokens:
            # 进一步压缩关键消息
            available_for_key = max_tokens - summary_tokens
            key_messages = self._truncate_messages(key_messages, available_for_key)
        
        # 构建压缩后的消息列表
        compressed = [{"role": "system", "content": summary_content}]
        compressed.extend(key_messages)
        
        return compressed
    
    def _truncate_messages(self, messages: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
        """截断消息列表到指定token数"""
        if not messages:
            return []
        
        truncated = []
        current_tokens = 0
        
        # 从后往前添加消息，确保最新的消息被保留
        for msg in reversed(messages):
            msg_tokens = self.estimate_tokens(self._message_to_text(msg))
            
            if current_tokens + msg_tokens <= max_tokens:
                truncated.insert(0, msg)
                current_tokens += msg_tokens
            else:
                # 如果这是第一条消息且超限，尝试截断内容
                if not truncated and max_tokens > 100:
                    content = self._message_to_text(msg)
                    truncated_content = self.truncate_text(content, max_tokens - 50)
                    truncated_msg = msg.copy()
                    truncated_msg['content'] = truncated_content
                    truncated.insert(0, truncated_msg)
                break
        
        return truncated


# 创建全局实例
default_context_manager = ContextManager()


def limit_tool_result_content(tool_result: ToolResult) -> ToolResult:
    """
    限制工具结果内容长度的便捷函数
    
    Args:
        tool_result: 工具执行结果
        
    Returns:
        长度受限的工具结果
    """
    return default_context_manager.limit_tool_result_content(tool_result)


def optimize_memory_context(memory: Memory) -> None:
    """
    优化Memory上下文长度的便捷函数
    
    Args:
        memory: 要优化的Memory对象
    """
    default_context_manager.optimize_memory_context(memory)


def create_context_manager(max_tool_content_tokens: int = 16000,
                          max_total_tokens: int = 200000,
                          preserve_recent_messages: int = 10) -> ContextManager:
    """
    创建自定义配置的上下文管理器
    
    Args:
        max_tool_content_tokens: 工具返回内容最大token数
        max_total_tokens: 总上下文最大token数
        preserve_recent_messages: 保留最近消息数量
        
    Returns:
        配置好的上下文管理器实例
    """
    return ContextManager(
        max_tool_content_tokens=max_tool_content_tokens,
        max_total_tokens=max_total_tokens,
        preserve_recent_messages=preserve_recent_messages
    ) 