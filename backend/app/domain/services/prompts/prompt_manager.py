from enum import Enum
import os
import re
import uuid
from datetime import datetime
from typing import List

from app.domain.services.agents.base import BaseAgent
import logging

from app.domain.services.prompts.execution_no_tool import EXECUTION_SYSTEM_PROMPT_NO_TOOL
from app.domain.services.prompts.sub_planner_no_tool import SUB_PLANNER_SYSTEM_PROMPT_NO_TOOL
from app.domain.services.prompts.code_sub_planner_prompt import CODE_SUB_PLANNER_SYSTEM_PROMPT_NO_TOOL
from app.domain.services.prompts.code_sub_planner_prompt import *
import app.domain.services.prompts.execution_tools as execution_tools
import app.domain.services.prompts.sub_planner_tools as sub_planner_tools

from app.domain.services.tools.base import BaseTool
from app.domain.services.tools import ShellTool, SearchTool, FileTool, MessageTool, McpTool
from app.domain.models.memory import Memory

logger = logging.getLogger(__name__)

class SubPlannerType(str, Enum):
    """
    子规划器类型枚举
    使用 str 作为基类以确保与 factory.py 和 sub_planner_flow.py 中的枚举兼容
    """
    CODE = "code"
    REASONING = "reasoning"
    SEARCH = "search"
    FILE = "file"

