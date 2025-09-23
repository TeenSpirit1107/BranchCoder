# file_slicer.py
from __future__ import annotations

import ast
import tokenize
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


# =========================
#         Models
# =========================

class FunctionSlice(BaseModel):
    """单个函数的切片 + 调用信息"""
    name: str
    qualname: str
    source: str
    calls: List[str] = Field(default_factory=list)       # 原始检测到的调用字符串（稍后在 workspace 里规范化）
    called_by: List[str] = Field(default_factory=list)   # 反向调用（由 workspace_slicer 补全）


class ClassSlice(BaseModel):
    """单个类的切片 + 类内方法列表"""
    name: str
    qualname: str
    source: str
    methods: List[str] = Field(default_factory=list)  # 类内直接定义的方法（qualname），不含继承/外部函数


class FileSlices(BaseModel):
    """整文件结果：函数与类的切片列表"""
    file: str
    functions: List[FunctionSlice] = Field(default_factory=list)
    classes: List[ClassSlice] = Field(default_factory=list)


# =========================
#       Helpers
# =========================

def _get_source_segment(src: str, node: ast.AST) -> str:
    """根据 AST 节点精准切片源码，保留缩进与换行"""
    if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
        lines = src.splitlines(keepends=True)
        return "".join(lines[node.lineno - 1: node.end_lineno])
    return ast.get_source_segment(src, node) or ""


def _dotted_name_from_node(node: ast.AST) -> Optional[str]:
    """
    尽量把被调用对象（func）还原成点分字符串：
    - Name(id) → "foo"
    - Attribute(value=Name("self"), attr="bar") → "self.bar"
    - Attribute(value=Name("mod"), attr="func") → "mod.func"
    - 嵌套 Attribute 也会拉平：pkg.sub.module.func
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


# =========================
#       AST Visitor
# =========================

class _Collector(ast.NodeVisitor):
    """
    DFS 顺序遍历，收集：
    - 函数切片（包含 async 与嵌套/类内方法），并提取其 body 内的调用名（Call）
    - 类切片（包含整个类体），并统计其直接定义的方法名
    """
    def __init__(self, src: str):
        self.src = src
        self.parents: List[str] = []  # 用于构造 qualname
        self.functions: List[FunctionSlice] = []
        self.classes: List[ClassSlice] = []

    # -------- 类 --------
    def visit_ClassDef(self, node: ast.ClassDef):
        qual = ".".join(self.parents + [node.name]) if self.parents else node.name

        # 先收集类内方法名（仅直系成员）
        method_qualnames: List[str] = []
        for n in node.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_qualnames.append(f"{qual}.{n.name}")

        cls_slice = ClassSlice(
            name=node.name,
            qualname=qual,
            source=_get_source_segment(self.src, node),
            methods=method_qualnames,
        )
        self.classes.append(cls_slice)

        # 进入类作用域，继续收集内部定义（包含内部类/方法的函数切片等）
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()

    # -------- 函数（含 async）--------
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


# =========================
#        Public API
# =========================

def extract_slices(py_file: str) -> FileSlices:
    """
    输入：Python 文件路径
    输出：FileSlices(BaseModel)
      - functions: 每个元素是 FunctionSlice(name, qualname, source, calls, called_by=[])
      - classes:   每个元素是 ClassSlice(name, qualname, source, methods)
    """
    path = Path(py_file)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(py_file)

    # 遵循 PEP 263 编码声明稳健读取
    with tokenize.open(str(path)) as f:
        src = f.read()

    tree = ast.parse(src, filename=str(path))

    collector = _Collector(src)
    collector.parents.append("<module>")
    collector.visit(tree)
    collector.parents.pop()

    return FileSlices(
        file=str(path),
        functions=collector.functions,
        classes=collector.classes,
    )
