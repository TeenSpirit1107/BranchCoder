"""用户仓储SQLite实现"""

import logging
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.external.user_repository import UserRepository
from app.domain.models.user import User, UserTask, UserFile
from app.infrastructure.database.connection import get_session, get_readonly_session
from app.infrastructure.database.models import UserORM, UserTaskORM, UserFileORM

logger = logging.getLogger(__name__)

class SQLiteUserRepository(UserRepository):
    """用户仓储SQLite实现"""
    
    def __init__(self, engine: AsyncEngine):
        """初始化用户仓储
        
        Args:
            engine: 数据库引擎
        """
        self.engine = engine
    
    def _orm_to_domain_user(self, user_orm: UserORM) -> User:
        """将ORM模型转换为领域模型"""
        return User(
            id=user_orm.id,
            email=user_orm.email,
            name=user_orm.name,
            groups=user_orm.groups or [],
            created_at=user_orm.created_at,
            last_login=user_orm.last_login
        )
    
    def _domain_to_orm_user(self, user: User) -> UserORM:
        """将领域模型转换为ORM模型"""
        return UserORM(
            id=user.id,
            email=user.email,
            name=user.name,
            groups=user.groups,
            created_at=user.created_at,
            last_login=user.last_login
        )
    
    def _orm_to_domain_task(self, task_orm: UserTaskORM) -> UserTask:
        """将任务ORM模型转换为领域模型"""
        return UserTask(
            id=task_orm.id,
            user_id=task_orm.user_id,
            agent_id=task_orm.agent_id,
            title=task_orm.title,
            status=task_orm.status,
            created_at=task_orm.created_at,
            completed_at=task_orm.completed_at,
            metadata=task_orm.meta_data or {}
        )
    
    def _domain_to_orm_task(self, task: UserTask) -> UserTaskORM:
        """将任务领域模型转换为ORM模型"""
        return UserTaskORM(
            id=task.id,
            user_id=task.user_id,
            agent_id=task.agent_id,
            title=task.title,
            status=task.status,
            created_at=task.created_at,
            completed_at=task.completed_at,
            meta_data=task.metadata
        )
    
    def _orm_to_domain_file(self, file_orm: UserFileORM) -> UserFile:
        """将文件ORM模型转换为领域模型"""
        return UserFile(
            id=file_orm.id,
            user_id=file_orm.user_id,
            filename=file_orm.filename,
            path=file_orm.path,
            created_at=file_orm.created_at,
            updated_at=file_orm.updated_at,
            metadata=file_orm.meta_data or {}
        )
    
    def _domain_to_orm_file(self, file: UserFile) -> UserFileORM:
        """将文件领域模型转换为ORM模型"""
        return UserFileORM(
            id=file.id,
            user_id=file.user_id,
            filename=file.filename,
            path=file.path,
            created_at=file.created_at,
            updated_at=file.updated_at,
            meta_data=file.metadata
        )
    
    async def save_user(self, user: User) -> None:
        """保存用户"""
        async with get_session(self.engine) as session:
            try:
                # 检查用户是否已存在
                stmt = select(UserORM).where(UserORM.id == user.id)
                result = await session.execute(stmt)
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    # 更新现有用户
                    existing_user.email = user.email
                    existing_user.name = user.name
                    existing_user.groups = user.groups
                    existing_user.last_login = user.last_login
                else:
                    # 创建新用户
                    user_orm = self._domain_to_orm_user(user)
                    session.add(user_orm)
                
                await session.commit()
                logger.debug(f"保存用户: {user.id}")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"保存用户失败: {user.id}, 错误: {str(e)}")
                raise
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """通过ID获取用户"""
        async with get_readonly_session(self.engine) as session:
            stmt = select(UserORM).where(UserORM.id == user_id)
            result = await session.execute(stmt)
            user_orm = result.scalar_one_or_none()
            
            if user_orm:
                return self._orm_to_domain_user(user_orm)
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        async with get_readonly_session(self.engine) as session:
            stmt = select(UserORM).where(UserORM.email == email)
            result = await session.execute(stmt)
            user_orm = result.scalar_one_or_none()
            
            if user_orm:
                return self._orm_to_domain_user(user_orm)
            return None
    
    async def save_task(self, task: UserTask) -> None:
        """保存用户任务"""
        async with get_session(self.engine) as session:
            try:
                # 检查任务是否已存在
                stmt = select(UserTaskORM).where(UserTaskORM.id == task.id)
                result = await session.execute(stmt)
                existing_task = result.scalar_one_or_none()
                
                if existing_task:
                    # 更新现有任务
                    existing_task.title = task.title
                    existing_task.status = task.status
                    existing_task.completed_at = task.completed_at
                    existing_task.meta_data = task.metadata
                else:
                    # 创建新任务
                    task_orm = self._domain_to_orm_task(task)
                    session.add(task_orm)
                
                await session.commit()
                logger.debug(f"保存用户任务: {task.id}, 用户: {task.user_id}")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"保存用户任务失败: {task.id}, 错误: {str(e)}")
                raise
    
    async def get_task(self, task_id: str) -> Optional[UserTask]:
        """通过ID获取任务"""
        async with get_readonly_session(self.engine) as session:
            stmt = select(UserTaskORM).where(UserTaskORM.id == task_id)
            result = await session.execute(stmt)
            task_orm = result.scalar_one_or_none()
            
            if task_orm:
                return self._orm_to_domain_task(task_orm)
            return None
    
    async def get_user_tasks(self, user_id: str) -> List[UserTask]:
        """获取用户所有任务"""
        async with get_readonly_session(self.engine) as session:
            stmt = select(UserTaskORM).where(UserTaskORM.user_id == user_id).order_by(UserTaskORM.created_at.desc())
            result = await session.execute(stmt)
            task_orms = result.scalars().all()
            
            return [self._orm_to_domain_task(task_orm) for task_orm in task_orms]
    
    async def save_file(self, file: UserFile) -> None:
        """保存用户文件"""
        async with get_session(self.engine) as session:
            try:
                # 检查文件是否已存在
                stmt = select(UserFileORM).where(UserFileORM.id == file.id)
                result = await session.execute(stmt)
                existing_file = result.scalar_one_or_none()
                
                if existing_file:
                    # 更新现有文件
                    existing_file.filename = file.filename
                    existing_file.path = file.path
                    existing_file.updated_at = file.updated_at
                    existing_file.meta_data = file.metadata
                else:
                    # 创建新文件
                    file_orm = self._domain_to_orm_file(file)
                    session.add(file_orm)
                
                await session.commit()
                logger.debug(f"保存用户文件: {file.id}, 用户: {file.user_id}")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"保存用户文件失败: {file.id}, 错误: {str(e)}")
                raise
    
    async def get_file(self, file_id: str) -> Optional[UserFile]:
        """通过ID获取文件"""
        async with get_readonly_session(self.engine) as session:
            stmt = select(UserFileORM).where(UserFileORM.id == file_id)
            result = await session.execute(stmt)
            file_orm = result.scalar_one_or_none()
            
            if file_orm:
                return self._orm_to_domain_file(file_orm)
            return None
    
    async def get_user_files(self, user_id: str) -> List[UserFile]:
        """获取用户所有文件"""
        async with get_readonly_session(self.engine) as session:
            stmt = select(UserFileORM).where(UserFileORM.user_id == user_id).order_by(UserFileORM.created_at.desc())
            result = await session.execute(stmt)
            file_orms = result.scalars().all()
            
            return [self._orm_to_domain_file(file_orm) for file_orm in file_orms] 