from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.interfaces.api.routes import router
from app.application.services.agent import AgentService
from app.infrastructure.config import get_settings
from app.infrastructure.logging import setup_logging
from app.interfaces.api.errors.exception_handlers import register_exception_handlers
from app.interfaces.api.middlewares import UserContextMiddleware, CodeServerSubdomainMiddleware
from app.infrastructure.tasks.cleanup_task import start_cleanup_task, stop_cleanup_task
from app.infrastructure.database.connection import init_database, close_database

# Initialize logging system
setup_logging()
logger = logging.getLogger(__name__)

# Load configuration
settings = get_settings()

# Create lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code executed on startup
    logger.info("Application startup - Manus AI Agent initializing")
    if settings.bypass_oauth2:
        logger.info("Development mode, bypassing OAuth2 authentication")
    
    # 初始化数据库（如果使用SQLite）
    if settings.database_type == "sqlite":
        try:
            await init_database()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise
    
    # 启动清理任务
    try:
        await start_cleanup_task(agent_service)
        logger.info("Subscription cleanup task started")
    except Exception as e:
        logger.error(f"Failed to start cleanup task: {str(e)}")
    
    yield
    
    # Code executed on shutdown
    logger.info("Application shutdown - Manus AI Agent terminating")
    
    # 停止清理任务
    try:
        await stop_cleanup_task()
        logger.info("Subscription cleanup task stopped")
    except Exception as e:
        logger.error(f"Failed to stop cleanup task: {str(e)}")
    
    # 关闭数据库连接（如果使用SQLite）
    if settings.database_type == "sqlite":
        try:
            await close_database()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Failed to close database connection: {str(e)}")
    
    # 关闭Agent服务
    await agent_service.close()

app = FastAPI(title="Manus AI Agent", lifespan=lifespan)
agent_service = AgentService()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middlewares
app.add_middleware(CodeServerSubdomainMiddleware)
app.add_middleware(UserContextMiddleware)

# Register exception handlers
register_exception_handlers(app)

# Register code server routes directly (without prefix for WebSocket support)
from app.interfaces.api.routes.code_server import router as code_server_router
app.include_router(code_server_router)

# Register API routes with prefix
app.include_router(router, prefix="/api/v1")