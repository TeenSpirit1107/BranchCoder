from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field


# ---------------------------
# Pydantic v2 Models
# ---------------------------

class WorkspaceFunction(BaseModel):
    file: str                       # 来自于哪个文件（相对路径）
    qualname: str                   # 函数（或方法）限定名
    source: str                     # 函数源代码
    calls: List[str] = Field(default_factory=list)
    called_by: List[str] = Field(default_factory=list)


class WorkspaceResult(BaseModel):
    items: List[WorkspaceFunction]


# ---------------------------
# Helpers
# ---------------------------

SKIP_DIRS = {".git", "__pycache__", ".tox", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache"}


def _iter_python_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 过滤不必要的目录
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                files.append(Path(dirpath) / fn)
    return files


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="ignore")


# ===== AST slicing: 提取函数源码 & qualname =====

@dataclass
class _FuncDef:
    file: Path
    qualname: str
    lineno: int
    end_lineno: int
    source: str


class _QualnameBuilder(ast.NodeVisitor):
    """计算限定名：module相对路径 + （Class.）* + func。"""
    def __init__(self, module_name: str, code: str):
        self.stack: List[str] = []
        self.funcs: List[_FuncDef] = []
        self.module_name = module_name
        self.code = code.splitlines(keepends=True)

    def _push(self, name: str):
        self.stack.append(name)

    def _pop(self):
        if self.stack:
            self.stack.pop()

    def _qual(self, leaf: str) -> str:
        parts = [self.module_name] + self.stack + [leaf]
        return ".".join([p for p in parts if p])

    def visit_ClassDef(self, node: ast.ClassDef):
        self._push(node.name)
        self.generic_visit(node)
        self._pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        qn = self._qual(node.name)
        src = "".join(self.code[node.lineno - 1: node.end_lineno])
        self.funcs.append(
            _FuncDef(
                file=Path(self.module_name.replace(".", os.sep) + ".py"),  # 占位；外层会替换为真实相对路径
                qualname=qn,
                lineno=node.lineno,
                end_lineno=node.end_lineno,
                source=src
            )
        )
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)  # 处理方式相同


def _module_name_from_path(root: Path, file: Path) -> str:
    rel = file.relative_to(root).with_suffix("")  # 去掉 .py
    # 将路径分隔符变成包名点
    return ".".join(rel.parts)


def _slice_functions(files: List[Path], root: Path) -> Dict[str, _FuncDef]:
    result: Dict[str, _FuncDef] = {}
    for f in files:
        code = _read_text(f)
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # 跳过无法解析的文件
            continue

        mod = _module_name_from_path(root, f)
        qb = _QualnameBuilder(module_name=mod, code=code)
        qb.visit(tree)

        # 覆盖 _FuncDef.file 为真实相对路径
        for fd in qb.funcs:
            fd.file = f.relative_to(root)
            result[fd.qualname] = fd
    return result


# ====== 调用图（优先用现成工具） ======

# ====== AST fallback calls（保底策略） ======

class _CallCollector(ast.NodeVisitor):
    def __init__(self):
        self.calls: Set[str] = set()

    def visit_Call(self, node: ast.Call):
        # 尝试收集简单的 Name/Attribute 调用名
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # 收集 attr 名称（不含对象全名，作为保底）
            name = node.func.attr
        if name:
            self.calls.add(name)
        self.generic_visit(node)


