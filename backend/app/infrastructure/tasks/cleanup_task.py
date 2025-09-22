import asyncio
import logging
from typing import Optional
from app.application.services.agent import AgentService

logger = logging.getLogger(__name__)


class SubscriptionCleanupTask:
    """订阅清理后台任务"""

    def __init__(self, agent_service: AgentService, cleanup_interval_minutes: int = 30, timeout_minutes: int = 60):
        self.agent_service = agent_service
        self.cleanup_interval_minutes = cleanup_interval_minutes
        self.timeout_minutes = timeout_minutes
        self.task: Optional[asyncio.Task] = None
        self.running = False

    async def start(self) -> None:
        """启动清理任务"""
        if self.running:
            logger.warning("Cleanup task is already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._cleanup_loop())
        logger.info(f"Started subscription cleanup task with interval {self.cleanup_interval_minutes} minutes")

    async def stop(self) -> None:
        """停止清理任务"""
        if not self.running:
            return

        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

        logger.info("Stopped subscription cleanup task")

    async def _cleanup_loop(self) -> None:
        """清理循环"""
        try:
            while self.running:
                try:
                    # 执行清理
                    cleaned_count = await self.agent_service.cleanup_inactive_subscriptions(self.timeout_minutes)
                    if cleaned_count > 0:
                        logger.info(f"Cleaned up {cleaned_count} inactive subscriptions")

                    # 等待下次清理
                    await asyncio.sleep(self.cleanup_interval_minutes * 60)

                except Exception as e:
                    logger.error(f"Error in cleanup task: {str(e)}")
                    # 出错后等待一段时间再重试
                    await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("Cleanup task was cancelled")
            raise
        except Exception as e:
            logger.error(f"Cleanup task failed: {str(e)}")
        finally:
            self.running = False


# 全局清理任务实例
_cleanup_task: Optional[SubscriptionCleanupTask] = None


async def start_cleanup_task(agent_service: AgentService) -> None:
    """启动全局清理任务"""
    global _cleanup_task
    
    if _cleanup_task is None:
        _cleanup_task = SubscriptionCleanupTask(agent_service)
    
    await _cleanup_task.start()


async def stop_cleanup_task() -> None:
    """停止全局清理任务"""
    global _cleanup_task
    
    if _cleanup_task:
        await _cleanup_task.stop()
        _cleanup_task = None 