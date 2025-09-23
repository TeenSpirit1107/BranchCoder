from __future__ import annotations

import ast
import os
import tokenize
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from pydantic import BaseModel, Field

# ==========================================================
#                         Models
# ==========================================================

class FunctionSlice(BaseModel):
    """单个函数/方法的切片 + 调用信息（原始/规范化后复用同一字段）"""
    name: str
    qualname: str
    source: str
    calls: List[str] = Field(default_factory=list)       # 在 extract 中是原始检测；在 workspace 规范化后写回
    called_by: List[str] = Field(default_factory=list)   # workspace 阶段回填


class WorkspaceFunction(BaseModel):
    file: str
    name: str
    qualname: str
    source: str
    calls: List[str] = Field(default_factory=list)       # 规范化后的 qualname 列表（仅限同文件内可解析者）
    called_by: List[str] = Field(default_factory=list)   # 规范化后的 qualname 列表（仅限同文件内可解析者）


class SliceError(BaseModel):
    file: str
    message: str
    lineno: Optional[int] = None
    colno: Optional[int] = None


class WorkspaceFunctionSlices(BaseModel):
    root: str
    functions: List[WorkspaceFunction] = Field(default_factory=list)
    errors: List[SliceError] = Field(default_factory=list)
    num_files_processed: int = 0
    num_functions: int = 0


# ==========================================================
#                        Helpers
# ==========================================================

def _get_source_segment(src: str, node: ast.AST) -> str:
    """根据 AST 节点精准切片源码，保留缩进与换行"""
    if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
        lines = src.splitlines(keepends=True)
        return "".join(lines[node.lineno - 1 : node.end_lineno])
    return ast.get_source_segment(src, node) or ""


def _dotted_name_from_node(node: ast.AST) -> Optional[str]:
    """
    尽量把被调用对象（func）还原成点分字符串：
    - Name(id) → "foo"；Attribute(value=Name("self"), attr="bar") → "self.bar"；
    - Attribute(value=Name("mod"), attr="func") → "mod.func"；支持嵌套。
    其余复杂情况（如调用表达式结果）返回 None。
    """
    parts: List[str] = []

    def walk(n: ast.AST) -> bool:
        if isinstance(n, ast.Name):
            parts.append(n.id)
            return True
        if isinstance(n, ast.Attribute):
            if walk(n.value):
                parts.append(n.attr)
                return True
            return False
        return False

    if walk(node):
        return ".".join(parts)
    return None


# -------- workspace 枚举工具 --------
DEFAULT_EXCLUDE_DIRS: Set[str] = {
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".venv", "venv", "env", ".idea", ".vscode", "node_modules",
    "dist", "build", "site-packages",
}


