from typing import AsyncGenerator, Dict, Any, Optional, Generator, List, Tuple
import logging
import os
import json
import uuid
import asyncio

from app.application.schemas.event import (
    SSEEvent, DoneSSEEvent,
    MessageData, MessageSSEEvent,
    ToolData, ToolSSEEvent,
    StepSSEEvent, ErrorSSEEvent,
    TitleData, TitleSSEEvent,
    BaseData,
    StepData, ErrorData,
    PlanData, PlanSSEEvent,
    UserInputData, UserInputSSEEvent
)
from app.application.schemas.response import ShellViewResponse, FileViewResponse, FileListResponse, FileListItem
from app.application.schemas.request import CreateAgentRequest
from app.domain.models.agent import Agent
from app.domain.models.environment import Environment
from ...domain.services.agent import AgentDomainService
from app.domain.models.event import (
    PlanCreatedEvent,
    ToolCallingEvent,
    ToolCalledEvent,
    StepStartedEvent,
    StepFailedEvent,
    StepCompletedEvent,
    PlanCompletedEvent,
    PlanUpdatedEvent,
    ErrorEvent,
    AgentEvent,
    DoneEvent,
    UserInputEvent,
    ReportEvent
)
from app.application.schemas.exceptions import NotFoundError, PermissionDeniedError, OperationError
from app.infrastructure.external.llm.openai_llm import OpenAILLM, OpenAIImageLLM
from app.infrastructure.external.llm.audio_llm import SiliconflowAudioLLM
from app.infrastructure.external.llm.video_llm import GeminiVideoLLM
from app.infrastructure.external.llm.reason_llm import DeepSeekReasonLLM
from app.infrastructure.external.sandbox.sandbox_factory import SandboxFactory
from app.infrastructure.external.browser.playwright_browser import PlaywrightBrowser
from app.infrastructure.external.search.search_engine_factory import create_search_engine
from app.infrastructure.external.search.search_engine_interface import SearchEngineInterface
from app.infrastructure.config import get_settings
from ..services.user_context import UserContext
from app.domain.services.conversation_service import ConversationService
from app.infrastructure.external.conversation.memory_repository import MemoryConversationRepository
from app.domain.services.event_subscription_service import EventSubscriptionDomainService
from app.infrastructure.external.user.memory_repository import MemoryUserRepository
from app.domain.services.user_service import UserService
from app.domain.models.memory import Memory
from app.domain.models.exceptions import AgentNotRunningError
from app.infrastructure.external.factories import get_event_subscription_manager, get_agent_context_repository

# Set up logger
logger = logging.getLogger(__name__)

