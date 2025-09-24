"""数据库连接管理 - 采用单例模式的DatabaseManager"""

import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker, AsyncEngine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base

from app.infrastructure.config import get_settings

logger = logging.getLogger(__name__)

# 全局Base类
Base = declarative_base()

class DatabaseManager:
    """数据库管理器 - 单例模式管理engine和session"""
    
    _instance: Optional['DatabaseManager'] = None
    _engine: Optional[AsyncEngine] = None
    _session_maker: dict[str, async_sessionmaker] = {}
    _readonly_session_maker: dict[str, async_sessionmaker] = {}
    
    def __new__(cls) -> 'DatabaseManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_engine(self) -> AsyncEngine:
        """获取数据库引擎（单例）"""
        if self._engine is None:
            settings = get_settings()
            # Use NullPool to avoid lingering connections in environments where
            # connections cannot be reliably checked back in by GC (threads/tasks).
            # This mitigates SAWarning about non-checked-in connections.
            self._engine = create_async_engine(
                settings.database_url,
                echo=False,
                poolclass=NullPool,
            )
            logger.info("数据库引擎已创建")
        return self._engine
    
    async def get_session_maker(self, engine: AsyncEngine) -> async_sessionmaker:
        """获取读写session maker（单例）"""
        if engine not in self._session_maker:
            self._session_maker[engine] = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
        return self._session_maker[engine]
    
    async def get_readonly_session_maker(self, engine: AsyncEngine) -> async_sessionmaker:
        """获取只读session maker（单例）"""
        if engine not in self._readonly_session_maker:
            self._readonly_session_maker[engine] = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                # 只读会话配置
                autoflush=False,  # 禁用自动刷新
                autocommit=False  # 禁用自动提交
            )
        return self._readonly_session_maker[engine]
    
    async def close(self):
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_maker = {}
            self._readonly_session_maker = {}
            logger.info("数据库连接已关闭")

# 全局数据库管理器实例
_db_manager = DatabaseManager()

def get_engine() -> AsyncEngine:
    """获取数据库引擎"""
    return _db_manager.get_engine()

@asynccontextmanager
async def get_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（读写模式）
    
    Args:
        engine: 数据库引擎
    """
    logger.debug(f"[DatabaseManager] 创建读写会话")
    # Session maker
    session_maker = await _db_manager.get_session_maker(engine)
    async with session_maker() as session:
        try:
            logger.debug(f"[DatabaseManager] 读写会话已创建")
            yield session
        except Exception as e:
            logger.debug(f"[DatabaseManager] 读写会话异常，执行回滚: {str(e)}")
            await session.rollback()
            raise
        finally:
            logger.debug(f"[DatabaseManager] 关闭读写会话")
            await session.close()

@asynccontextmanager
async def get_readonly_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """获取只读数据库会话（优化的只读模式）
    
    Args:
        engine: 数据库引擎
    """
    logger.debug(f"[DatabaseManager] 创建只读会话")
    # 只读Session maker
    session_maker = await _db_manager.get_readonly_session_maker(engine)
    async with session_maker() as session:
        try:
            logger.debug(f"[DatabaseManager] 只读会话已创建")
            # 对于只读操作，我们不需要开启事务
            # SQLAlchemy会在需要时自动开启只读事务
            yield session
        except Exception as e:
            logger.debug(f"[DatabaseManager] 只读会话异常: {str(e)}")
            # 只读会话通常不需要回滚，但为了安全起见还是执行
            try:
                await session.rollback()
            except Exception as rollback_e:
                logger.debug(f"[DatabaseManager] 只读会话回滚异常（可忽略）: {str(rollback_e)}")
            raise
        finally:
            logger.debug(f"[DatabaseManager] 关闭只读会话")
            await session.close()

async def close_database():
    """关闭数据库连接"""
    await _db_manager.close()

async def init_database():
    """初始化数据库"""
    engine = get_engine()
    # 确保数据库引擎已创建，初始化表结构
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库初始化完成")