def _iter_py_files(
    root: Path,
    include_globs: tuple[str, ...] = ("**/*.py",),
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


# ==========================================================
#                     AST Visitor (functions)
# ==========================================================

class _FunctionCollector(ast.NodeVisitor):
    """仅收集函数定义（包含 async 与嵌套/类内方法），并提取 body 内的调用名（Call）。"""

    def __init__(self, src: str):
        self.src = src
        self.parents: List[str] = []  # 用于构造 qualname
        self.functions: List[FunctionSlice] = []

    def _handle_func(self, node: ast.AST, is_async: bool):
        name: str = node.name  # type: ignore[attr-defined]
        qual = ".".join(self.parents + [name]) if self.parents else name
        source = _get_source_segment(self.src, node)

        # 提取函数体内的调用（Call）
        calls: List[str] = []
        seen = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                callee = _dotted_name_from_node(sub.func)
                if callee and callee not in seen:
                    seen.add(callee)
                    calls.append(callee)

        fn_slice = FunctionSlice(
            name=name,
            qualname=qual,
            source=source,
            calls=calls,
            called_by=[],
        )
        self.functions.append(fn_slice)

        # 递归下探（内部函数等）
        self.parents.append(name)
        self.generic_visit(node)
        self.parents.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_func(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_func(node, is_async=True)

    def visit_ClassDef(self, node: ast.ClassDef):
        # 进入类作用域，但不记录类信息，仅为了给方法构造正确的 qualname
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()


# ==========================================================
#                        Public APIs
# ==========================================================

def extract_function_slices(py_file: str) -> List[FunctionSlice]:
    """
    输入：Python 文件路径
    输出：List[FunctionSlice]
    仅提取函数/方法切片与其中的调用（原始字符串）。
    """
    path = Path(py_file)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(py_file)

    # 遵循 PEP 263 编码声明稳健读取
    with tokenize.open(str(path)) as f:
        src = f.read()

    tree = ast.parse(src, filename=str(path))

    collector = _FunctionCollector(src)
    collector.parents.append("<module>")
    collector.visit(tree)
    collector.parents.pop()

    return collector.functions


# 需要类集合来解析 self./ClassName. —— 复用 class_slicer 的抽取接口
try:  # 允许在没有 class_slicer 的极简环境下导入失败但仍能用 extract
    from class_slicer import extract_class_slices  # type: ignore
except Exception:  # pragma: no cover - 运行时兜底
    extract_class_slices = None  # type: ignore


def slice_functions_in_workspace(
    workspace_root: str | Path,
    *,
    exclude_dirs: Optional[Set[str]] = None,
    max_file_mb: Optional[float] = 2.0,
) -> WorkspaceFunctionSlices:
    """
    对整个 workspace 进行“函数视角”的切片与整合：
    - 逐文件提取函数切片
    - 同文件内规范化 calls（解析到 qualname）
    - 回填 called_by（同文件内）
    - 扁平化为 WorkspaceFunction 列表
    """
    root = Path(workspace_root).resolve()
    errors: List[SliceError] = []

    flat_functions: List[WorkspaceFunction] = []
    num_functions = 0
    processed = 0

    for py_file in _iter_py_files(root, exclude_dirs=exclude_dirs):
        if not _under_size_limit(py_file, max_file_mb):
            errors.append(SliceError(
                file=str(py_file),
                message=f"Skipped: file too large (> {max_file_mb} MB)"
            ))
            continue

        try:
            # 为解析 self./ClassName. 取类集合（仅 qualname）
            class_qns: Set[str] = set()
            if extract_class_slices is not None:
                try:
                    class_qns = {c.qualname for c in extract_class_slices(str(py_file))}
                except Exception:
                    # 如果 class_slices 抽取失败，不影响函数抽取，只是少了同文件解析能力
                    class_qns = set()

            func_slices: List[FunctionSlice] = extract_function_slices(str(py_file))
            processed += 1
            num_functions += len(func_slices)

            # 规范化 calls -> qualname（仅本文件内可解析）
            file_func_qns: Set[str] = {fn.qualname for fn in func_slices}
            for fn in func_slices:
                normalized: List[str] = []
                seen: Set[str] = set()
                for raw in fn.calls:
                    tgt = _resolve_callee_in_file(
                        caller_qn=fn.qualname,
                        raw_callee=raw,
                        file_funcs=file_func_qns,
                        file_classes=class_qns,
                    )
                    if tgt and tgt not in seen:
                        seen.add(tgt)
                        normalized.append(tgt)
                fn.calls = normalized

            # 回填 called_by（用规范化后的 calls）
            for fn in func_slices:
                fn.called_by = []
            index: Dict[str, FunctionSlice] = {fn.qualname: fn for fn in func_slices}
            for fn in func_slices:
                caller_qn = fn.qualname
                for callee_qn in fn.calls:
                    callee_fn = index.get(callee_qn)
                    if callee_fn and caller_qn not in callee_fn.called_by:
                        callee_fn.called_by.append(caller_qn)

            # 扁平化输出
            for fn in func_slices:
                flat_functions.append(
                    WorkspaceFunction(
                        file=str(py_file),
                        name=fn.name,
                        qualname=fn.qualname,
                        source=fn.source,
                        calls=list(fn.calls),
                        called_by=list(fn.called_by),
                    )
                )

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

    return WorkspaceFunctionSlices(
        root=str(root),
        functions=flat_functions,
        errors=errors,
        num_files_processed=processed,
        num_functions=num_functions,
    )