def _ast_fallback_calls(files: List[Path], root: Path, func_index: Dict[str, _FuncDef]) -> Dict[str, Set[str]]:
    """
    极简静态分析：对每个函数体里出现的调用，收集函数名（不含 fully-qualified）。
    仅用作在没有 pycg / pyan3 时的保底。
    """
    # 建立一个从 简名 -> full qualname 的候选映射（可能多义）
    short_map: Dict[str, Set[str]] = {}
    for qn in func_index:
        short = qn.split(".")[-1]
        short_map.setdefault(short, set()).add(qn)

    calls: Dict[str, Set[str]] = {}
    for qn, fd in func_index.items():
        code = _read_text(root / fd.file)
        try:
            tree = ast.parse(code)
        except SyntaxError:
            continue

        # 找到对应函数节点的源码片段重新解析以精简范围
        segment = "\n".join(code.splitlines()[fd.lineno - 1: fd.end_lineno])
        try:
            seg_tree = ast.parse(segment)
        except SyntaxError:
            seg_tree = tree

        cc = _CallCollector()
        cc.visit(seg_tree)

        resolved: Set[str] = set()
        for name in cc.calls:
            # 映射到可能的 full qualnames，取并集
            if name in short_map:
                resolved.update(short_map[name])
        if resolved:
            calls[qn] = resolved
    return calls


# ====== 对齐外部工具节点名到我们的 qualname ======

def _normalize_node_name(name: str) -> str:
    """
    将外部工具的节点名尽可能规整到 module.Class.func 的形式。
    对 pycg/pyan3 节点名做宽松处理，以最大概率匹配到 _FuncDef.qualname。
    """
    # 常见形式举例：
    #   pyan: package.module:Class.func 或 package.module:func
    #   pycg: package.module.Class.func 或 函数签名携带参数
    name = name.strip().strip('"')
    name = name.replace(":", ".")
    # 去掉可能的参数、返回类型等附加信息（保守）
    name = re.sub(r"\(.*?\)$", "", name)
    # 去掉重复的点
    name = re.sub(r"\.+", ".", name)
    return name


def _align_tool_graph(tool_graph: Dict[str, Set[str]], known_qualnames: Set[str]) -> Dict[str, Set[str]]:
    aligned: Dict[str, Set[str]] = {}
    for raw_src, raw_dsts in tool_graph.items():
        src = _normalize_node_name(raw_src)
        # 找到最接近的 qualname（完全匹配或后缀匹配）
        src_match = _best_match(src, known_qualnames)
        if not src_match:
            continue
        for raw_dst in raw_dsts:
            dst = _normalize_node_name(raw_dst)
            dst_match = _best_match(dst, known_qualnames)
            if dst_match:
                aligned.setdefault(src_match, set()).add(dst_match)
    return aligned


def _best_match(candidate: str, pool: Set[str]) -> Optional[str]:
    if candidate in pool:
        return candidate
    # 后缀匹配（module.Class.func 的后半截）
    for q in pool:
        if q.endswith("." + candidate) or candidate.endswith("." + q):
            return q
    # 最后再尝试极简的末尾函数名匹配（若唯一）
    cand_leaf = candidate.split(".")[-1]
    matches = [q for q in pool if q.split(".")[-1] == cand_leaf]
    if len(matches) == 1:
        return matches[0]
    return None


# ---------------------------
# 主函数
# ---------------------------

def slice_functions_in_workspace(workspace_path: str) -> WorkspaceResult:
    """
    遍历工作区，切出所有函数/方法源码，并生成调用关系（calls / called_by）。
    调用关系优先使用 pycg，其次 pyan3；若都不可用，则回退到 AST 简易分析。
    """
    root = Path(workspace_path).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Invalid workspace path: {workspace_path}")

    files = _iter_python_files(root)
    func_index = _slice_functions(files, root)   # qualname -> _FuncDef

    known_qualnames = set(func_index.keys())

    calls_map = _ast_fallback_calls(files, root, func_index)

    # 反向边：called_by
    called_by_map: Dict[str, Set[str]] = {qn: set() for qn in known_qualnames}
    for caller, callees in calls_map.items():
        for callee in callees:
            called_by_map.setdefault(callee, set()).add(caller)

    items: List[WorkspaceFunction] = []
    for qn, fd in func_index.items():
        items.append(
            WorkspaceFunction(
                file=str(fd.file).replace("\\", "/"),
                qualname=qn,
                source=fd.source,
                calls=sorted(list(calls_map.get(qn, set()))),
                called_by=sorted(list(called_by_map.get(qn, set())))
            )
        )

    return WorkspaceResult(items=items)
