from abc import abstractmethod
from typing import Optional, List, Protocol

from app.domain.models.user import User, UserTask, UserFile


class UserRepository(Protocol):
    """用户仓储接口"""
    
    @abstractmethod
    async def save_user(self, user: User) -> None:
        """保存用户"""
        pass
    
    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[User]:
        """通过ID获取用户"""
        pass
    
    @abstractmethod
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        pass
    
    @abstractmethod
    async def save_task(self, task: UserTask) -> None:
        """保存用户任务"""
        pass
    
    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[UserTask]:
        """通过ID获取任务"""
        pass
    
    @abstractmethod
    async def get_user_tasks(self, user_id: str) -> List[UserTask]:
        """获取用户所有任务"""
        pass
    
    @abstractmethod
    async def save_file(self, file: UserFile) -> None:
        """保存用户文件"""
        pass
    
    @abstractmethod
    async def get_file(self, file_id: str) -> Optional[UserFile]:
        """通过ID获取文件"""
        pass
    
    @abstractmethod
    async def get_user_files(self, user_id: str) -> List[UserFile]:
        """获取用户所有文件"""
        pass 