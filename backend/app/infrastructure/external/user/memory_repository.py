"""用户仓储内存实现"""

import logging
from typing import Optional, List, Dict

from app.domain.models.conversation import ConversationHistory, ConversationEvent
from app.domain.models.user import User, UserTask, UserFile

logger = logging.getLogger(__name__)


class UserDataStore:
    """用户数据存储"""

    def __init__(self):
        # 用户表: user_id -> User
        self.users: Dict[str, User] = {}
        # 用户邮箱索引: email -> user_id
        self.email_index: Dict[str, str] = {}
        # 任务表: task_id -> UserTask
        self.tasks: Dict[str, UserTask] = {}
        # 用户任务索引: user_id -> [task_id]
        self.user_tasks_index: Dict[str, List[str]] = {}
        # 文件表: file_id -> UserFile
        self.files: Dict[str, UserFile] = {}
        # 用户文件索引: user_id -> [file_id]
        self.user_files_index: Dict[str, List[str]] = {}


class ConversationDataStore:
    """对话数据存储"""

    def __init__(self):
        # 会话历史表: agent_id -> ConversationHistory
        self.histories: Dict[str, ConversationHistory] = {}
        # 事件表: (agent_id, sequence) -> ConversationEvent
        self.events: Dict[str, Dict[int, ConversationEvent]] = {}
        # 用户会话索引: user_id -> [agent_id]
        self.user_histories_index: Dict[str, List[str]] = {}


class AgentContextDataStore:
    """Agent上下文数据存储"""

    def __init__(self):
        # Agent上下文表: agent_id -> AgentContext
        self.contexts: Dict[str, 'AgentContext'] = {}
        # 用户Agent索引: user_id -> [agent_id]
        self.user_agents_index: Dict[str, List[str]] = {}
        # 状态索引: status -> [agent_id]
        self.status_index: Dict[str, List[str]] = {}
        # 沙盒索引: sandbox_id -> agent_id
        self.sandbox_index: Dict[str, str] = {}


user_data_store = UserDataStore()
conversation_data_store = ConversationDataStore()
agent_context_data_store = AgentContextDataStore()


class MemoryUserRepository:
    """用户仓储内存实现"""
    
    async def save_user(self, user: User) -> None:
        """保存用户"""
        user_data_store.users[user.id] = user
        
        # 更新邮箱索引
        if user.email:
            user_data_store.email_index[user.email] = user.id
            
        logger.debug(f"保存用户: {user.id}")
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """通过ID获取用户"""
        return user_data_store.users.get(user_id)
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        user_id = user_data_store.email_index.get(email)
        if user_id:
            return user_data_store.users.get(user_id)
        return None
    
    async def save_task(self, task: UserTask) -> None:
        """保存用户任务"""
        user_data_store.tasks[task.id] = task
        
        # 更新用户任务索引
        if task.user_id not in user_data_store.user_tasks_index:
            user_data_store.user_tasks_index[task.user_id] = []
            
        if task.id not in user_data_store.user_tasks_index[task.user_id]:
            user_data_store.user_tasks_index[task.user_id].append(task.id)
            
        logger.debug(f"保存用户任务: {task.id}, 用户: {task.user_id}")
    
    async def get_task(self, task_id: str) -> Optional[UserTask]:
        """通过ID获取任务"""
        return user_data_store.tasks.get(task_id)
    
    async def get_user_tasks(self, user_id: str) -> List[UserTask]:
        """获取用户所有任务"""
        task_ids = user_data_store.user_tasks_index.get(user_id, [])
        return [user_data_store.tasks[task_id] for task_id in task_ids 
                if task_id in user_data_store.tasks]
    
    async def save_file(self, file: UserFile) -> None:
        """保存用户文件"""
        user_data_store.files[file.id] = file
        
        # 更新用户文件索引
        if file.user_id not in user_data_store.user_files_index:
            user_data_store.user_files_index[file.user_id] = []
            
        if file.id not in user_data_store.user_files_index[file.user_id]:
            user_data_store.user_files_index[file.user_id].append(file.id)
            
        logger.debug(f"保存用户文件: {file.id}, 用户: {file.user_id}")
    
    async def get_file(self, file_id: str) -> Optional[UserFile]:
        """通过ID获取文件"""
        return user_data_store.files.get(file_id)
    
    async def get_user_files(self, user_id: str) -> List[UserFile]:
        """获取用户所有文件"""
        file_ids = user_data_store.user_files_index.get(user_id, [])
        return [user_data_store.files[file_id] for file_id in file_ids 
                if file_id in user_data_store.files]
