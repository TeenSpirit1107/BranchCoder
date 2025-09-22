from datetime import datetime
from typing import Optional, AsyncGenerator, Dict, List
import asyncio
import logging
from dataclasses import dataclass

from app.domain.external import Sandbox, Browser, SearchEngine
from app.domain.external.agent_context_repository import AgentContextRepository
from app.domain.models.agent_context import AgentContext as DomainAgentContext
from app.domain.models.memory import Memory
from app.domain.models.agent import Agent
from app.domain.external.llm import LLM, AudioLLM, ImageLLM, VideoLLM, ReasonLLM
from app.domain.models.event import (
    AgentEvent,
    ErrorEvent,
    DoneEvent,
    PlanCreatedEvent,
    UserInputEvent
)
from app.domain.services.flows import BaseFlow, flow_factory
from app.domain.models.environment import Environment
from app.domain.services.conversation_service import ConversationService
from app.domain.services.event_subscription_service import EventSubscriptionDomainService
from app.domain.services.user_service import UserService
from app.domain.models.exceptions import AgentNotRunningError

# Setup logging
logger = logging.getLogger(__name__)

@dataclass
class RuntimeAgentContext:
    """运行时Agent上下文（包含不可持久化的资源）"""
    domain_context: DomainAgentContext
    flow: BaseFlow
    sandbox: Sandbox
    msg_queue: asyncio.Queue
    event_queue: asyncio.Queue
    task: Optional[asyncio.Task] = None