class AgentService:
    def __init__(self):
        logger.info("Initializing AgentService")
        # 初始化事件订阅管理器
        self.event_subscription_manager = get_event_subscription_manager()
        
        # 初始化事件订阅领域服务
        self.event_subscription_domain_service = EventSubscriptionDomainService(
            broadcast_repository=self.event_subscription_manager.broadcast_repository,
            stream_repository=self.event_subscription_manager.stream_repository,
            event_subscription_manager=self.event_subscription_manager  # 传递底层管理器
        )
        
        # 初始化会话服务
        conversation_repository = MemoryConversationRepository()
        conversation_service = ConversationService(conversation_repository)
        
        # 初始化用户服务
        user_repository = MemoryUserRepository()
        user_service = UserService(user_repository)
        
        # 根据配置选择使用哪种Agent领域服务实现
        logger.info("Using AgentDomainServiceWithRepository (repository pattern)")
        agent_context_repository = get_agent_context_repository()
        self.agent_domain_service = AgentDomainService(
            agent_context_repository=agent_context_repository,
            conversation_service=conversation_service,
            event_subscription_service=self.event_subscription_domain_service,
            user_service=user_service
        )
        
        self.settings = get_settings()
        self.llm = OpenAILLM()
        self.audio_llm = SiliconflowAudioLLM()
        self.image_llm = OpenAIImageLLM()
        self.video_llm = GeminiVideoLLM()
        self.reason_llm = DeepSeekReasonLLM()
        self.search_engine: SearchEngineInterface = create_search_engine()

    async def create_agent(self, request: Optional[CreateAgentRequest] = None) -> Agent:
        """
        Create a new agent.
        
        Args:
            request: Optional request containing agent configuration
            
        Returns:
            Agent: The created agent
        """
        logger.info("Creating new agent")
        
        # 初始化请求
        if request is None:
            request = CreateAgentRequest()
            
        # 获取当前用户ID
        user_id = UserContext.get_current_user_id()
        logger.info(f"Creating agent for user: {user_id}")
        
        # 获取flow_id
        flow_id = request.flow_id
        logger.info(f"Using flow type: {flow_id}")
        
        # 验证flow_id是否有效
        available_flows = self.agent_domain_service.get_available_flows()
        valid_flow_ids = [flow["flow_id"] for flow in available_flows]
        if flow_id not in valid_flow_ids:
            raise ValueError(f"无效的flow类型: {flow_id}. 可用的flow类型: {valid_flow_ids}")
        
        # 获取环境变量
        environment_variables = request.environment_variables
        if environment_variables:
            logger.info(f"Received {len(environment_variables)} environment variables")
        
        # 首先创建Agent实例以获取agent_id
        # 创建环境变量领域模型（如果有）
        environment = None
        if environment_variables:
            environment = Environment.from_dict(
                variables=environment_variables,
                user_id=user_id
            )
        
        # 创建Agent实例，获取agent_id
        agent = Agent(
            planner_memory=Memory(),
            execution_memory=Memory(),
            model_name=self.settings.model_name,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
            user_id=user_id,
            environment=environment
        )
        
        agent_id = agent.id
        logger.info(f"Generated agent ID: {agent_id}")
        
        # 使用agent_id作为沙箱ID，获取或创建沙箱（支持持久化存储卷）
        sandbox = await SandboxFactory.get_or_create_sandbox(
            sandbox_id=agent_id,
            user_id=user_id,
            environment_variables=environment_variables
        )
        cdp_url = sandbox.get_cdp_url()
        logger.info(f"Got or created sandbox with CDP URL: {cdp_url}")
        
        browser = PlaywrightBrowser(self.llm, cdp_url)
        logger.info("Initialized Playwright browser")
        
        # 使用异步方法
        final_agent = await self.agent_domain_service.initialize_agent(
            agent=agent,
            llm=self.llm, 
            image_llm=self.image_llm,
            audio_llm=self.audio_llm,
            video_llm=self.video_llm,
            reason_llm=self.reason_llm,
            sandbox=sandbox, 
            browser=browser, 
            search_engine=self.search_engine,
            flow_id=flow_id
        )
        
        logger.info(f"Agent created successfully with ID: {agent_id}, user ID: {user_id}, flow: {flow_id}")
        return final_agent

    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        logger.info(f"Retrieving agent with ID: {agent_id}")
        agent = await self.agent_domain_service.get_agent(agent_id)
        
        if agent:
            logger.info(f"Agent found: {agent_id}")
        else:
            logger.warning(f"Agent not found: {agent_id}")
        return agent

    def _to_sse_event(self, event: AgentEvent) -> Generator[SSEEvent, None, None]:
        if isinstance(event, (PlanCreatedEvent, PlanUpdatedEvent, PlanCompletedEvent)):
            if isinstance(event, PlanCreatedEvent):
                if event.plan.title:
                    yield TitleSSEEvent(data=TitleData(title=event.plan.title))
                yield MessageSSEEvent(data=MessageData(content=event.plan.message))
            if len(event.plan.steps) > 0:
                """
                if event.issubplan == True: 
                    yield PlanSSEEvent(data=PlanData(steps=[StepData(
                        status=step.status,
                        id=step.id, 
                        description=step.description
                    ) for step in event.plan.steps]))
                elif event.issuperplan == True: 
                    yield PlanSSEEvent(data=PlanData(steps=[StepData(
                        status=step.status,
                        id=step.id, 
                        description=step.description
                    ) for step in event.plan.steps]))
                else: 
                    yield PlanSSEEvent(data=PlanData(steps=[StepData(
                        status=step.status,
                        id=step.id, 
                        description=step.description
                    ) for step in event.plan.steps]))
                """
                print('DEBUG: issuperplan:', getattr(event, 'issuperplan', None), 'issubplan:', getattr(event, 'issubplan', None))
                yield PlanSSEEvent(data=PlanData(
                    steps=[StepData(
                        status=step.status,
                        id=step.id,
                        description=step.description
                    ) for step in event.plan.steps],
                    issuperplan=getattr(event, 'issuperplan', False),
                    issubplan=getattr(event, 'issubplan', False)
                ))
        elif isinstance(event, ReportEvent):
            yield MessageSSEEvent(data=MessageData(content=event.message))
        elif isinstance(event, ToolCallingEvent):
            if event.tool_name in ["message_notify_user"]:
                yield MessageSSEEvent(data=MessageData(content=event.function_args["text"]))
            elif event.function_name in ["message_done", "message_request_clarification"]:
                yield MessageSSEEvent(data=MessageData(content=event.function_args["text"]))
            elif event.function_name in ["message_deliver_artifact"]:
                yield ToolSSEEvent(data=ToolData(
                    name="message",
                    status="calling",
                    function=event.function_name,
                    args=event.function_args
                ))
            elif event.tool_name in ["browser", "file", "shell", "message", "audio", "image", "video", "reasoning"]:
                yield ToolSSEEvent(data=ToolData(
                    name=event.tool_name,
                    status="calling",
                    function=event.function_name,
                    args=event.function_args
                ))
        elif isinstance(event, ToolCalledEvent):
            if event.tool_name in ["search"]:
                yield ToolSSEEvent(data=ToolData(
                    name=event.tool_name,
                    function=event.function_name,
                    args=event.function_args,
                    status="called",
                    result=event.function_result
                ))
        elif isinstance(event, (StepStartedEvent, StepCompletedEvent, StepFailedEvent)):
            yield StepSSEEvent(data=StepData(
                status=event.step.status,
                id=event.step.id,
                description=event.step.description
            ))
            if event.step.error:
                yield ErrorSSEEvent(data=ErrorData(error=event.step.error))
            if event.step.result:
                yield MessageSSEEvent(data=MessageData(content=event.step.result))
        elif isinstance(event, DoneEvent):
            yield DoneSSEEvent(data=BaseData())
        elif isinstance(event, ErrorEvent):
            yield ErrorSSEEvent(data=ErrorData(error=event.error))
        elif isinstance(event, UserInputEvent):
            yield UserInputSSEEvent(data=UserInputData(content=event.message, file_ids=event.file_ids))

        #print('SSE OUT:', json.dumps(PlanSSEEvent(...).dict(), ensure_ascii=False))

    async def destroy_agent(self, agent_id: str) -> bool:
        """Destroy the specified Agent and its associated sandbox
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Whether the destruction was successful
        """
        logger.info(f"Attempting to destroy agent: {agent_id}")
        try:
            # Destroy Agent resources through the domain service
            result = await self.agent_domain_service.close_agent(agent_id)
            if result:
                logger.info(f"Agent destroyed successfully: {agent_id}")
            else:
                logger.warning(f"Failed to destroy agent: {agent_id}")
            return result
        except Exception as e:
            logger.error(f"Error destroying agent {agent_id}: {str(e)}")
            return False

    async def close(self):
        logger.info("Closing all agents and cleaning up resources")
        # Clean up all Agents and their associated sandboxes
        await self.agent_domain_service.close_all()
        logger.info("All agents closed successfully")

    async def agent_exists(self, agent_id: str) -> bool:
        """Check if agent exists"""
        return await self.agent_domain_service.has_agent(agent_id)

    async def shell_view(self, agent_id: str, session_id: str) -> ShellViewResponse:
        """View shell session output
        
        Args:
            agent_id: Agent ID
            session_id: Shell session ID
            
        Returns:
            APIResponse: Response entity containing shell output
            
        Raises:
            ResourceNotFoundError: When Agent or Sandbox does not exist
            OperationError: When a server error occurs during execution
        """
        logger.info(f"Viewing shell output for agent {agent_id} in session {session_id}")
        
        if not await self.agent_exists(agent_id):
            logger.warning(f"Agent not found: {agent_id}")
            raise NotFoundError(f"Agent not found: {agent_id}")
        
        sandbox = await SandboxFactory.get_or_create_sandbox(agent_id)

        if not sandbox:
            logger.warning(f"Sandbox not found: {agent_id}")
            raise NotFoundError(f"Sandbox not found: {agent_id}")
            
        result = await sandbox.view_shell(session_id)
        return ShellViewResponse(**result.data)

    async def get_vnc_url(self, agent_id: str) -> str:
        """Get the VNC URL for the Agent sandbox
        
        Args:
            agent_id: Agent ID
            
        Returns:
            str: Sandbox host address
            
        Raises:
            NotFoundError: When Agent or Sandbox does not exist
        """
        logger.info(f"Getting sandbox host for agent {agent_id}")
        
        if not await self.agent_exists(agent_id):
            logger.warning(f"Agent not found: {agent_id}")
            raise NotFoundError(f"Agent not found: {agent_id}")
        
        sandbox = await SandboxFactory.get_or_create_sandbox(agent_id)
        
        if not sandbox:
            logger.warning(f"Sandbox not found: {agent_id}")
            raise NotFoundError(f"Sandbox not found: {agent_id}")
        
        return sandbox.get_vnc_url()
    
    async def get_code_server_url(self, agent_id: str) -> str:
        """Get the Code Server URL for the Agent sandbox
        
        Args:
            agent_id: Agent ID

        Returns:
            str: Code Server URL
            
        Raises:
            NotFoundError: When Agent or Sandbox does not exist
        """
        logger.info(f"Getting code server URL for agent {agent_id}")

        if not await self.agent_exists(agent_id):
            logger.warning(f"Agent not found: {agent_id}")
            raise NotFoundError(f"Agent not found: {agent_id}")
        
        sandbox = await SandboxFactory.get_or_create_sandbox(agent_id)

        if not sandbox:
            logger.warning(f"Sandbox not found: {agent_id}")
            raise NotFoundError(f"Sandbox not found: {agent_id}")

        return sandbox.get_code_server_url()
    
    async def get_code_server_subdomain_url(self, agent_id: str) -> str:
        """Get the Code Server subdomain URL for the Agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            str: Code Server subdomain URL
            
        Raises:
            NotFoundError: When Agent does not exist
        """
        logger.info(f"Getting code server subdomain URL for agent {agent_id}")
        
        if not await self.agent_exists(agent_id):
            logger.warning(f"Agent not found: {agent_id}")
            raise NotFoundError(f"Agent not found: {agent_id}")
        
        # 构建子域名URL - 开发环境使用HTTP，生产环境使用HTTPS
        protocol = "http" if "localhost" in self.settings.code_server_origin else "https"
        port_suffix = ":8000" if "localhost" in self.settings.code_server_origin else ""
        subdomain_url = f"{protocol}://code-{agent_id}.{self.settings.code_server_origin}{port_suffix}"
        logger.info(f"Generated code server subdomain URL: {subdomain_url}")
        return subdomain_url

    async def file_view(self, agent_id: str, path: str) -> FileViewResponse:
        """View file content
        
        Args:
            agent_id: Agent ID
            path: File path
            
        Returns:
            FileViewResponse: File content
        """
        logger.info(f"[DEBUG 2] 开始查看文件 {path} for agent {agent_id}")
        
        # Verify agent exists
        if not await self.agent_exists(agent_id):
            logger.error(f"[DEBUG 2] Agent {agent_id} not found when viewing file")
            raise NotFoundError(f"Agent {agent_id} not found")
        
        # Get sandbox and view file
        sandbox = await SandboxFactory.get_or_create_sandbox(agent_id)
        
        if sandbox is None:
            logger.error(f"[DEBUG 2] Sandbox not found for agent {agent_id}")
            raise NotFoundError(f"Sandbox not found for agent {agent_id}")
        
        logger.info(f"[DEBUG 2] 调用sandbox.file_read读取文件: {path}")
        result = await sandbox.file_read(path)
        logger.info(f"[DEBUG 2] 文件读取结果: success={result.success}, message={result.message}")
        logger.info(f"[DEBUG 2] 文件数据: {result.data}")
        
        if not result.success:
            logger.error(f"[DEBUG 2] Failed to view file {path}: {result.message}")
            raise OperationError(f"Failed to view file: {result.message}")
        
        content = result.data.get("content", "")
        logger.info(f"[DEBUG 2] 提取的文件内容: type={type(content)}, is_none={content is None}, length={len(str(content)) if content is not None else 'N/A'}")
        
        if content is None:
            logger.error(f"[DEBUG 2] 文件内容为None! 文件路径: {path}, 原始数据: {result.data}")
            content = ""  # 设置为空字符串而不是None
        
        return FileViewResponse(content=content, file=path)

    async def list_files(self, agent_id: str, path: str = "/home/ubuntu") -> FileListResponse:
        """列出沙盒中的文件
        
        Args:
            agent_id: Agent ID
            path: 目录路径，默认为/home/ubuntu
            
        Returns:
            FileListResponse: 文件列表
        """
        logger.info(f"Listing files in {path} for agent {agent_id}")
        
        # 确保路径不为空
        if not path or path.strip() == "":
            path = "/home/ubuntu"
            logger.info(f"Empty path provided, using default: {path}")
        
        # 验证agent是否存在
        if not await self.agent_exists(agent_id):
            logger.error(f"Agent {agent_id} not found when listing files")
            raise NotFoundError(f"Agent {agent_id} not found")
        
        # 获取沙盒并列出文件
        sandbox = await SandboxFactory.get_or_create_sandbox(agent_id)
        
        if sandbox is None:
            logger.error(f"Sandbox not found for agent {agent_id}")
            raise NotFoundError(f"Sandbox not found for agent {agent_id}")
        
        try:
            # 使用shell命令列出文件（临时实现）
            command = f"cd {path} && ls -l --time-style=long-iso | tail -n +2"
            logger.debug(f"Executing command: {command}")
            result = await sandbox.exec_command("list_files_session", "/home/ubuntu", command)
            
            if not result.success:
                logger.error(f"Failed to list files in {path}: {result.message}")
                raise OperationError(f"Failed to list files: {result.message}")
            
            output = result.data.get("output", "")
            logger.debug(f"Command output: {output[:200]}...")
            
            # 解析输出文本为文件列表
            items = []
            for line in output.strip().split("\n"):
                if not line.strip():
                    continue
                
                try:
                    parts = line.split()
                    if len(parts) < 8:
                        continue
                    
                    permissions = parts[0]
                    is_dir = permissions.startswith("d")
                    size = int(parts[4])
                    modified_date = f"{parts[5]} {parts[6]}"
                    name = " ".join(parts[7:])
                    
                    # 排除 "." 和 ".." 目录
                    if name in [".", ".."]:
                        continue
                    
                    # 构建完整路径
                    full_path = f"{path}/{name}" if path.endswith("/") else f"{path}/{name}"
                    
                    items.append(FileListItem(
                        name=name,
                        path=full_path,
                        size=size,
                        is_dir=is_dir,
                        modified_time=modified_date
                    ))
                except Exception as e:
                    logger.warning(f"Error parsing file list entry '{line}': {str(e)}")
            
            logger.info(f"Listed {len(items)} files in {path}")
            return FileListResponse(
                current_path=path,
                items=items
            )
        except Exception as e:
            logger.exception(f"Error listing files in {path}: {str(e)}")
            raise OperationError(f"Failed to list files: {str(e)}")

    async def download_file(self, agent_id: str, file_path: str) -> Tuple[bytes, str, str]:
        """Download a file from sandbox
        
        Args:
            agent_id: Agent ID
            file_path: File path
            
        Returns:
            Tuple[bytes, str]: File content and filename
        """
        logger.info(f"Downloading file from agent {agent_id}, file path: {file_path}")
        
        # 检查Agent是否存在
        if not await self.agent_exists(agent_id):
            logger.warning(f"Agent not found: {agent_id}")
            raise NotFoundError(f"Agent not found: {agent_id}")
        
        # 获取沙箱实例
        sandbox = await SandboxFactory.get_or_create_sandbox(agent_id)
        
        if not sandbox:
            logger.warning(f"Sandbox not found: {agent_id}")
            raise NotFoundError(f"Sandbox not found: {agent_id}")
        
        try:
            # 从沙箱下载文件
            content = await sandbox.file_download(file_path)
            
            # 推断文件类型
            filename = os.path.basename(file_path)
            content_type = self._guess_content_type(filename)
            
            logger.info(f"File downloaded successfully: {file_path}")
            return content, filename, content_type
            
        except FileNotFoundError as e:
            logger.warning(f"File not found in sandbox: {file_path}")
            raise NotFoundError(str(e))
        except PermissionError as e:
            logger.warning(f"Permission denied for file: {file_path}")
            raise PermissionDeniedError(str(e))
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            raise OperationError(f"Error downloading file: {str(e)}")
    
    def _guess_content_type(self, filename: str) -> str:
        """
        根据文件名推断内容类型
        
        Args:
            filename: 文件名
            
        Returns:
            内容类型
        """
        import mimetypes
        
        # 确保mimetypes已初始化
        mimetypes.init()
        
        # 获取文件扩展名并推断内容类型
        content_type, _ = mimetypes.guess_type(filename)
        
        # 如果无法推断，返回通用二进制流类型
        if content_type is None:
            content_type = "application/octet-stream"
            
        return content_type
    
    async def delete_conversation_history(self, agent_id: str) -> bool:
        """删除会话历史"""
        logger.info(f"Deleting conversation history for agent {agent_id}")
        return await self.agent_domain_service.delete_conversation_history(agent_id)
    
    async def list_conversations(self, user_id: Optional[str] = None, limit: int = 50, offset: int = 0):
        """列出会话历史"""
        logger.info(f"Listing conversations for user {user_id}")
        return await self.agent_domain_service.list_conversations(user_id, limit, offset)

    async def get_event_stream(self, agent_id: str, from_sequence: int = 1) -> AsyncGenerator[SSEEvent, None]:
        """
        获取Agent的事件流，支持断连重连
        
        Args:
            agent_id: Agent ID
            from_sequence: 从指定序号开始获取事件
            
        Returns:
            SSE事件流
        """
        logger.info(f"Starting event stream for agent {agent_id} from sequence {from_sequence}")
        
        # 检查Agent是否存在
        if not await self.agent_exists(agent_id):
            logger.error(f"Agent {agent_id} not found")
            yield ErrorSSEEvent(data=ErrorData(error="Agent not found"))
            return
        
        try:
            # 获取事件流
            async for event in self.event_subscription_domain_service.get_event_stream(agent_id, from_sequence):
                # 转换为SSE事件
                for sse_event in self._to_sse_event(event):
                    yield sse_event
                    
        except Exception as e:
            logger.error(f"Error in event stream for agent {agent_id}: {str(e)}")
            yield ErrorSSEEvent(data=ErrorData(error=f"Event stream error: {str(e)}"))

    async def send_message(self, agent_id: str, message: str, timestamp: int = 0, file_ids: List[str] = None) -> bool:
        """
        发送消息到Agent（不返回事件流）
        
        这个方法只负责将消息放入Agent的处理队列，不返回事件流。
        客户端需要通过get_event_stream方法来接收事件。
        
        Args:
            agent_id: Agent ID
            message: 用户消息
            timestamp: 消息时间戳
            file_ids: 文件ID列表，可选
            
        Returns:
            是否成功将消息放入队列
        """
        logger.info(f"Sending message to agent {agent_id}: {message[:50]}...")
        
        # 检查Agent是否存在
        if not await self.agent_exists(agent_id):
            logger.error(f"Agent {agent_id} not found")
            raise NotFoundError(f"Agent {agent_id} not found")
        
        try:
            sandbox = await SandboxFactory.get_or_create_sandbox(agent_id)
            # 使用领域层的send_message方法
            return await self.agent_domain_service.send_message(agent_id, message, sandbox, timestamp, file_ids)
                
        except AgentNotRunningError as e:
            # 尝试从仓储恢复
            logger.info(f"Agent {agent_id} exists in repository but not in runtime, attempting to restore...")
            try:
                # 尝试从仓储恢复Agent
                restored_agent = await self.load_agent_from_repository(agent_id)
                if restored_agent:
                    logger.info(f"Successfully restored Agent {agent_id} from repository")
                    # 重新尝试发送消息
                    return await self.agent_domain_service.send_message(agent_id, message, sandbox, timestamp, file_ids)
                else:
                    logger.error(f"Failed to restore Agent {agent_id} from repository")
                    raise NotFoundError(f"Agent {agent_id} could not be restored")
            except Exception as restore_error:
                logger.error(f"Error restoring Agent {agent_id}: {str(restore_error)}")
                raise OperationError(f"Failed to restore Agent {agent_id}: {str(restore_error)}")

        except RuntimeError as e:
            # 领域层抛出的RuntimeError转换为OperationError
            logger.error(f"Failed to send message: {str(e)}")
            raise OperationError(str(e))
        except Exception as e:
            logger.error(f"Unexpected error sending message to agent {agent_id}: {str(e)}")
            raise OperationError(f"Failed to send message: {str(e)}")

    def get_available_flows(self) -> List[Dict[str, str]]:
        """
        获取所有可用的flow类型
        
        Returns:
            List[Dict[str, str]]: 包含所有可用flow类型的列表
        """
        return self.agent_domain_service.get_available_flows()

    # Agent上下文管理相关方法（仅在使用repository模式时可用）
    async def list_agent_contexts(self, user_id: Optional[str] = None, status: Optional[str] = None, 
                                 limit: int = 50, offset: int = 0):
        """
        列出Agent上下文（仅在使用repository模式时可用）
        
        Args:
            user_id: 用户ID，可选
            status: 状态过滤，可选
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            Agent上下文列表
        """
        return await self.agent_domain_service.list_agent_contexts(user_id, status, limit, offset)
    
    async def get_agent_context(self, agent_id: str):
        """
        获取Agent上下文（仅在使用repository模式时可用）
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent上下文或None
        """
        return await self.agent_domain_service.get_agent_context(agent_id)
    
    async def update_agent_status(self, agent_id: str, status: str) -> bool:
        """
        更新Agent状态（仅在使用repository模式时可用）
        
        Args:
            agent_id: Agent ID
            status: 新状态
            
        Returns:
            是否更新成功
        """
        return await self.agent_domain_service.update_agent_status(agent_id, status)
    
    async def load_agent_from_repository(self, agent_id: str) -> Optional[Agent]:
        """
        从仓储加载Agent并恢复运行时上下文（仅在使用repository模式时可用）
        
        Args:
            agent_id: Agent ID
            
        Returns:
            加载的Agent或None
        """
        try:
            # 创建沙盒
            sandbox = await SandboxFactory.get_or_create_sandbox(
                sandbox_id=agent_id,
                user_id=None,  # 从上下文中获取
                environment_variables=None
            )
            cdp_url = sandbox.get_cdp_url()
            browser = PlaywrightBrowser(self.llm, cdp_url)
            
            return await self.agent_domain_service.load_agent_from_repository(
                agent_id=agent_id,
                llm=self.llm,
                audio_llm=self.audio_llm,
                image_llm=self.image_llm,
                video_llm=self.video_llm,
                reason_llm=self.reason_llm,
                sandbox=sandbox,
                browser=browser,
                search_engine=self.search_engine
            )
        except Exception as e:
            logger.error(f"Failed to load agent {agent_id} from repository: {str(e)}")
            return None

    async def cleanup_inactive_subscriptions(self, timeout_minutes: int = 30) -> int:
        """
        清理不活跃的订阅
        
        Args:
            timeout_minutes: 超时时间（分钟）
            
        Returns:
            清理的订阅数量
        """
        agent_contexts = await self.agent_domain_service.list_agent_contexts()
        for agent_context in agent_contexts:
            try:
                if agent_context.status != "running":
                    await self.event_subscription_domain_service.cleanup_inactive_subscribers(agent_context.agent_id, timeout_minutes)
            except Exception as e:
                logger.error(f"Failed to cleanup inactive subscribers for agent {agent_context.agent_id}: {str(e)}")
                continue
        return len(agent_contexts)

