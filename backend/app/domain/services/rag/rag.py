# rag.py
import ast
import tokenize
from pathlib import Path
from typing import List
from pydantic import BaseModel


class FileSlices(BaseModel):
    """表示一个 Python 文件被切分后的源码片段"""
    file: str
    functions: List[str]  # 函数源码（含 async / 内部函数 / 类内方法）
    classes: List[str]    # 类源码（包含整个类体）


def _get_source_segment(src: str, node: ast.AST) -> str:
    """根据 AST 节点获取源码切片"""
    if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
        lines = src.splitlines(keepends=True)
        return "".join(lines[node.lineno - 1 : node.end_lineno])
    return ast.get_source_segment(src, node) or ""


def extract_slices(py_file: str) -> FileSlices:
    """
    输入: Python 文件路径
    输出: FileSlices(BaseModel)，包含函数列表与类列表（源码字符串）
    """
    path = Path(py_file)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(py_file)

    # 读取源码，自动处理编码声明
    with tokenize.open(str(path)) as f:
        src = f.read()

    tree = ast.parse(src, filename=str(path))

    func_slices: List[str] = []
    class_slices: List[str] = []

    class _Collector(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef):
            func_slices.append(_get_source_segment(src, node))
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            func_slices.append(_get_source_segment(src, node))
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef):
            class_slices.append(_get_source_segment(src, node))
            self.generic_visit(node)

    _Collector().visit(tree)

    return FileSlices(file=str(path), functions=func_slices, classes=class_slices)