class AgentDomainService:
    """
    使用仓储模式的Agent领域服务

    将Agent上下文的持久化信息存储在仓储中，运行时资源在内存中管理
    """

    def __init__(
        self,
        agent_context_repository: AgentContextRepository,
        conversation_service: ConversationService,
        event_subscription_service: Optional[EventSubscriptionDomainService] = None,
        user_service: Optional[UserService] = None
    ):
        # 运行时上下文管理，key是agent_id，value是运行时资源集合
        self._runtime_contexts: Dict[str, RuntimeAgentContext] = {}
        self.agent_context_repository = agent_context_repository
        self.conversation_service = conversation_service
        self.event_subscription_service = event_subscription_service
        self.user_service = user_service
        logger.info("AgentDomainServiceWithRepository initialization completed")

    async def create_agent(self, model_name: str, llm: LLM, audio_llm: AudioLLM, image_llm: ImageLLM,
                          video_llm: VideoLLM, reason_llm: ReasonLLM, sandbox: Sandbox, browser: Browser,
                          search_engine: Optional[SearchEngine] = None,
                          temperature: float = 0.7,
                          max_tokens: Optional[int] = None,
                          user_id: Optional[str] = None,
                          environment: Optional[Environment] = None,
                          flow_id: str = "plan_act") -> Agent:
        """创建并初始化Agent，包括相关代理和资源"""
        # 验证flow_id是否有效
        if not flow_factory.has_flow(flow_id):
            available_flows = [f["flow_id"] for f in flow_factory.get_available_flows()]
            raise ValueError(f"未知的flow类型: {flow_id}. 可用类型: {available_flows}")

        # 创建Agent实例，ID会自动生成
        agent = Agent(
            planner_memory=Memory(),
            execution_memory=Memory(),
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=user_id,
            environment=environment
        )

        return await self._initialize_agent_context(agent, llm, audio_llm, image_llm, video_llm, reason_llm,
                                                   sandbox, browser, search_engine, flow_id)

    async def initialize_agent(self, agent: Agent, llm: LLM, audio_llm: AudioLLM, image_llm: ImageLLM,
                              video_llm: VideoLLM, reason_llm: ReasonLLM, sandbox: Sandbox, browser: Browser,
                              search_engine: Optional[SearchEngine] = None,
                              flow_id: str = "plan_act") -> Agent:
        """初始化现有Agent实例的资源和上下文"""
        # 验证flow_id是否有效
        if not flow_factory.has_flow(flow_id):
            available_flows = [f["flow_id"] for f in flow_factory.get_available_flows()]
            raise ValueError(f"未知的flow类型: {flow_id}. 可用类型: {available_flows}")

        return await self._initialize_agent_context(agent, llm, audio_llm, image_llm, video_llm, reason_llm,
                                                   sandbox, browser, search_engine, flow_id)

    async def _initialize_agent_context(self, agent: Agent, llm: LLM, audio_llm: AudioLLM, image_llm: ImageLLM,
                                       video_llm: VideoLLM, reason_llm: ReasonLLM, sandbox: Sandbox, browser: Browser,
                                       search_engine: Optional[SearchEngine], flow_id: str) -> Agent:
        """初始化Agent上下文和资源（create_agent和initialize_agent的公共逻辑）"""
        agent_id = agent.id
        logger.info(f"初始化Agent上下文, ID: {agent_id}, model: {agent.model_name}, user_id: {agent.user_id}, flow_id: {flow_id}")

        # 检查该agent_id的资源是否已存在（虽然概率很小）
        if agent_id in self._runtime_contexts:
            logger.error(f"Agent with ID {agent_id} already exists")
            raise ValueError(f"Agent with ID {agent_id} already exists")

        # 使用工厂模式创建flow
        try:
            flow = flow_factory.create_flow(
                flow_id=flow_id,
                agent=agent,
                llm=llm,
                audio_llm=audio_llm,
                image_llm=image_llm,
                video_llm=video_llm,
                reason_llm=reason_llm,
                sandbox=sandbox,
                browser=browser,
                search_engine=search_engine
            )
            logger.info(f"Successfully created flow '{flow_id}' for Agent {agent_id}")
        except Exception as e:
            logger.error(f"Failed to create flow '{flow_id}' for Agent {agent_id}: {str(e)}")
            raise

        # 创建领域上下文
        domain_context = DomainAgentContext(
            agent_id=agent_id,
            agent=agent,
            flow_id=flow_id,
            status="created"
        )

        # 保存到仓储
        try:
            await self.agent_context_repository.save_context(domain_context)
            logger.debug(f"Agent上下文已保存到仓储: {agent_id}")
        except Exception as e:
            logger.error(f"保存Agent上下文到仓储失败: {agent_id}, 错误: {str(e)}")
            raise

        # 创建运行时资源集合
        runtime_context = RuntimeAgentContext(
            domain_context=domain_context,
            flow=flow,
            sandbox=sandbox,
            msg_queue=asyncio.Queue(),
            event_queue=asyncio.Queue()
        )

        self._runtime_contexts[agent_id] = runtime_context

        # 创建并启动任务
        runtime_context.task = asyncio.create_task(
            self._run_flow_task(agent_id)
        )

        # 更新状态为运行中
        await self.agent_context_repository.update_status(agent_id, "running")
        domain_context.update_status("running")

        # 创建会话历史记录
        asyncio.create_task(
            self.conversation_service.create_conversation(
                agent_id=agent_id,
                user_id=agent.user_id,
                flow_id=flow_id
            )
        )

        logger.info(f"Agent {agent_id} initialization completed and task started")

        return agent

    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取指定ID的Agent实例"""
        # 首先尝试从运行时上下文获取
        runtime_context = self._runtime_contexts.get(agent_id)
        if runtime_context:
            return runtime_context.domain_context.agent

        # 如果运行时上下文不存在，尝试从仓储加载
        domain_context = await self.agent_context_repository.get_context(agent_id)
        if domain_context:
            return domain_context.agent

        logger.warning(f"Attempted to get non-existent Agent: {agent_id}")
        return None

    async def has_agent(self, agent_id: str) -> bool:
        """检查指定ID的Agent是否存在"""
        # 首先检查运行时上下文
        if agent_id in self._runtime_contexts:
            return True

        # 然后检查仓储
        domain_context = await self.agent_context_repository.get_context(agent_id)
        exists = domain_context is not None
        logger.debug(f"Checking if Agent {agent_id} exists: {exists}")
        return exists

    async def load_agent_from_repository(self, agent_id: str, llm: LLM, audio_llm: AudioLLM,
                                        image_llm: ImageLLM, video_llm: VideoLLM, reason_llm: ReasonLLM,
                                        sandbox: Sandbox, browser: Browser,
                                        search_engine: Optional[SearchEngine] = None) -> Optional[Agent]:
        """从仓储加载Agent并恢复运行时上下文"""
        domain_context = await self.agent_context_repository.get_context(agent_id)
        if not domain_context:
            logger.warning(f"Agent {agent_id} not found in repository")
            return None

        # 如果已经在运行时上下文中，直接返回
        if agent_id in self._runtime_contexts:
            logger.info(f"Agent {agent_id} already loaded in runtime")
            return domain_context.agent

        try:
            # 重新初始化运行时资源
            await self._restore_runtime_context(domain_context, llm, audio_llm, image_llm, video_llm,
                                               reason_llm, sandbox, browser, search_engine)
            logger.info(f"Agent {agent_id} loaded from repository and runtime context restored")
            return domain_context.agent
        except Exception as e:
            logger.error(f"Failed to restore runtime context for Agent {agent_id}: {str(e)}")
            raise

    async def _restore_runtime_context(self, domain_context: DomainAgentContext, llm: LLM, audio_llm: AudioLLM,
                                      image_llm: ImageLLM, video_llm: VideoLLM, reason_llm: ReasonLLM,
                                      sandbox: Sandbox, browser: Browser,
                                      search_engine: Optional[SearchEngine]) -> None:
        """恢复运行时上下文"""
        agent_id = domain_context.agent_id
        flow_id = domain_context.flow_id

        # 创建flow
        flow = flow_factory.create_flow(
            flow_id=flow_id,
            agent=domain_context.agent,
            llm=llm,
            audio_llm=audio_llm,
            image_llm=image_llm,
            video_llm=video_llm,
            reason_llm=reason_llm,
            sandbox=sandbox,
            browser=browser,
            search_engine=search_engine
        )

        # 创建运行时上下文
        runtime_context = RuntimeAgentContext(
            domain_context=domain_context,
            flow=flow,
            sandbox=sandbox,
            msg_queue=asyncio.Queue(),
            event_queue=asyncio.Queue()
        )

        self._runtime_contexts[agent_id] = runtime_context

        # 启动任务
        runtime_context.task = asyncio.create_task(
            self._run_flow_task(agent_id)
        )

        # 更新状态
        await self.agent_context_repository.update_status(agent_id, "running")
        domain_context.update_status("running")

    async def _run_flow(self, agent_id: str, message: Optional[str] = None) -> AsyncGenerator[AgentEvent, None]:
        """
        处理用户消息的完整业务流程:
        1. 创建计划
        2. 执行计划
        """
        # 获取相关资源
        runtime_context = self._runtime_contexts.get(agent_id)

        if not runtime_context:
            logger.error(f"Agent {agent_id} not initialized")
            yield ErrorEvent(error="Agent not initialized")
            return

        if not message:
            logger.warning(f"Agent {agent_id} received empty message")
            yield ErrorEvent(error="No message")
            return

        async for event in runtime_context.flow.run(message):
            yield event

    def _ensure_task(self, agent_id: str) -> None:
        """确保指定agent的任务和队列已初始化并正常运行"""
        runtime_context = self._runtime_contexts.get(agent_id)
        if not runtime_context:
            logger.warning(f"Attempted to ensure task for non-existent Agent {agent_id}")
            return

        # 检查任务是否需要重启（不存在或已完成或已取消或遇到异常）
        task_needs_restart = (
            runtime_context.task is None or
            runtime_context.task.done() or
            runtime_context.task.cancelled()
        )

        if task_needs_restart:
            # 创建并启动新任务
            logger.info(f"Agent {agent_id} task needs restart, creating new task")
            runtime_context.task = asyncio.create_task(
                self._run_flow_task(agent_id)
            )

    async def _run_flow_task(self, agent_id: str) -> None:
        """处理指定agent的消息队列，支持优雅退出"""
        try:
            logger.info(f"Agent {agent_id} 消息处理任务已启动")
            while True:
                runtime_context = self._runtime_contexts.get(agent_id)

                if not runtime_context:
                    logger.warning(f"Agent {agent_id} 运行时上下文不存在，结束任务")
                    break

                # 使用带超时的等待，以便能够更快响应取消操作
                try:
                    logger.debug(f"Agent {agent_id} 等待消息...")
                    message = await asyncio.wait_for(runtime_context.msg_queue.get(), timeout=1.0)
                    logger.info(f"Agent {agent_id} 收到新消息: {message[:50]}...")

                    # 更新最后消息到仓储
                    await self.agent_context_repository.update_last_message(agent_id, message)
                    runtime_context.domain_context.update_last_message(message)

                    # 调用原始chat方法处理消息，并将事件放入队列
                    try:
                        async for event in self._run_flow(agent_id, message):
                            logger.info(f"Agent {agent_id} 输出事件: {event}")
                            if isinstance(event, PlanCreatedEvent):
                                await self.conversation_service.update_title(agent_id, event.plan.title)
                            # 将事件放入队列供传统chat方法使用
                            await runtime_context.event_queue.put(event)

                            # 如果有事件订阅服务，同时广播事件
                            if self.event_subscription_service:
                                try:
                                    await self.event_subscription_service.broadcast_event(agent_id, event)
                                except Exception as broadcast_error:
                                    logger.warning(f"Failed to broadcast event for agent {agent_id}: {str(broadcast_error)}")

                            # 更新context
                            self.agent_context_repository.update_context(runtime_context.domain_context)

                            # 如果消息队列不为空，优先处理下一条消息
                            if not runtime_context.msg_queue.empty():
                                break
                    except Exception as flow_error:
                        # 捕获并处理flow执行中的错误
                        logger.exception(f"Agent {agent_id} 在执行flow时发生错误: {str(flow_error)}")
                        error_event = ErrorEvent(error=f"Flow执行错误: {str(flow_error)}")
                        done_event = DoneEvent()

                        # 放入队列
                        await runtime_context.event_queue.put(error_event)
                        await runtime_context.event_queue.put(done_event)

                        # 广播错误事件
                        if self.event_subscription_service:
                            try:
                                await self.event_subscription_service.broadcast_event(agent_id, error_event)
                                await self.event_subscription_service.broadcast_event(agent_id, done_event)
                            except Exception as broadcast_error:
                                logger.warning(f"Failed to broadcast error event for agent {agent_id}: {str(broadcast_error)}")

                        # 更新状态为错误
                        await self.agent_context_repository.update_status(agent_id, "error")
                        runtime_context.domain_context.update_status("error")

                    runtime_context.msg_queue.task_done()
                    logger.debug(f"Agent {agent_id} 完成处理一条消息")
                except asyncio.TimeoutError:
                    # 超时只是用来检查是否需要退出循环，无需处理
                    continue

        except asyncio.CancelledError:
            # 任务被取消时的清理工作
            logger.info(f"Agent {agent_id} 任务被取消，正在进行清理...")

            # 获取上下文并进行资源清理
            runtime_context = self._runtime_contexts.get(agent_id)
            if runtime_context:
                # 通知客户端任务已取消
                try:
                    # 如果已经结束，则不需要额外操作
                    if runtime_context.task.done():
                        return

                    error_event = ErrorEvent(error="任务已被取消")
                    done_event = DoneEvent()

                    await runtime_context.event_queue.put(error_event)
                    await runtime_context.event_queue.put(done_event)

                    # 广播取消事件
                    if self.event_subscription_service:
                        try:
                            await self.event_subscription_service.broadcast_event(agent_id, error_event)
                            await self.event_subscription_service.broadcast_event(agent_id, done_event)
                        except Exception as broadcast_error:
                            logger.warning(f"Failed to broadcast cancellation event for agent {agent_id}: {str(broadcast_error)}")

                    # 更新状态为停止
                    await self.agent_context_repository.update_status(agent_id, "stopped")
                    runtime_context.domain_context.update_status("stopped")
                except Exception as e:
                    logger.error(f"取消通知发送失败: {str(e)}")

            logger.info(f"Agent {agent_id} 任务已优雅退出")
            # 重新抛出异常，确保调用者知道任务被取消
            raise
        except Exception as e:
            # 处理任务执行过程中的其他异常
            logger.exception(f"Agent {agent_id} 任务遇到异常: {str(e)}")
            runtime_context = self._runtime_contexts.get(agent_id)
            if runtime_context:
                try:
                    error_event = ErrorEvent(error=f"任务错误: {str(e)}")
                    done_event = DoneEvent()

                    await runtime_context.event_queue.put(error_event)
                    await runtime_context.event_queue.put(done_event)

                    # 广播异常事件
                    if self.event_subscription_service:
                        try:
                            await self.event_subscription_service.broadcast_event(agent_id, error_event)
                            await self.event_subscription_service.broadcast_event(agent_id, done_event)
                        except Exception as broadcast_error:
                            logger.warning(f"Failed to broadcast exception event for agent {agent_id}: {str(broadcast_error)}")

                    # 更新状态为错误
                    await self.agent_context_repository.update_status(agent_id, "error")
                    runtime_context.domain_context.update_status("error")
                except Exception as e2:
                    logger.error(f"错误通知发送失败: {str(e2)}")
        finally:
            # 确保即使在异常情况下也能进行资源清理
            logger.info(f"Agent {agent_id} 任务结束，正在清理最终资源")
            runtime_context = self._runtime_contexts.get(agent_id)
            if runtime_context:
                try:
                    if not runtime_context.event_queue.empty():
                        done_event = DoneEvent()
                        await runtime_context.event_queue.put(done_event)

                        # 广播最终完成事件
                        if self.event_subscription_service:
                            try:
                                await self.event_subscription_service.broadcast_event(agent_id, done_event)
                            except Exception as broadcast_error:
                                logger.warning(f"Failed to broadcast final done event for agent {agent_id}: {str(broadcast_error)}")
                except Exception as e:
                    logger.error(f"最终清理过程中出错: {str(e)}")

    async def _clear_queue(self, queue: asyncio.Queue) -> None:
        """清空指定队列"""
        cleared_count = 0
        while not queue.empty():
            try:
                queue.get_nowait()
                cleared_count += 1
            except asyncio.QueueEmpty:
                break
        logger.debug(f"Cleared queue, removed {cleared_count} items")

    async def close_agent(self, agent_id: str) -> bool:
        """清理指定Agent的资源"""
        logger.info(f"Starting to close Agent {agent_id}")
        runtime_context = self._runtime_contexts.get(agent_id)

        if not runtime_context:
            logger.warning(f"Attempted to close non-existent Agent {agent_id}")
            # 即使运行时上下文不存在，也尝试从仓储删除
            try:
                await self.agent_context_repository.delete_context(agent_id)
                logger.info(f"Deleted Agent {agent_id} from repository")
                return True
            except Exception as e:
                logger.error(f"Failed to delete Agent {agent_id} from repository: {str(e)}")
                return False

        # 1. 取消并清理任务
        if runtime_context.task and not runtime_context.task.done():
            logger.debug(f"Cancelling Agent {agent_id}'s task")
            runtime_context.task.cancel()
            try:
                await runtime_context.task
            except asyncio.CancelledError:
                pass

        # 2. 清理事件订阅
        if self.event_subscription_service:
            try:
                logger.debug(f"Cleaning up event subscriptions for Agent {agent_id}")
                await self.event_subscription_service.cleanup_agent_streams(agent_id)
            except Exception as e:
                logger.warning(f"Failed to cleanup event subscriptions for agent {agent_id}: {str(e)}")

        # 3. 清理队列资源
        logger.debug(f"Clearing Agent {agent_id}'s message queue")
        await self._clear_queue(runtime_context.msg_queue)
        logger.debug(f"Clearing Agent {agent_id}'s event queue")
        await self._clear_queue(runtime_context.event_queue)

        # 4. 销毁沙盒环境
        if runtime_context.sandbox:
            logger.debug(f"Destroying Agent {agent_id}'s sandbox environment")
            await runtime_context.sandbox.close()

        # 5. 从仓储删除
        try:
            await self.agent_context_repository.delete_context(agent_id)
            logger.debug(f"Deleted Agent {agent_id} from repository")
        except Exception as e:
            logger.error(f"Failed to delete Agent {agent_id} from repository: {str(e)}")

        # 6. 移除运行时资源集合
        self._runtime_contexts.pop(agent_id, None)
        logger.info(f"Agent {agent_id} has been fully closed and resources cleared")
        return True

    async def close_all(self) -> None:
        """清理所有Agent的资源"""
        logger.info(f"Starting to close all Agents, currently {len(self._runtime_contexts)} in runtime")
        # 逐个关闭运行时上下文中的agent
        for agent_id in list(self._runtime_contexts.keys()):
            await self.close_agent(agent_id)
        logger.info("All runtime Agents have been closed")

    @staticmethod
    def get_available_flows():
        """获取所有可用的flow类型"""
        return flow_factory.get_available_flows()

    async def delete_conversation_history(self, agent_id: str) -> bool:
        """删除会话历史"""
        return await self.conversation_service.delete_conversation(agent_id)

    async def list_conversations(self, user_id: Optional[str] = None, limit: int = 50, offset: int = 0):
        """列出会话历史"""
        return await self.conversation_service.list_conversations(user_id, limit, offset)

    async def send_message(
            self, 
            agent_id: str, 
            message: str, 
            sandbox: Sandbox,
            timestamp: Optional[int] = None, 
            file_ids: Optional[List[str]] = None
        ) -> bool:
        """
        发送消息到Agent（不返回事件流）

        这个方法只负责将消息放入Agent的处理队列，不返回事件流。
        客户端需要通过其他方式来接收事件。

        Args:
            agent_id: Agent ID
            message: 用户消息
            timestamp: 消息时间戳
            file_ids: 文件ID列表

        Returns:
            是否成功将消息放入队列

        Raises:
            ValueError: 当Agent不存在时
        """
        if file_ids is None:
            file_ids = []

        # 提供给agent的信息
        combined_message = message

        # 文件上传的固定目标路径
        destination_path = "/home/ubuntu"

        # 如果提供了文件ID列表，则先处理文件传输
        uploaded_files = []
        if file_ids and len(file_ids) > 0:
            logger.info(f"Processing {len(file_ids)} attached files for agent {agent_id}")

            # 处理每个文件
            for file_id in file_ids:
                try:
                    content, filename, _ = await self.user_service.get_file_content(file_id)
                    if content:
                        # 构建沙箱中的完整文件路径
                        sandbox_file_path = f"{destination_path}/{filename}"

                        # 传输文件到沙箱
                        result = await sandbox.file_upload(
                            file_path=sandbox_file_path,
                            content=content,
                            make_executable=False
                        )

                        # 将文件信息添加到上传列表
                        uploaded_files.append({
                            "id": file_id,
                            "filename": filename,
                            "path": sandbox_file_path,
                            "size": result.data.get("size", 0)
                        })

                        logger.info(f"Transferred file {filename} to sandbox at {sandbox_file_path}")
                    else:
                        logger.warning(f"Failed to get content for file {file_id}")
                except Exception as e:
                    logger.exception(f"Error transferring file {file_id} to sandbox: {str(e)}")

            # 如果成功上传了文件，将文件信息添加到消息中
            if uploaded_files:
                file_info = "\n\n附件信息:\n"
                for idx, file in enumerate(uploaded_files, 1):
                    file_info += f"{idx}. {file['filename']} - 位置: {file['path']}\n"

                # 将附件信息添加到原始消息
                combined_message = message + file_info

        logger.info(f"Sending message to agent {agent_id}: {combined_message[:50]}...")

        # 检查Agent是否存在（先检查运行时上下文）
        runtime_context = self._runtime_contexts.get(agent_id)
        if not runtime_context:
            # 尝试从仓储加载
            domain_context = await self.agent_context_repository.get_context(agent_id)
            if not domain_context:
                logger.error(f"Agent {agent_id} not found")
                raise ValueError(f"Agent {agent_id} not found")
            else:
                logger.info(f"Agent {agent_id} exists in repository but not in runtime context, needs restoration")
                raise AgentNotRunningError(f"Agent {agent_id} is not running")

        try:
            # 将消息放入队列（避免重复消息）
            domain_context = runtime_context.domain_context
            if not (domain_context.last_message == combined_message and domain_context.last_message_time == timestamp):
                user_input_event = UserInputEvent(message=message, file_ids=file_ids)
                await runtime_context.event_queue.put(user_input_event)
                # 如果有事件订阅服务，同时广播事件
                if self.event_subscription_service:
                    try:
                        await self.event_subscription_service.broadcast_event(agent_id, user_input_event)
                    except Exception as broadcast_error:
                        logger.warning(f"Failed to broadcast event for agent {agent_id}: {str(broadcast_error)}")
                await runtime_context.msg_queue.put(combined_message)

                # 更新最后消息到仓储和内存
                await self.agent_context_repository.update_last_message(agent_id, combined_message, timestamp)
                domain_context.update_last_message(combined_message, timestamp)

                logger.info(f"Message queued successfully for agent {agent_id}")

                # 确保任务正在运行
                self._ensure_task(agent_id)

                return True
            else:
                logger.info(f"Duplicate message ignored for agent {agent_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to queue message for agent {agent_id}: {str(e)}")
            raise RuntimeError(f"Failed to queue message: {str(e)}")

    # Agent上下文管理相关方法
    async def list_agent_contexts(self, user_id: Optional[str] = None, status: Optional[str] = None,
                                 limit: int = 50, offset: int = 0) -> List[DomainAgentContext]:
        """列出Agent上下文"""
        return await self.agent_context_repository.list_contexts(user_id, status, limit, offset)

    async def get_agent_context(self, agent_id: str) -> Optional[DomainAgentContext]:
        """获取Agent上下文"""
        # 首先尝试从运行时上下文获取
        runtime_context = self._runtime_contexts.get(agent_id)
        if runtime_context:
            return runtime_context.domain_context

        # 如果运行时上下文不存在，从仓储获取
        return await self.agent_context_repository.get_context(agent_id)

    async def update_agent_status(self, agent_id: str, status: str) -> bool:
        """更新Agent状态"""
        # 更新仓储
        success = await self.agent_context_repository.update_status(agent_id, status)

        # 更新运行时上下文
        runtime_context = self._runtime_contexts.get(agent_id)
        if runtime_context:
            runtime_context.domain_context.update_status(status)

        return success

    async def save_agent_context(self, agent: Agent, flow_id: str, sandbox_id: Optional[str] = None,
                                status: str = "created", last_message: Optional[str] = None,
                                meta_data: Optional[Dict] = None) -> DomainAgentContext:
        """保存Agent上下文到仓储"""
        # 创建领域上下文
        domain_context = DomainAgentContext(
            agent_id=agent.id,
            agent=agent,
            flow_id=flow_id,
            sandbox_id=sandbox_id,
            status=status,
            last_message=last_message,
            meta_data=meta_data or {}
        )

        # 保存到仓储
        await self.agent_context_repository.save_context(domain_context)
        logger.info(f"Agent上下文已保存到仓储: {agent.id}")

        return domain_context

    async def update_agent_last_message(self, agent_id: str, message: str, timestamp: Optional[datetime] = None) -> bool:
        """更新Agent最后消息"""
        if timestamp is None:
            timestamp = datetime.now()

        # 更新仓储
        success = await self.agent_context_repository.update_last_message(agent_id, message, timestamp)

        # 更新运行时上下文
        runtime_context = self._runtime_contexts.get(agent_id)
        if runtime_context:
            runtime_context.domain_context.update_last_message(message, timestamp)

        return success

    async def create_agent_context(self, agent: Agent, flow_id: str, sandbox_id: Optional[str] = None,
                                  status: str = "created", last_message: Optional[str] = None,
                                  meta_data: Optional[Dict] = None) -> DomainAgentContext:
        """创建Agent上下文（别名方法）"""
        return await self.save_agent_context(agent, flow_id, sandbox_id, status, last_message, meta_data)
