# workspace_slicer.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

# 从你改名后的文件引入
# 期待 file_slicer.py 内有：
#   - extract_slices(py_file: str) -> FileSlices
#   - FileSlices(BaseModel) 包含 .file, .functions(List[FunctionSlice]), .classes(List[ClassSlice])
from file_slicer import extract_slices, FileSlices


# ========== 返回模型 ==========

class SliceError(BaseModel):
    file: str
    message: str
    lineno: Optional[int] = None
    colno: Optional[int] = None


class WorkspaceSlices(BaseModel):
    root: str
    files: List[FileSlices] = Field(default_factory=list)
    errors: List[SliceError] = Field(default_factory=list)
    num_files_processed: int = 0
    num_functions: int = 0
    num_classes: int = 0


# ========== 工具函数 ==========

DEFAULT_EXCLUDE_DIRS: Set[str] = {
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".venv", "venv", "env", ".idea", ".vscode", "node_modules",
    "dist", "build", "site-packages"
}

def _iter_py_files(
    root: Path,
    include_globs: Tuple[str, ...] = ("**/*.py",),
    exclude_dirs: Optional[Set[str]] = None,
) -> Iterable[Path]:
    """递归枚举 .py 文件（支持排除常见目录）。"""
    exclude_dirs = exclude_dirs or DEFAULT_EXCLUDE_DIRS
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs and not d.startswith(".#")]
        for name in filenames:
            if name.endswith(".py"):
                yield Path(dirpath) / name


def _under_size_limit(p: Path, max_file_mb: Optional[float]) -> bool:
    if max_file_mb is None:
        return True
    try:
        size = p.stat().st_size
    except Exception:
        return True
    return size <= max_file_mb * 1024 * 1024


# ========== 主入口（无 CLI） ==========

def slice_workspace(
    workspace_root: str | Path,
    *,
    exclude_dirs: Optional[Set[str]] = None,
    max_file_mb: Optional[float] = 2.0,  # >2MB 的源码默认跳过，按需调整或设为 None
) -> WorkspaceSlices:
    """
    对整个 workspace 目录进行切片并整合结果。

    返回：WorkspaceSlices(BaseModel)
      - files: List[FileSlices]
      - errors: 解析失败或跳过的文件信息
      - 统计字段：num_files_processed / num_functions / num_classes
    """
    root = Path(workspace_root).resolve()
    files: List[FileSlices] = []
    errors: List[SliceError] = []

    num_functions = 0
    num_classes = 0
    processed = 0

    for py_file in _iter_py_files(root, exclude_dirs=exclude_dirs):
        if not _under_size_limit(py_file, max_file_mb):
            errors.append(SliceError(
                file=str(py_file),
                message=f"Skipped: file too large (> {max_file_mb} MB)"
            ))
            continue

        try:
            fs = extract_slices(str(py_file))
            files.append(fs)
            processed += 1
            # 兼容你最新的 FunctionSlice/ClassSlice 结构
            num_functions += len(fs.functions)
            num_classes += len(fs.classes)
        except SyntaxError as e:
            errors.append(SliceError(
                file=str(py_file),
                message=f"SyntaxError: {e.msg}",
                lineno=getattr(e, "lineno", None),
                colno=getattr(e, "offset", None),
            ))
        except UnicodeDecodeError as e:
            errors.append(SliceError(
                file=str(py_file),
                message=f"UnicodeDecodeError: {e.reason}"
            ))
        except Exception as e:
            errors.append(SliceError(
                file=str(py_file),
                message=f"UnhandledError: {e.__class__.__name__}: {e}"
            ))

    return WorkspaceSlices(
        root=str(root),
        files=files,
        errors=errors,
        num_files_processed=processed,
        num_functions=num_functions,
        num_classes=num_classes,
    )
