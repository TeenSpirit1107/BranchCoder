from __future__ import annotations

import ast
import os
import tokenize
from pathlib import Path
from typing import Iterable, List, Optional, Set

from pydantic import BaseModel, Field

# ==========================================================
#                         Models
# ==========================================================

class ClassSlice(BaseModel):
    """单个类的切片 + 类内方法列表"""
    name: str
    qualname: str
    source: str
    methods: List[str] = Field(default_factory=list)  # 仅直系方法（qualname）


class WorkspaceClass(BaseModel):
    file: str
    name: str
    qualname: str
    source: str
    methods: List[str] = Field(default_factory=list)


class WorkspaceClassSlices(BaseModel):
    classes: List[WorkspaceClass] = Field(default_factory=list)


# ==========================================================
#                        Helpers
# ==========================================================

def _get_source_segment(src: str, node: ast.AST) -> str:
    if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
        lines = src.splitlines(keepends=True)
        return "".join(lines[node.lineno - 1 : node.end_lineno])
    return ast.get_source_segment(src, node) or ""


DEFAULT_EXCLUDE_DIRS: Set[str] = {
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".venv", "venv", "env", ".idea", ".vscode", "node_modules",
    "dist", "build", "site-packages",
}


def _iter_py_files(
    root: Path,
    exclude_dirs: Optional[Set[str]] = None,
):
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


# ==========================================================
#                   AST Visitor (classes)
# ==========================================================

class _ClassCollector(ast.NodeVisitor):
    """仅收集类定义（包含整个类体），并统计其直接定义的方法名；不负责函数切片或调用关系提取。"""

    def __init__(self, src: str):
        self.src = src
        self.parents: List[str] = []  # 用于构造 qualname
        self.classes: List[ClassSlice] = []

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

        # 进入类作用域，继续收集内部类
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()

    # 函数定义不做记录，但要维持 parents 以便嵌套类 qualname 正确
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()


# ==========================================================
#                        Public APIs
# ==========================================================

def extract_class_slices(py_file: str) -> List[ClassSlice]:
    """提取单文件类切片以及类内直系方法列表。"""
    path = Path(py_file)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(py_file)

    with tokenize.open(str(path)) as f:
        src = f.read()

    tree = ast.parse(src, filename=str(path))

    collector = _ClassCollector(src)
    collector.parents.append("<module>")
    collector.visit(tree)
    collector.parents.pop()

    return collector.classes


def slice_classes_in_workspace(
    workspace_root: str | Path,
    *,
    exclude_dirs: Optional[Set[str]] = None,
    max_file_mb: Optional[float] = 2.0,
) -> WorkspaceClassSlices:
    """对整个 workspace 进行“类视角”的切片与整合，并扁平化输出。"""
    root = Path(workspace_root).resolve()

    flat_classes: List[WorkspaceClass] = []
    num_classes = 0
    processed = 0

    for py_file in _iter_py_files(root, exclude_dirs=exclude_dirs):
        if not _under_size_limit(py_file, max_file_mb):
            continue

        try:
            class_slices: List[ClassSlice] = extract_class_slices(str(py_file))
            processed += 1
            num_classes += len(class_slices)

            for cls in class_slices:
                flat_classes.append(
                    WorkspaceClass(
                        file=str(py_file),
                        name=cls.name,
                        qualname=cls.qualname,
                        source=cls.source,
                        methods=list(cls.methods),
                    )
                )

        except SyntaxError as e:
           continue
        except UnicodeDecodeError as e:
            continue
        except Exception as e:
            continue

    return WorkspaceClassSlices(
        classes=flat_classes,
    )