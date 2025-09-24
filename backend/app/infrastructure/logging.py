import logging
import sys
import os
from .config import get_settings



class ComponentLoggerFilter(logging.Filter):
    """更灵活的组件日志过滤器"""
    def __init__(self, show_sub_planners: bool = True, show_super_planner: bool = True):
        super().__init__()
        self.show_sub_planners = show_sub_planners
        self.show_super_planner = show_super_planner
    
    def filter(self, record):
        # 根据配置决定是否显示super_planner相关日志
        if self.show_super_planner and (record.name.startswith('super_planner') or record.name.startswith('super_planner_flow')):
            return True
        # 根据配置决定是否显示sub_planner相关日志
        if self.show_sub_planners and (record.name.startswith('sub_planner') or record.name.startswith('sub_planner_flow')):
            return True
        return False
    
def _remove_existing_log_file(log_file_path: str):
    """删除已存在的日志文件"""
    if os.path.exists(log_file_path):
        try:
            os.remove(log_file_path)
        except OSError:
            # 如果删除失败，忽略错误继续执行
            pass

def setup_logging():
    """
    Configure the application logging system
    
    Sets up log levels, formatters, and handlers for both console and file output.
    Uses overwrite strategy to replace existing log files on each initialization.
    """
    # Get configuration
    settings = get_settings()
    
    # Get root logger
    root_logger = logging.getLogger()

    # Clear existing handlers to avoid duplicate outputs from other frameworks (e.g., uvicorn)
    # root_logger.handlers.clear()
    
    # Set root log level
    log_level = getattr(logging, settings.log_level)
    root_logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create console handler (show all by default; filtering can be enabled separately if needed)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)  # 确保控制台处理器级别足够低
    
    # 添加组件过滤器，默认显示super_planner和sub_planner的日志
    # console_handler.addFilter(ComponentLoggerFilter(show_sub_planners=True, show_super_planner=True))
    
    # Add handlers to root logger
    root_logger.addHandler(console_handler)
    
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Create file handler for general application logs (append mode to avoid losing history)
    app_log_path = os.path.join(logs_dir, "app.log")
    file_handler = logging.FileHandler(
        app_log_path,
        mode='w',  # 覆盖写入模式
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)

    # 添加Agent单独日志记录
    # 如果以agent.开头，则设置为DEBUG，添加文件Handler
    for logger_name in root_logger.manager.loggerDict:
        if logger_name.startswith("agent."):
            # 创建文件Handler
            file_handler = logging.FileHandler(
                os.path.join(logs_dir, f"{logger_name}.log"),
                mode='w',  # 覆盖写入模式
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)
            _logger = logging.getLogger(logger_name)
            _logger.addHandler(file_handler)

    # 配置SQLAlchemy相关日志器的级别，减少冗余日志
    sqlalchemy_loggers = [
        'sqlalchemy.engine',
        'sqlalchemy.dialects',
        'sqlalchemy.pool',
        'sqlalchemy.orm'
    ]
    
    for logger_name in sqlalchemy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
    
    # Log initialization complete
    root_logger.info("Logging system initialized - Console and file logging active")
    root_logger.info("SQLAlchemy logging level set to WARNING to reduce verbosity")

    # Traceloop


