#!/usr/bin/env python3
"""
Logger module for Python services
Provides a reusable logger class that outputs to stderr and optionally to log files.
"""

import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class Logger:
    """
    A reusable logger class that writes logs to stderr (and optionally to a file).
    This ensures logs don't interfere with stdout JSON output for service communication.
    """
    
    def __init__(
        self,
        name: str,
        log_to_file: bool = False,
        log_file_path: Optional[str] = None,
        log_level: int = logging.DEBUG,
        base_dir: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB default
        backup_count: int = 5  # Keep 5 backup files
    ):
        """
        Initialize a logger instance.
        
        Args:
            name: Logger name (typically module name like 'ai_service', 'worker', etc.)
            log_to_file: Whether to also write logs to a file (default: False)
            log_file_path: Path to log file (if None, uses default: {name}.log in project root directory)
            log_level: Logging level (default: logging.DEBUG)
            base_dir: Base directory for log files (if None, uses project root directory)
            max_bytes: Maximum size of log file before rotation (default: 10MB)
            backup_count: Number of backup log files to keep (default: 5)
        """
        self.name = name
        
        # TODO(Yimeng: remove this after debugging)
        # self.log_to_file = log_to_file
        self.log_to_file = True
        
        self.log_level = log_level
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        
        # Get logger instance
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create formatter with timestamp, level, and message
        self.formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Handler for stderr - always enabled
        self._setup_stderr_handler()
        
        # Handler for log file - optional
        if self.log_to_file:
            if log_file_path is None:
                # Default log file location
                if base_dir:
                    log_dir = Path(base_dir)
                else:
                    # Default to project root directory
                    log_dir = Path("/home/ym/Documents/Projects/Course/CSC4100/group_project/BranchCoder/logs/logs")
                    # TODO(Yimeng): revert to previous implementation
                    # log_dir = Path(__file__).parent
                log_file_path = log_dir / f"{name}.log"
            
            self._setup_file_handler(log_file_path, max_bytes, backup_count)
    
    def _setup_stderr_handler(self):
        """Setup stderr handler for logging."""
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(self.log_level)
        stderr_handler.setFormatter(self.formatter)
        self.logger.addHandler(stderr_handler)
    
    def _setup_file_handler(self, log_file_path: Path, max_bytes: int, backup_count: int):
        """Setup rotating file handler for logging."""
        try:
            # Ensure log directory exists
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use RotatingFileHandler for log rotation
            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8',
                mode='a'
            )
            file_handler.setLevel(self.log_level)
            file_handler.setFormatter(self.formatter)
            self.logger.addHandler(file_handler)
            
            self.logger.info(
                f"Logging to file: {log_file_path} "
                f"(max size: {max_bytes / (1024 * 1024):.1f}MB, backups: {backup_count})"
            )
        except Exception as e:
            # Use stderr to report file logging setup failure
            sys.stderr.write(f"ERROR: Failed to setup file logging to {log_file_path}: {e}\n")
    
    def debug(self, message: str):
        """Log a debug message."""
        self.logger.debug(message)
    
    def info(self, message: str):
        """Log an info message."""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log a warning message."""
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False):
        """Log an error message."""
        self.logger.error(message, exc_info=exc_info)
    
    def critical(self, message: str):
        """Log a critical message."""
        self.logger.critical(message)
    
    def get_logger(self) -> logging.Logger:
        """
        Get the underlying logging.Logger instance.
        Useful for advanced usage scenarios.
        
        Returns:
            The logging.Logger instance
        """
        return self.logger
    
    def set_level(self, level: int):
        """Set the logging level for all handlers."""
        self.log_level = level
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)

