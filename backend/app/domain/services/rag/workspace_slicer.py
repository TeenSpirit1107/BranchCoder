# workspace_slicer.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

# 来自你的 file_slicer.py
# - extract_slices(py_file: str) -> FileSlices
# - FileSlices(functions: List[FunctionSlice], classes: List[ClassSlice])
# - FunctionSlice(name, qualname, source, calls, called_by)
# - ClassSlice(name, qualname, source, methods)
from file_slicer import extract_slices, FileSlices, FunctionSlice, ClassSlice


# ========= 返回模型（扁平化；每个条目都带 file） =========

class WorkspaceFunction(BaseModel):
    file: str
    name: str
    qualname: str
    source: str
    calls: List[str] = Field(default_factory=list)      # 规范化后的 qualname 列表（仅限同文件内可解析者）
    called_by: List[str] = Field(default_factory=list)  # 规范化后的 qualname 列表（仅限同文件内可解析者）


class WorkspaceClass(BaseModel):
    file: str
    name: str
    qualname: str
    source: str
    methods: List[str] = Field(default_factory=list)    # 类内方法（qualname）


class SliceError(BaseModel):
    file: str
    message: str
    lineno: Optional[int] = None
    colno: Optional[int] = None


class WorkspaceSlices(BaseModel):
    root: str
    functions: List[WorkspaceFunction] = Field(default_factory=list)
    classes: List[WorkspaceClass] = Field(default_factory=list)
    errors: List[SliceError] = Field(default_factory=list)
    num_files_processed: int = 0
    num_functions: int = 0
    num_classes: int = 0


# ========= 工具函数 =========

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


# ========= 解析 helpers（同文件内把“原始 calls”解析为 qualname） =========

def _scopes_from_qualname(qualname: str) -> List[str]:
    return qualname.split(".")

def _resolve_callee_in_file(
    caller_qn: str,
    raw_callee: str,
    file_funcs: Set[str],
    file_classes: Set[str],
) -> Optional[str]:
    """
    把单文件内的 raw 调用字符串解析为“文件内定义的函数的 qualname”：
    - self.foo / cls.foo  → 当前类作用域里的方法
    - ClassName.foo       → 本文件内该类的方法（可嵌套类路径）
    - foo                 → 顶层或外层作用域的嵌套函数
    解析失败则返回 None。
    """
    scopes = _scopes_from_qualname(caller_qn)  # 例：['<module>', 'MyClass', 'run']
    module_prefix = scopes[0] if scopes else "<module>"
    scope_chain = scopes[:-1]  # 去掉自身函数名

    # 1) self./cls.
    if raw_callee.startswith("self.") or raw_callee.startswith("cls."):
        method = raw_callee.split(".", 1)[1]
        # 找最近的类作用域
        for i in range(len(scope_chain) - 1, -1, -1):
            cand = ".".join(scope_chain[: i + 1])  # 可能是类或外层函数
            if cand in file_classes:
                target_qn = f"{cand}.{method}"
                return target_qn if target_qn in file_funcs else None
        return None

    # 2) ClassName.foo / Outer.Inner.bar
    if "." in raw_callee:
        head, tail = raw_callee.split(".", 1)
        class_qn = f"{module_prefix}.{head}"  # 相对模块解析
        if class_qn in file_classes:
            tgt = f"{class_qn}.{tail}"
            return tgt if tgt in file_funcs else None
        return None

    # 3) 裸标识符 foo：先尝试顶层
    top_level = f"{module_prefix}.{raw_callee}"
    if top_level in file_funcs:
        return top_level

    # 再尝试外层嵌套：<module>.Outer... + raw
    for i in range(len(scope_chain), 0, -1):
        qual = ".".join(scope_chain[:i] + [raw_callee])
        if qual in file_funcs:
            return qual

    return None


# ========= 主入口（无 CLI） =========

def slice_workspace(
    workspace_root: str | Path,
    *,
    exclude_dirs: Optional[Set[str]] = None,
    max_file_mb: Optional[float] = 2.0,  # >2MB 的源码默认跳过，按需调整或设为 None
) -> WorkspaceSlices:
    """
    对整个 workspace 目录进行切片并整合结果。
    - 逐文件切片 -> 规范化 calls（仅同文件内可解析的目标，均为 qualname）
    - 回填 called_by（同文件内）
    - 扁平化为两个列表返回（每条都带 file）
    """
    root = Path(workspace_root).resolve()
    errors: List[SliceError] = []
    per_file: List[FileSlices] = []

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
            per_file.append(fs)
            processed += 1
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

    # === 在每个文件内：规范化 calls，并回填 called_by ===
    for fs in per_file:
        file_func_qns: Set[str] = {fn.qualname for fn in fs.functions}
        file_class_qns: Set[str] = {cls.qualname for cls in fs.classes}

        # 规范化 calls -> qualname（仅本文件内可解析）
        for fn in fs.functions:
            normalized: List[str] = []
            seen: Set[str] = set()
            for raw in fn.calls:
                tgt = _resolve_callee_in_file(
                    caller_qn=fn.qualname,
                    raw_callee=raw,
                    file_funcs=file_func_qns,
                    file_classes=file_class_qns,
                )
                if tgt and tgt not in seen:
                    seen.add(tgt)
                    normalized.append(tgt)
            fn.calls = normalized

        # 回填 called_by（用规范化后的 calls）
        for fn in fs.functions:
            fn.called_by = []
        index: Dict[str, FunctionSlice] = {fn.qualname: fn for fn in fs.functions}
        for fn in fs.functions:
            caller_qn = fn.qualname
            for callee_qn in fn.calls:
                callee_fn = index.get(callee_qn)
                if callee_fn and caller_qn not in callee_fn.called_by:
                    callee_fn.called_by.append(caller_qn)

    # === 扁平化汇总（每项都带 file） ===
    flat_functions: List[WorkspaceFunction] = []
    flat_classes: List[WorkspaceClass] = []

    for fs in per_file:
        # 函数
        for fn in fs.functions:
            flat_functions.append(
                WorkspaceFunction(
                    file=fs.file,
                    name=fn.name,
                    qualname=fn.qualname,
                    source=fn.source,
                    calls=list(fn.calls),
                    called_by=list(fn.called_by),
                )
            )
        # 类
        for cls in fs.classes:
            flat_classes.append(
                WorkspaceClass(
                    file=fs.file,
                    name=cls.name,
                    qualname=cls.qualname,
                    source=cls.source,
                    methods=list(cls.methods),
                )
            )

    return WorkspaceSlices(
        root=str(root),
        functions=flat_functions,
        classes=flat_classes,
        errors=errors,
        num_files_processed=processed,
        num_functions=num_functions,
        num_classes=num_classes,
    )