def setup_plan_act_logger(agent_id: str) -> logging.Logger:
    """
    为特定的Agent创建专门的plan_act日志记录器
    
    Args:
        agent_id: Agent的唯一标识符
        
    Returns:
        配置好的日志记录器
    """
    logger_name = f"plan_act.{agent_id}"
    logger = logging.getLogger(logger_name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
    
    # 设置日志级别
    logger.setLevel(logging.INFO)
    
    # 创建logs目录
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # 创建plan_act专用目录
    plan_act_dir = os.path.join(logs_dir, "plan_act")
    if not os.path.exists(plan_act_dir):
        os.makedirs(plan_act_dir)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 删除已存在的日志文件并创建新的文件处理器
    log_file_path = os.path.join(plan_act_dir, f"{agent_id}.log")
    _remove_existing_log_file(log_file_path)
    
    file_handler = logging.FileHandler(
        log_file_path,
        mode='w',  # 覆盖写入模式
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # 添加处理器
    logger.addHandler(file_handler)
    
    # 防止日志向上传播到根日志器
    logger.propagate = False
    
    return logger

def setup_agent_logger(agent_id: str) -> logging.Logger:
    """
    为特定的Agent创建专门的agent日志记录器
    """
    logger_name = f"agent.{agent_id}"
    logger = logging.getLogger(logger_name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
    
    # 设置日志级别
    logger.setLevel(logging.INFO)
    
    # 创建logs目录
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # 创建agent专用目录
    agent_dir = os.path.join(logs_dir, "agent")
    if not os.path.exists(agent_dir):
        os.makedirs(agent_dir)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 删除已存在的日志文件并创建新的文件处理器
    log_file_path = os.path.join(agent_dir, f"{agent_id}.log")
    _remove_existing_log_file(log_file_path)
    
    file_handler = logging.FileHandler(
        log_file_path,
        mode='w',  # 覆盖写入模式
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # 添加处理器
    logger.addHandler(file_handler)
    
    # 防止日志向上传播到根日志器
    logger.propagate = False
    
    return logger

def setup_super_planner_flow_logger(agent_id: str) -> logging.Logger:
    """
    为特定的Agent创建专门的super_planner日志记录器
    
    Args:
        agent_id: Agent的唯一标识符
        
    Returns:
        配置好的日志记录器
    """
    logger_name = f"super_planner_flow.{agent_id}"
    logger = logging.getLogger(logger_name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
    
    # 设置日志级别
    logger.setLevel(logging.INFO)
    
    # 创建logs目录
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # 创建super_planner专用目录
    super_planner_flow_dir = os.path.join(logs_dir, "super_planner_flow")
    if not os.path.exists(super_planner_flow_dir):
        os.makedirs(super_planner_flow_dir)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 删除已存在的日志文件并创建新的文件处理器
    log_file_path = os.path.join(super_planner_flow_dir, f"{agent_id}.log")
    _remove_existing_log_file(log_file_path)
    
    file_handler = logging.FileHandler(
        log_file_path,
        mode='w',  # 覆盖写入模式
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # 添加处理器
    logger.addHandler(file_handler)
    
    # 不允许日志向上传播到根日志器
    logger.propagate = False
    
    return logger

def setup_super_planner_agent_logger(agent_id: str) -> logging.Logger:
    """为SuperPlannerAgent创建专门的日志记录器"""
    logger_name = f"super_planner.{agent_id}"
    logger = logging.getLogger(logger_name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # 创建logs目录
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # 创建super_planner专用目录
    super_planner_dir = os.path.join(logs_dir, "super_planner")
    if not os.path.exists(super_planner_dir):
        os.makedirs(super_planner_dir)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 删除已存在的日志文件并创建新的文件处理器
    log_file_path = os.path.join(super_planner_dir, f"{agent_id}.log")
    _remove_existing_log_file(log_file_path)
    
    file_handler = logging.FileHandler(
        log_file_path,
        mode='w',  # 覆盖写入模式
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # 添加处理器
    logger.addHandler(file_handler)
    
    # 不允许日志向上传播到根日志器
    logger.propagate = False
    
    return logger

def setup_sub_planner_interface_logger(agent_id: str) -> logging.Logger:
    """为SubPlannerInterface创建专门的日志记录器"""
    logger_name = f"sub_planner_interface.{agent_id}"
    logger = logging.getLogger(logger_name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # 创建sub_planner_interface专用目录
    logs_dir = "logs"
    sub_planner_interface_dir = os.path.join(logs_dir, "sub_planner_interface")
    if not os.path.exists(sub_planner_interface_dir):
        os.makedirs(sub_planner_interface_dir)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    log_file_path = os.path.join(sub_planner_interface_dir, f"{agent_id}.log")
    _remove_existing_log_file(log_file_path)
    
    file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    logger.addHandler(file_handler)
    
    # 不允许日志向上传播到根日志器
    logger.propagate = False
    
    return logger

def setup_sub_planner_agent_logger(agent_id: str) -> logging.Logger:
    """为SubPlannerAgent创建专门的日志记录器"""
    logger_name = f"sub_planner_agent.{agent_id}"
    logger = logging.getLogger(logger_name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # 创建sub_planner_agent专用目录
    logs_dir = "logs"
    sub_planner_agent_dir = os.path.join(logs_dir, "sub_planner_agent")
    if not os.path.exists(sub_planner_agent_dir):
        os.makedirs(sub_planner_agent_dir)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    log_file_path = os.path.join(sub_planner_agent_dir, f"{agent_id}.log")
    _remove_existing_log_file(log_file_path)
    
    file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    logger.addHandler(file_handler)
    
    # 不允许日志向上传播到根日志器
    logger.propagate = False
    
    return logger

def setup_search_flow_logger(agent_id: str) -> logging.Logger:
    """为SearchFlow创建专门的日志记录器"""
    logger_name = f"search_flow.{agent_id}"
    logger = logging.getLogger(logger_name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # 创建logs目录
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # 创建search_flow专用目录
    search_flow_dir = os.path.join(logs_dir, "search_flow")
    if not os.path.exists(search_flow_dir):
        os.makedirs(search_flow_dir)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 删除已存在的日志文件并创建新的文件处理器
    log_file_path = os.path.join(search_flow_dir, f"{agent_id}.log")
    _remove_existing_log_file(log_file_path)
    
    file_handler = logging.FileHandler(
        log_file_path,
        mode='w',  # 覆盖写入模式
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # 添加处理器
    logger.addHandler(file_handler)
    
    # 不允许日志向上传播到根日志器
    logger.propagate = False
    
    return logger

def setup_sub_planner_flow_logger(agent_id: str) -> logging.Logger:
    """为SubPlannerFlow创建专门的日志记录器"""
    logger_name = f"sub_planner_flow.{agent_id}"
    logger = logging.getLogger(logger_name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # 创建logs目录
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # 创建sub_planner_flow专用目录
    sub_planner_flow_dir = os.path.join(logs_dir, "sub_planner_flow")
    if not os.path.exists(sub_planner_flow_dir):
        os.makedirs(sub_planner_flow_dir)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 删除已存在的日志文件并创建新的文件处理器
    log_file_path = os.path.join(sub_planner_flow_dir, f"{agent_id}.log")
    _remove_existing_log_file(log_file_path)
    
    file_handler = logging.FileHandler(
        log_file_path,
        mode='w',  # 覆盖写入模式
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # 添加处理器
    logger.addHandler(file_handler)
    
    # 不允许日志向上传播到根日志器
    logger.propagate = False
    
    return logger

def setup_mcp_flow_logger(agent_id: str) -> logging.Logger:
    """为McpFlow创建专门的日志记录器"""
    logger_name = f"mcp_flow.{agent_id}"
    logger = logging.getLogger(logger_name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # 创建logs目录
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # 创建mcp_flow专用目录
    mcp_flow_dir = os.path.join(logs_dir, "mcp_flow")
    if not os.path.exists(mcp_flow_dir):
        os.makedirs(mcp_flow_dir)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 删除已存在的日志文件并创建新的文件处理器
    log_file_path = os.path.join(mcp_flow_dir, f"{agent_id}.log")
    _remove_existing_log_file(log_file_path)
    
    file_handler = logging.FileHandler(
        log_file_path,
        mode='w',  # 覆盖写入模式
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # 添加处理器
    logger.addHandler(file_handler)
    
    # 不允许日志向上传播到根日志器
    logger.propagate = False
    
    return logger