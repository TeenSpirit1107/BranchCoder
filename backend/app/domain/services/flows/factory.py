from typing import Dict, Type, List, Optional
import logging
from enum import Enum

from app.domain.services.flows.base import BaseFlow, BaseSubFlow
from app.domain.services.flows.branch_code_flow import BranchCodeFlow
from app.domain.services.flows.plan_act import PlanActFlow
from app.domain.services.flows.simple_chat import SimpleChatFlow
from app.domain.services.flows.default_flow import DefaultFlow
from app.domain.services.flows.search_flow import SearchFlow
from app.domain.services.flows.code_flow import CodeFlow
from app.domain.models.agent import Agent
from app.domain.external.llm import LLM, AudioLLM, ImageLLM, VideoLLM, ReasonLLM
from app.domain.external.sandbox import Sandbox
from app.domain.external.browser import Browser
from app.domain.external.search import SearchEngine
from app.infrastructure.logging import setup_sub_planner_flow_logger

logger = logging.getLogger(__name__)

class FlowFactory:
    """Flow工厂类,负责管理和创建不同类型的flow"""
    
    def __init__(self):
        # 注册所有可用的flow类型
        self._flow_classes: Dict[str, Type[BaseFlow]] = {}
        self._register_default_flows()
    
    def _register_default_flows(self):
        """注册默认的flow类型"""
        self.register_flow(PlanActFlow)
        self.register_flow(SimpleChatFlow)
        self.register_flow(BranchCodeFlow)
        # 延迟导入 SuperPlannerFlow 以避免循环导入
        from app.domain.services.flows.super_flow import SuperFlow
        self.register_flow(SuperFlow)
        logger.info("已注册默认flow类型")
    
    def register_flow(self, flow_class: Type[BaseFlow]) -> None:
        """注册新的flow类型"""
        if not issubclass(flow_class, BaseFlow):
            raise ValueError(f"Flow类 {flow_class.__name__} 必须继承自BaseFlow")
        
        flow_id = flow_class.get_flow_id()
        if not flow_id:
            raise ValueError(f"Flow类 {flow_class.__name__} 必须定义flow_id")
        
        if flow_id in self._flow_classes:
            logger.warning(f"Flow ID '{flow_id}' 已存在，将被覆盖")
        
        self._flow_classes[flow_id] = flow_class
        logger.info(f"已注册flow类型: {flow_id} -> {flow_class.__name__}")
    
    def create_flow(self, flow_id: str, agent: Agent, llm: LLM, audio_llm: AudioLLM, image_llm: ImageLLM, video_llm: VideoLLM, reason_llm: ReasonLLM, sandbox: Sandbox, 
                   browser: Browser, search_engine: Optional[SearchEngine] = None, 
                   **kwargs) -> BaseFlow:
        """根据flow_id创建对应的flow实例"""
    
        
        if flow_id not in self._flow_classes:
            available_flows = list(self._flow_classes.keys())
            raise ValueError(f"未知的flow类型: {flow_id}. 可用类型: {available_flows}")
        
        flow_class = self._flow_classes[flow_id]
        
        try:
            # 创建flow实例，传递所有必要的参数
            flow_instance = flow_class(
                agent=agent,
                llm=llm,
                audio_llm=audio_llm,
                image_llm=image_llm,
                video_llm=video_llm,
                reason_llm=reason_llm,
                sandbox=sandbox,
                browser=browser,
                search_engine=search_engine,
                **kwargs
            )
            logger.info(f"成功创建flow实例: {flow_id} for Agent {agent.id}")
            return flow_instance
        except Exception as e:
            logger.error(f"创建flow实例失败: {flow_id}, 错误: {str(e)}")
            raise
    
    def get_available_flows(self) -> List[Dict[str, str]]:
        """获取所有可用的flow类型信息"""
        flows = []
        for flow_id, flow_class in self._flow_classes.items():
            flows.append({
                "flow_id": flow_id,
                "name": flow_class.__name__,
                "description": flow_class.get_description()
            })
        return flows
    
    def has_flow(self, flow_id: str) -> bool:
        """检查是否存在指定的flow类型"""
        return flow_id in self._flow_classes
    
    def get_flow_class(self, flow_id: str) -> Optional[Type[BaseFlow]]:
        """获取指定flow_id对应的flow类"""
        return self._flow_classes.get(flow_id)

# 创建全局工厂实例
flow_factory = FlowFactory()

# 把这些type临时重定向到sub_planner_flow
class SubPlannerType(Enum):
    CODE = "code"
    REASONING = "reasoning"
    SEARCH = "search"
    FILE = "file"
    #MESSAGE = "message"
    #SHELL = "shell"

