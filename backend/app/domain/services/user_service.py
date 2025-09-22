"""User domain service."""

import logging
import uuid
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from ...domain.models.user import User, UserTask, UserFile
from ...domain.external.user_repository import UserRepository

logger = logging.getLogger(__name__)

class UserService:
    """领域服务：用户管理"""
    
    def __init__(self, user_repository: UserRepository):
        """
        初始化用户服务
        
        Args:
            user_repository: 用户仓储接口
        """
        self.user_repository = user_repository
    
    async def get_or_create_user(self, user_info: Dict[str, Any]) -> User:
        """
        获取现有用户或创建新用户
        
        Args:
            user_info: 从OAuth获取的用户信息
            
        Returns:
            User 对象
        """
        user_id = user_info.get("user_id")
        email = user_info.get("email")
        
        if not user_id and not email:
            raise ValueError("需要提供用户ID或邮箱")
        
        # 尝试通过ID查找用户
        if user_id:
            user = await self.user_repository.get_user(user_id)
            if user:
                user.last_login = datetime.now()
                await self.user_repository.save_user(user)
                return user
        
        # 尝试通过邮箱查找用户
        if email:
            user = await self.user_repository.get_user_by_email(email)
            if user:
                user.last_login = datetime.now()
                await self.user_repository.save_user(user)
                return user
        
        # 创建新用户
        if not user_id:
            user_id = str(uuid.uuid4())
            user_info["user_id"] = user_id
            
        user = User.from_oauth(user_info)
        await self.user_repository.save_user(user)
        logger.info(f"创建新用户: {user_id}, 邮箱: {email}")
        
        return user
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """
        通过ID获取用户
        
        Args:
            user_id: 用户ID
            
        Returns:
            User对象，如果未找到则返回None
        """
        return await self.user_repository.get_user(user_id)
    
    async def create_task(self, user_id: str, agent_id: str, title: str, metadata: Dict[str, Any] = None) -> UserTask:
        """
        为用户创建新任务
        
        Args:
            user_id: 用户ID
            agent_id: Agent ID
            title: 任务标题
            metadata: 可选的任务元数据
            
        Returns:
            创建的任务
        """
        # 检查用户是否存在
        user = await self.user_repository.get_user(user_id)
        if not user:
            raise ValueError(f"未找到用户: {user_id}")
        
        task_id = str(uuid.uuid4())
        task = UserTask(
            id=task_id,
            user_id=user_id,
            agent_id=agent_id,
            title=title,
            status="in_progress",
            metadata=metadata or {}
        )
        
        await self.user_repository.save_task(task)
        
        logger.info(f"为用户 {user_id} 创建任务 {task_id}")
        return task
    
    async def complete_task(self, task_id: str) -> Optional[UserTask]:
        """
        将任务标记为已完成
        
        Args:
            task_id: 任务ID
            
        Returns:
            更新后的任务，如果未找到则返回None
        """
        task = await self.user_repository.get_task(task_id)
        if not task:
            logger.warning(f"未找到任务: {task_id}")
            return None
        
        task.complete()
        await self.user_repository.save_task(task)
        
        logger.info(f"完成任务 {task_id}")
        return task
    
    async def create_file(self, user_id: str, filename: str, path: str, metadata: Dict[str, Any] = None) -> UserFile:
        """
        为用户创建新文件
        
        Args:
            user_id: 用户ID
            filename: 文件名
            path: 文件路径
            metadata: 可选的文件元数据
            
        Returns:
            创建的文件
        """
        # 检查用户是否存在
        user = await self.user_repository.get_user(user_id)
        if not user:
            raise ValueError(f"未找到用户: {user_id}")
        
        file_id = str(uuid.uuid4())
        file = UserFile(
            id=file_id,
            user_id=user_id,
            filename=filename,
            path=path,
            metadata=metadata or {}
        )
        
        await self.user_repository.save_file(file)
        
        logger.info(f"为用户 {user_id} 创建文件 {file_id}")
        return file
    
    async def get_user_tasks(self, user_id: str) -> List[UserTask]:
        """
        获取用户所有任务
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户任务列表
        """
        # 检查用户是否存在
        user = await self.user_repository.get_user(user_id)
        if not user:
            logger.warning(f"未找到用户: {user_id}")
            return []
        
        return await self.user_repository.get_user_tasks(user_id)
    
    async def get_user_files(self, user_id: str) -> List[UserFile]:
        """
        获取用户所有文件
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户文件列表
        """
        # 检查用户是否存在
        user = await self.user_repository.get_user(user_id)
        if not user:
            logger.warning(f"未找到用户: {user_id}")
            return []
        
        return await self.user_repository.get_user_files(user_id)
        
    async def get_file_by_id(self, file_id: str) -> Optional[UserFile]:
        """
        根据文件ID获取文件信息
        
        Args:
            file_id: 文件ID
            
        Returns:
            UserFile对象，如果未找到则返回None
        """
        return await self.user_repository.get_file(file_id)
        
    async def get_file_content(self, file_id: str) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
        """
        根据文件ID获取文件二进制内容
        
        Args:
            file_id: 文件ID
            
        Returns:
            元组(文件内容, 文件名, 内容类型)，如果未找到则返回(None, None, None)
        """
        file = await self.user_repository.get_file(file_id)
        if not file:
            logger.warning(f"未找到文件: {file_id}")
            return None, None, None
            
        file_path = file.path
        if not os.path.exists(file_path):
            logger.warning(f"未找到文件路径: {file_path}")
            return None, None, None
            
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                
            # 尝试从元数据获取内容类型
            content_type = file.metadata.get('content_type', 'application/octet-stream')
                
            return content, file.filename, content_type
        except Exception as e:
            logger.error(f"读取文件 {file_id} 出错: {str(e)}")
            return None, None, None 