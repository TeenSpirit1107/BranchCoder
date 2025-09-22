"""文件处理工具函数。"""

import os
import shutil
import uuid
import logging
from datetime import datetime
from typing import Optional, BinaryIO, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# 文件上传的根目录
UPLOAD_DIR = Path("./uploads")

def ensure_upload_dir() -> None:
    """确保上传目录存在。"""
    if not UPLOAD_DIR.exists():
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"已创建上传目录：{UPLOAD_DIR}")

def save_uploaded_file(file: BinaryIO, filename: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    保存上传的文件并返回文件信息。
    
    Args:
        file: 上传的文件对象（必须有 read 方法）
        filename: 文件名
        user_id: 用户ID
        metadata: 文件元数据
        
    Returns:
        包含文件信息的字典
    """
    # 确保上传目录存在
    ensure_upload_dir()
    
    # 为用户创建独立的目录
    user_dir = UPLOAD_DIR / user_id
    if not user_dir.exists():
        user_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成唯一的文件名（使用 UUID 和原始文件名）
    # 先获取文件扩展名
    _, file_ext = os.path.splitext(filename)
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = user_dir / unique_filename
    
    # 保存文件
    try:
        with open(file_path, "wb") as dest_file:
            # 读取并写入文件内容
            content = file.read()
            dest_file.write(content)
        
        # 返回文件信息
        return {
            "filename": filename,  # 原始文件名
            "path": str(file_path),  # 保存路径
            "size": os.path.getsize(file_path),  # 文件大小
            "created_at": datetime.now().isoformat(),  # 创建时间
            "metadata": metadata or {}  # 元数据
        }
    except Exception as e:
        logger.error(f"保存文件时出错: {str(e)}")
        # 如果文件已创建但保存过程中出错，尝试删除文件
        if file_path.exists():
            os.remove(file_path)
        raise 