class PromptManager:
    """
    提示词管理器，负责根据任务类型选择合适的提示词
    """
    
    @staticmethod
    def _get_task_value(task_type) -> str:
        """
        安全地获取任务类型的值
        
        Args:
            task_type: 任务类型，可以是枚举、字符串或其他类型
            
        Returns:
            str: 任务类型的字符串值
        """
        try:
            if isinstance(task_type, Enum):
                return task_type.value
            elif isinstance(task_type, str):
                # 检查是否是有效的任务类型值
                valid_values = [t.value for t in SubPlannerType]
                if task_type in valid_values:
                    return task_type
                logger.warning(f"无效的任务类型字符串: {task_type}，使用默认值")
            elif hasattr(task_type, 'value'):
                return task_type.value
            else:
                logger.warning(f"未知的任务类型: {task_type}，使用默认值")
                return str(task_type)
        except Exception as e:
            logger.error(f"获取任务类型值失败: {str(e)}")
            return SubPlannerType.MESSAGE.value  # 默认返回 message
    
    @staticmethod
    def get_subplanner_prompt(task_type) -> str:
        """
        根据任务类型获取对应的 SubPlanner 系统提示词
        
        Args:
            task_type: 任务类型，可以是枚举、字符串或其他类型
            
        Returns:
            str: 对应的系统提示词
        """
        try:
            task_value = PromptManager._get_task_value(task_type)
            
            if task_value == SubPlannerType.CODE.value:
                from app.domain.services.prompts.code_sub_planner_prompt import CODE_SUB_PLANNER_SYSTEM_PROMPT
                return CODE_SUB_PLANNER_SYSTEM_PROMPT
            elif task_value == SubPlannerType.FILE.value:
                from app.domain.services.prompts.file_sub_planner_prompt import FILE_SUB_PLANNER_SYSTEM_PROMPT
                return FILE_SUB_PLANNER_SYSTEM_PROMPT
            elif task_value == SubPlannerType.SEARCH.value:
                from app.domain.services.prompts.search_sub_planner_prompt import SEARCH_SUB_PLANNER_SYSTEM_PROMPT
                return SEARCH_SUB_PLANNER_SYSTEM_PROMPT
            elif task_value == SubPlannerType.REASONING.value:
                from app.domain.services.prompts.reasoning_sub_planner_prompt import REASONING_SUB_PLANNER_SYSTEM_PROMPT
                return REASONING_SUB_PLANNER_SYSTEM_PROMPT
                
        except Exception as e:
            logger.error(f"获取 SubPlanner 提示词失败: {str(e)}")
            from app.domain.services.prompts.reasoning_sub_planner_prompt import REASONING_SUB_PLANNER_SYSTEM_PROMPT
            return REASONING_SUB_PLANNER_SYSTEM_PROMPT

    @staticmethod
    def get_create_plan_prompt(task_type) -> str:
        """
        根据任务类型获取创建计划的提示词
        """
        try:
            task_value = PromptManager._get_task_value(task_type)
            
            if task_value == SubPlannerType.CODE.value:
                from backend.app.domain.services.prompts.code_sub_planner_prompt import CODE_SUB_PLANNER_CREATE_PLAN_PROMPT
                return CODE_SUB_PLANNER_CREATE_PLAN_PROMPT
            elif task_value == SubPlannerType.FILE.value:
                from app.domain.services.prompts.file_sub_planner_prompt import FILE_SUB_PLANNER_CREATE_PLAN_PROMPT
                return FILE_SUB_PLANNER_CREATE_PLAN_PROMPT
            elif task_value == SubPlannerType.SEARCH.value:
                from app.domain.services.prompts.search_sub_planner_prompt import SEARCH_SUB_PLANNER_CREATE_PLAN_PROMPT
                return SEARCH_SUB_PLANNER_CREATE_PLAN_PROMPT
            elif task_value == SubPlannerType.REASONING.value:
                from app.domain.services.prompts.reasoning_sub_planner_prompt import REASONING_SUB_PLANNER_CREATE_PLAN_PROMPT
                return REASONING_SUB_PLANNER_CREATE_PLAN_PROMPT

                
        except Exception as e:
            logger.error(f"获取创建计划提示词失败: {str(e)}")
            from app.domain.services.prompts.reasoning_sub_planner_prompt import REASONING_SUB_PLANNER_CREATE_PLAN_PROMPT
            return REASONING_SUB_PLANNER_CREATE_PLAN_PROMPT

    @staticmethod
    def get_update_plan_prompt(task_type) -> str:
        """
        根据任务类型获取更新计划的提示词
        """
        try:
            task_value = PromptManager._get_task_value(task_type)
            
            if task_value == SubPlannerType.CODE.value:
                from backend.app.domain.services.prompts.code_sub_planner_prompt import CODE_SUB_PLANNER_UPDATE_PLAN_PROMPT
                return CODE_SUB_PLANNER_UPDATE_PLAN_PROMPT
            elif task_value == SubPlannerType.FILE.value:
                from app.domain.services.prompts.file_sub_planner_prompt import FILE_SUB_PLANNER_UPDATE_PLAN_PROMPT
                return FILE_SUB_PLANNER_UPDATE_PLAN_PROMPT
            elif task_value == SubPlannerType.SEARCH.value:
                from app.domain.services.prompts.search_sub_planner_prompt import SEARCH_SUB_PLANNER_UPDATE_PLAN_PROMPT
                return SEARCH_SUB_PLANNER_UPDATE_PLAN_PROMPT
            elif task_value == SubPlannerType.REASONING.value:
                from app.domain.services.prompts.reasoning_sub_planner_prompt import REASONING_SUB_PLANNER_UPDATE_PLAN_PROMPT
                return REASONING_SUB_PLANNER_UPDATE_PLAN_PROMPT

                
        except Exception as e:
            logger.error(f"获取更新计划提示词失败: {str(e)}")
            from app.domain.services.prompts.reasoning_sub_planner_prompt import REASONING_SUB_PLANNER_UPDATE_PLAN_PROMPT
            return REASONING_SUB_PLANNER_UPDATE_PLAN_PROMPT

    @staticmethod
    def get_execute_prompt(task_type) -> str:
        """
        根据任务类型获取执行任务的提示词
        """
        try:
            task_value = PromptManager._get_task_value(task_type)
            
            if task_value == SubPlannerType.CODE.value:
                from backend.app.domain.services.prompts.code_sub_planner_prompt import CODE_SUB_PLANNER_EXECUTE_PROMPT
                return CODE_SUB_PLANNER_EXECUTE_PROMPT
            elif task_value == SubPlannerType.FILE.value:
                from app.domain.services.prompts.file_sub_planner_prompt import FILE_SUB_PLANNER_EXECUTE_PROMPT
                return FILE_SUB_PLANNER_EXECUTE_PROMPT
            elif task_value == SubPlannerType.SEARCH.value:
                from app.domain.services.prompts.search_sub_planner_prompt import SEARCH_SUB_PLANNER_EXECUTE_PROMPT
                return SEARCH_SUB_PLANNER_EXECUTE_PROMPT
            elif task_value == SubPlannerType.REASONING.value:
                from app.domain.services.prompts.reasoning_sub_planner_prompt import REASONING_SUB_PLANNER_EXECUTE_PROMPT
                return REASONING_SUB_PLANNER_EXECUTE_PROMPT

                
        except Exception as e:
            logger.error(f"获取执行任务提示词失败: {str(e)}")
            from app.domain.services.prompts.reasoning_sub_planner_prompt import REASONING_SUB_PLANNER_EXECUTE_PROMPT
            return REASONING_SUB_PLANNER_EXECUTE_PROMPT

    @staticmethod
    def get_summarize_prompt(task_type) -> str:
        """
        根据任务类型获取总结执行的提示词
        """
        try:
            task_value = PromptManager._get_task_value(task_type)
            
            if task_value == SubPlannerType.CODE.value:
                from backend.app.domain.services.prompts.code_sub_planner_prompt import CODE_SUB_PLANNER_SUMMARIZE_PROMPT
                return CODE_SUB_PLANNER_SUMMARIZE_PROMPT
            elif task_value == SubPlannerType.FILE.value:
                from app.domain.services.prompts.file_sub_planner_prompt import FILE_SUB_PLANNER_SUMMARIZE_PROMPT
                return FILE_SUB_PLANNER_SUMMARIZE_PROMPT
            elif task_value == SubPlannerType.SEARCH.value:
                from app.domain.services.prompts.search_sub_planner_prompt import SEARCH_SUB_PLANNER_SUMMARIZE_PROMPT
                return SEARCH_SUB_PLANNER_SUMMARIZE_PROMPT
            elif task_value == SubPlannerType.REASONING.value:
                from app.domain.services.prompts.reasoning_sub_planner_prompt import REASONING_SUB_PLANNER_SUMMARIZE_PROMPT
                return REASONING_SUB_PLANNER_SUMMARIZE_PROMPT

                
        except Exception as e:
            logger.error(f"获取总结执行提示词失败: {str(e)}")
            from app.domain.services.prompts.reasoning_sub_planner_prompt import REASONING_SUB_PLANNER_SUMMARIZE_PROMPT
            return REASONING_SUB_PLANNER_SUMMARIZE_PROMPT

    @staticmethod
    def get_report_prompt(task_type) -> str:
        """
        根据任务类型获取生成报告的提示词
        """
        try:
            task_value = PromptManager._get_task_value(task_type)
            
            if task_value == SubPlannerType.CODE.value:
                from backend.app.domain.services.prompts.code_sub_planner_prompt import CODE_SUB_PLANNER_REPORT_PROMPT
                return CODE_SUB_PLANNER_REPORT_PROMPT
            elif task_value == SubPlannerType.FILE.value:
                from app.domain.services.prompts.file_sub_planner_prompt import FILE_SUB_PLANNER_REPORT_PROMPT
                return FILE_SUB_PLANNER_REPORT_PROMPT
            elif task_value == SubPlannerType.SEARCH.value:
                from app.domain.services.prompts.search_sub_planner_prompt import SEARCH_SUB_PLANNER_REPORT_PROMPT
                return SEARCH_SUB_PLANNER_REPORT_PROMPT
            elif task_value == SubPlannerType.REASONING.value:
                from app.domain.services.prompts.reasoning_sub_planner_prompt import REASONING_SUB_PLANNER_REPORT_PROMPT
                return REASONING_SUB_PLANNER_REPORT_PROMPT
           
                
        except Exception as e:
            logger.error(f"获取生成报告提示词失败: {str(e)}")
            from app.domain.services.prompts.reasoning_sub_planner_prompt import REASONING_SUB_PLANNER_REPORT_PROMPT
            return REASONING_SUB_PLANNER_REPORT_PROMPT


    @staticmethod
    def clear_tag(prompt: str = "", tag: str = "", save_tag = False):
        
        if tag == "":
            return prompt
        
        # Remove content between tags, optionally keeping the tags themselves
        if save_tag:
            # Keep tags but remove content between them
            pattern = f"<{tag}>(.*?)</{tag}>"
            return re.sub(pattern, f"<{tag}></{tag}>", prompt, flags=re.DOTALL)
        else:
            # Remove tags and content between them
            pattern = f"<{tag}>.*?</{tag}>"
            return re.sub(pattern, "", prompt, flags=re.DOTALL)
    
    @staticmethod
    async def update_ls(prompt: str = "", shell_tool: ShellTool = None):
        
        if shell_tool is None:
            logger.warning("Shell tool not available, using default values")
            return prompt
        
        DIR_PROMPT = """
            <dir>
            Current directory: {current_dir}
            Current list: {current_list}
            </dir>
            """
        
        prompt = PromptManager.clear_tag(prompt, "dir", save_tag = False)
        
        # Use shell tool to get actual sandbox container directory info
        try:
            # Create a unique session ID for this shell operation
            session_id = f"dir_check_{uuid.uuid4().hex[:8]}"
            logger.info(f"Creating dir check session with ID: {session_id}")
            
            logger.info("Shell tool available, executing pwd command...")
            cwd_result = await shell_tool.shell_exec(
                id=session_id,
                exec_dir="/home/ubuntu",  # Start from default sandbox home
                command="pwd"
            )
            
            # Get directory listing
            logger.info("Executing ls command...")
            ls_result = await shell_tool.shell_exec(
                id=session_id,
                exec_dir="/home/ubuntu",  # Start from default sandbox home
                command="ls -la"
            )
            
            # Extract results
            current_dir = cwd_result.data.get('output', '').strip() if cwd_result.success and cwd_result.data else "/home/ubuntu"
            current_list = ls_result.data.get('output', '').strip() if ls_result.success and ls_result.data else "No files found"
            
            # Update the system prompt
            dir_info = DIR_PROMPT.format(current_dir=current_dir, current_list=current_list)
            prompt += dir_info
            
            return prompt
            
        except Exception as e:
            logger.error(f"Error updating system prompt: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Error traceback: {traceback.format_exc()}")
            return prompt
        
    @staticmethod
    def update_mem(prompt: str, memory: Memory) -> str:
        """
        根据memory更新prompt，检查是否存在<memory>标签
        如果存在则替换内容，如果不存在则在末尾追加
        """
        if memory is None:
            return prompt
        
        MEMORY_PROMPT = """
        <memory>
        Messages History:
        {messages}
        Tool Usage History:
        {tool_history}
        </memory>
        """
        
        # 清除现有的memory标签内容
        prompt = PromptManager.clear_tag(prompt, "memory", save_tag=False)
        
        try:
            # 获取消息历史
            messages = memory.get_filtered_messages()
            messages_str = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                for msg in messages
            ])
            
            # 获取工具使用历史
            tool_history = memory.get_tool_history()
            
            # 安全地更新prompt，避免格式化冲突
            memory_info = MEMORY_PROMPT.replace("{messages}", messages_str).replace("{tool_history}", tool_history)
            prompt += memory_info
            
            return prompt
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating memory in prompt: {str(e)}")
            return prompt

    # TODO: "update_step" function?
    
    def _find_tool_rule(tool: BaseTool, is_executor: bool = False) -> str:
        """
        根据工具类型获取对应的工具规则
        """
        tool_collection = execution_tools if is_executor else sub_planner_tools
        if isinstance(tool, ShellTool):
            return tool_collection.SHELL
        elif isinstance(tool, SearchTool):
            return tool_collection.SEARCH
        elif isinstance(tool, FileTool):
            return tool_collection.FILE
        elif isinstance(tool, MessageTool):
            return tool_collection.MESSAGE
        return ""
    
    def _find_all_tools_rules(tools = List[BaseTool], is_executor: bool = False) -> str:
        
        result = ""
        for tool in tools:
            if tool is None:
                continue
            result += PromptManager._find_tool_rule(tool, is_executor)
        return result
    
    def get_system_prompt_with_tools(tools: List[BaseTool], is_executor: bool = False, is_code: bool = False) -> str:
        
        if is_executor:
            prompt = EXECUTION_SYSTEM_PROMPT_NO_TOOL
        else:
            prompt = CODE_SUB_PLANNER_SYSTEM_PROMPT_NO_TOOL if is_code else SUB_PLANNER_SYSTEM_PROMPT_NO_TOOL
        
        tool_rules = PromptManager._find_all_tools_rules(tools, is_executor)
        logger.info(f"tool_rules: {tool_rules}")
        if tool_rules:
            prompt = prompt.replace('{tool_rules}', tool_rules)
        return prompt

    def insert_datetime(prompt: str) -> str:
        """
        安全地插入当前时间到prompt中，只替换{cur_time}占位符
        """
        try:
            # 只替换{cur_time}占位符，避免与其他占位符冲突
            return prompt.replace("{cur_time}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            logger.error(f"插入时间到prompt失败: {str(e)}")
            return prompt

    