class SubFlowFactory:
    """
    子流程工厂类
    负责创建和管理所有子流程实例
    """
    
    def __init__(self):
        # 注册所有可用的子流程类型
        self._flow_classes: Dict[str, Type[BaseSubFlow]] = {}
        
        # 设置专门的日志记录器
        self.factory_logger = setup_sub_planner_flow_logger("SubFlowFactory")
        self.factory_logger.info(f"=== SubFlowFactory初始化 ===")
        
        # 注册默认流程
        self._register_default_flows()
    
    def _register_default_flows(self):
        """注册默认的子流程类型"""
        self.register_flow(DefaultFlow)
        self.register_flow(SearchFlow)
        self.register_flow(CodeFlow)
        self.factory_logger.info("已注册默认子流程类型")
    
    def register_flow(self, flow_class: Type[BaseSubFlow]) -> None:
        """注册新的子流程类型"""
        if not issubclass(flow_class, BaseSubFlow):
            raise ValueError(f"Flow类 {flow_class.__name__} 必须继承自BaseSubFlow")
        
        flow_id = flow_class.get_flow_id()
        if not flow_id:
            raise ValueError(f"Flow类 {flow_class.__name__} 必须定义flow_id")
        
        if flow_id in self._flow_classes:
            self.factory_logger.warning(f"Flow ID '{flow_id}' 已存在，将被覆盖")
        
        self._flow_classes[flow_id] = flow_class
        self.factory_logger.info(f"已注册子流程类型: {flow_id} -> {flow_class.__name__}")
    
    def create_flow(self,
                    llm: LLM,
                    task_type: Enum,
                    sandbox: Sandbox,
                    browser: Browser,
                    search_engine: Optional[SearchEngine] = None,
                    audio_llm: Optional[AudioLLM] = None,
                    image_llm: Optional[ImageLLM] = None,
                    video_llm: Optional[VideoLLM] = None,
                    reason_llm: Optional[ReasonLLM] = None,
                    ) -> BaseSubFlow:
        """根据任务类型创建对应的子流程实例"""
        # 添加详细的调试日志
        self.factory_logger.info(f"=== create_flow 开始 ===")
        self.factory_logger.debug(f"task_type 参数: {task_type}")
        self.factory_logger.debug(f"task_type 类型: {type(task_type)}")
        self.factory_logger.debug(f"task_type.value 类型: {type(task_type.value)}")
        
        # 获取实际的 flow_type
        flow_type = task_type.value
       # self.factory_logger.info(f"flow_type: {flow_type}")
      #  self.factory_logger.debug(f"可用的flow类型: {list(self._flow_classes.keys())}")
            
        # 重定向逻辑：所有 -> general sub flow
        if flow_type == "search":
            self.factory_logger.info(f"flow_type {flow_type} 不重定向")
        elif flow_type == "code":
            self.factory_logger.info(f"flow_type {flow_type} 不重定向 ")
        elif flow_type == "file":
            self.factory_logger.info(f"flow_type {flow_type} 重定向到general_flow")
            flow_type = "default"
        elif flow_type == 'reasoning':
            self.factory_logger.info(f"flow_type {flow_type} 重定向到general_flow")
            flow_type = "default"
        else:
            available_flows = list(self._flow_classes.keys())
            self.factory_logger.error(f"未知的子流程类型: {flow_type}. 可用类型: {available_flows}")
            raise ValueError(f"未知的子流程类型: {flow_type}. 可用类型: {available_flows}")
        
        flow_class = self._flow_classes[flow_type]
        self.factory_logger.debug(f"选择的flow_class: {flow_class}")
        self.factory_logger.debug(f"flow_class 类型: {type(flow_class)}")
        
        try:
            self.factory_logger.info(f"=== 开始创建flow实例 ===")
            self.factory_logger.debug(f"检查flow_class是否在预期列表中: {flow_class in [DefaultFlow, SearchFlow, CodeFlow]}")
            
            # 针对不同子类传递不同参数
            # self.factory_logger.debug(f"使用完整参数创建flow实例")
            # self.factory_logger.debug(f"传递的参数:")
            # self.factory_logger.debug(f"llm: {llm}")
            # self.factory_logger.debug(f"sandbox: {sandbox}")
            # self.factory_logger.debug(f"browser: {browser}")
            # self.factory_logger.debug(f"search_engine: {search_engine}")
            # self.factory_logger.debug(f"task_type: {task_type} (类型: {type(task_type)})")

            flow_instance = flow_class(
                llm=llm,
                sandbox=sandbox,
                browser=browser,
                search_engine=search_engine,
                audio_llm=audio_llm,
                image_llm=image_llm,
                video_llm=video_llm,
                reason_llm=reason_llm,
                task_type=task_type,
            )
            self.factory_logger.info(f"成功创建子流程实例: {flow_type}")
            return flow_instance
        except Exception as e:
            self.factory_logger.error(f"创建子流程实例失败: {flow_type}, 错误: {str(e)}")
            self.factory_logger.error(f"错误类型: {type(e)}")
            import traceback
            self.factory_logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise
    
    def get_available_flows(self) -> List[Dict[str, str]]:
        """获取所有可用的子流程类型信息"""
        flows = []
        for flow_id, flow_class in self._flow_classes.items():
            flows.append({
                "flow_id": flow_id,
                "name": flow_class.__name__,
                "description": flow_class.get_description()
            })
        return flows

    def get_available_flows_enum(self,enum_name: str = "SubPlannerType") -> type[Enum]:
        flows = self.get_available_flows()
        # 构造枚举成员字典: { "MESSAGE": "message", ... }
        enum_members = {}
        for flow in flows:
            raw_name = flow["name"]
            enum_key = raw_name.replace("Flow", "").upper()
            enum_value = flow["flow_id"]
            enum_members[enum_key] = enum_value

        # 使用 type() + EnumMeta 创建类
        return Enum(enum_name, enum_members)

    def has_flow(self, flow_id: str) -> bool:
        """检查是否存在指定的子流程类型"""
        return flow_id in self._flow_classes
    
    def get_flow_class(self, flow_id: str) -> Optional[Type[BaseSubFlow]]:
        """获取指定flow_id对应的子流程类"""
        return self._flow_classes.get(flow_id)

# 创建全局子流程工厂实例
sub_flow_factory = SubFlowFactory() 