from __future__ import annotations

from pathlib import Path
import ast
import os
import tokenize
from typing import Dict, Iterable, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

# ==========================================================
#                         Models
# ==========================================================

class FunctionSlice(BaseModel):
    """单个函数/方法的切片 + 调用信息。
    在 `extract_function_slices` 阶段，``calls`` 为原始检测到的调用字符串；
    在 workspace 规范化阶段，会写回为“可解析的规范化 qualname”（首段为模块名）。
    """
    name: str
    qualname: str
    source: str
    calls: List[str] = Field(default_factory=list)  # 原始/规范化后的同名字段
    called_by: List[str] = Field(default_factory=list)  # workspace 阶段回填


class WorkspaceFunction(BaseModel):
    file: str
    module: str
    name: str
    qualname: str
    source: str
    calls: List[str] = Field(default_factory=list)  # 规范化后的 qualname 列表（可跨文件）
    called_by: List[str] = Field(default_factory=list)  # 规范化后的 qualname 列表（可跨文件）


class SliceError(BaseModel):
    """处理单个文件时产生的错误信息。"""
    file: str
    message: str
    lineno: Optional[int] = None
    colno: Optional[int] = None


class WorkspaceFunctionSlices(BaseModel):
    """工作区级别的函数切片结果与统计信息。"""
    root: str
    functions: List[WorkspaceFunction] = Field(default_factory=list)
    errors: List[SliceError] = Field(default_factory=list)
    num_files_processed: int = 0
    num_functions: int = 0


# ==========================================================
#                        Helpers
# ==========================================================

DEFAULT_EXCLUDE_DIRS: Set[str] = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    "site-packages",
}


def _get_source_segment(src: str, node: ast.AST) -> str:
    """根据 AST 节点精准切片源码，保留缩进与换行。"""
    if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
        lines = src.splitlines(keepends=True)
        return "".join(lines[node.lineno - 1 : node.end_lineno])
    # 兜底：使用 ast.get_source_segment（可能丢缩进/行尾）
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


def _iter_py_files(
    root: Path,
    include_globs: tuple[str, ...] = ("**/*.py",),  # 为兼容保留参数（当前实现按后缀判定）
    exclude_dirs: Optional[Set[str]] = None,
) -> Iterable[Path]:
    """递归枚举 .py 文件（支持排除常见目录）。

    注：为保持行为不变，仍以文件后缀判断是否为 Python 文件；``include_globs`` 参数
    仅为 API 兼容而保留，尚未用于过滤逻辑。
    """
    _ = include_globs  # 明确占位，防止未使用告警
    effective_excludes = exclude_dirs or DEFAULT_EXCLUDE_DIRS

    for dirpath, dirnames, filenames in os.walk(root):
        # 就地过滤以避免进入被排除目录
        dirnames[:] = [d for d in dirnames if d not in effective_excludes and not d.startswith(".#")]
        for name in filenames:
            if name.endswith(".py"):
                yield Path(dirpath) / name


def _under_size_limit(p: Path, max_file_mb: Optional[float]) -> bool:
    """判断文件大小是否在限制内（None 表示不限制）。"""
    if max_file_mb is None:
        return True
    try:
        size = p.stat().st_size
    except Exception:
        # 读取失败时不阻断后续流程，保守放行
        return True
    return size <= max_file_mb * 1024 * 1024


# ---------------- Module & import utilities ----------------

def _module_name_from_path(root: Path, file: Path) -> str:
    """把文件路径转换为模块名（去掉扩展名，路径分隔符->点）。

    - <root>/pkg/mod.py -> pkg.mod
    - <root>/pkg/__init__.py -> pkg
    """
    rel = file.relative_to(root)
    if rel.name == "__init__.py":
        rel = rel.parent
    else:
        rel = rel.with_suffix("")
    parts = list(rel.parts)
    return ".".join([p for p in parts if p]) or "<root>"


class _ImportTable(BaseModel):
    """记录单文件内的 import 映射。

    - modules:  alias -> absolute module ("import pkg.mod as m" → m: pkg.mod)
    - names:    alias -> (absolute module, original name) ("from pkg.mod import foo as bar" → bar: (pkg.mod, foo))
    - levelled: 支持相对导入：会在构建时解析为绝对模块。
    """

    modules: Dict[str, str] = Field(default_factory=dict)
    names: Dict[str, Tuple[str, str]] = Field(default_factory=dict)


def _absolutize_from_module(cur_module: str, level: int, target: Optional[str]) -> str:
    """将相对导入解析为绝对模块名。``cur_module`` 为当前模块，如 "pkg.sub.mod"。
    level=1 表示 "from . import x"，level=2 表示 "from .. import x"。
    target 可能为 None（"from . import x"），或 "a.b"。
    """
    if level == 0:
        return target or ""
    base_parts = cur_module.split(".")
    if len(base_parts) < level:
        # 退化：超出根则置空前缀
        prefix = []
    else:
        prefix = base_parts[: -level]
    if target:
        prefix += target.split(".")
    return ".".join([p for p in prefix if p])


def _build_import_table(cur_module: str, tree: ast.AST) -> _ImportTable:
    tbl = _ImportTable()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name  # e.g. "pkg.mod"
                asname = alias.asname or mod.split(".")[0]  # 无 as 时，绑定顶层包名
                tbl.modules[asname] = mod
        elif isinstance(node, ast.ImportFrom):
            # node.module 可能为 None（from . import x），需结合 level 解析
            abs_mod = _absolutize_from_module(cur_module, getattr(node, "level", 0) or 0, node.module)
            for alias in node.names:
                name = alias.name
                asname = alias.asname or name
                tbl.names[asname] = (abs_mod, name)
    return tbl


# ---------------- Collectors ----------------

class _ClassCollector(ast.NodeVisitor):
    def __init__(self, src: str, module: str):
        self.src = src
        self.module = module
        self.parents: List[str] = [module]
        self.classes: Set[str] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        qual = ".".join(self.parents + [node.name])
        self.classes.add(qual)
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()


class _FunctionCollector(ast.NodeVisitor):
    """仅收集函数定义（包含 async 与嵌套/类内方法），并提取 body 内的调用名（Call）。"""

    def __init__(self, src: str, module: str):
        self.src = src
        self.module = module
        self.parents: List[str] = [module]  # 用于构造 qualname
        self.functions: List[FunctionSlice] = []

    def _handle_func(self, node: ast.AST, is_async: bool) -> None:
        # ``is_async`` 暂不影响行为，保留参数以示区分
        name: str = node.name  # type: ignore[attr-defined]
        qual = ".".join(self.parents + [name])
        source = _get_source_segment(self.src, node)

        # 提取函数体内的调用（Call）
        calls: List[str] = []
        seen: Set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                callee = _dotted_name_from_node(sub.func)
                if callee and callee not in seen:
                    seen.add(callee)
                    calls.append(callee)

        self.functions.append(
            FunctionSlice(
                name=name,
                qualname=qual,
                source=source,
                calls=calls,
                called_by=[],
            )
        )

        # 递归下探（内部函数等）
        self.parents.append(name)
        self.generic_visit(node)
        self.parents.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._handle_func(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._handle_func(node, is_async=True)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()


# ==========================================================
#                        Public APIs
# ==========================================================

def extract_function_slices(py_file: str, *, module: Optional[str] = None, root: Optional[str | Path] = None) -> List[FunctionSlice]:
    """从单个 Python 源文件提取函数切片与其中的调用（原始字符串）。

    如果传入 ``root``，将据此推导 ``module``；否则 ``module`` 必须显式提供。
    生成的 ``qualname`` 将以模块名作为首段（如 "pkg.mod.func").
    """
    path = Path(py_file)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(py_file)

    # 遵循 PEP 263 编码声明稳健读取
    with tokenize.open(str(path)) as f:
        src = f.read()

    if module is None:
        if root is None:
            raise ValueError("When 'module' is None, 'root' must be provided to compute it.")
        module = _module_name_from_path(Path(root).resolve(), path.resolve())

    tree = ast.parse(src, filename=str(path))

    collector = _FunctionCollector(src, module)
    collector.visit(tree)

    return collector.functions


# 需要类集合来解析 self./ClassName. —— 复用 class_slicer 的抽取接口（可选）
try:  # 允许在没有 class_slicer 的极简环境下导入失败但仍能用 extract
    from class_slicer import extract_class_slices  # type: ignore
except Exception:  # pragma: no cover - 运行时兜底
    extract_class_slices = None  # type: ignore


# ---------------- Cross-file resolution ----------------

def _resolve_callee(
    *,
    caller_qn: str,
    caller_module: str,
    raw_callee: str,
    file_funcs: Set[str],
    file_classes: Set[str],
    imports: _ImportTable,
    global_function_qns: Set[str],
    global_class_qns: Set[str],
) -> Optional[str]:
    """把原始调用字符串解析为全局 qualname。

    解析顺序：
    1) self./cls. → 最近类作用域的方法
    2) ClassName.foo / Outer.Inner.bar → 先在当前模块内解析；若失败，尝试导入的类名
    3) 裸标识符 foo → 当前模块的函数/外层嵌套；若失败，尝试 from-import 的符号
    4) 带点名 a.b.c → 如果首段是 import 的别名，则替换为真实模块后匹配全局函数；否则当作绝对 qualname 尝试
    """

    def _scopes_from_qualname(qualname: str) -> List[str]:
        return qualname.split(".")

    scopes = _scopes_from_qualname(caller_qn)
    scope_chain = scopes[:-1]  # 去掉自身函数名

    # 1) self./cls.
    if raw_callee.startswith("self.") or raw_callee.startswith("cls."):
        method = raw_callee.split(".", 1)[1]
        # 找最近的类作用域
        for i in range(len(scope_chain) - 1, -1, -1):
            cand = ".".join(scope_chain[: i + 1])
            if cand in file_classes or cand in global_class_qns:
                target_qn = f"{cand}.{method}"
                return target_qn if target_qn in global_function_qns else None
        return None

    # 2) ClassName.foo / Outer.Inner.bar
    if "." in raw_callee:
        head, tail = raw_callee.split(".", 1)
        # 2.1: 导入的模块别名
        if head in imports.modules:
            mod = imports.modules[head]
            tgt = f"{mod}.{tail}"
            return tgt if tgt in global_function_qns else None
        # 2.2: from-import 的类名 / 函数名
        if head in imports.names:
            mod, name = imports.names[head]
            # 如果调用 head.method... 则认为 head 可能是类名
            tgt = f"{mod}.{name}.{tail}"
            if tgt in global_function_qns:
                return tgt
            # 或者 name 本身就是子模块： fall back 为模块+tail
            alt = f"{mod}.{tail}"
            if alt in global_function_qns:
                return alt
        # 2.3: 当前模块内的类/嵌套
        # 构造相对解析：caller_module + '.' + raw_callee 的前缀部分为类，再拼尾部
        # 例如 pkg.m.Class.meth → 直接匹配
        local_head = f"{caller_module}.{head}"
        if local_head in file_classes or local_head in global_class_qns:
            tgt = f"{local_head}.{tail}"
            return tgt if tgt in global_function_qns else None
        # 2.4: 将 raw 视为绝对 qualname
        abs_cand = raw_callee
        return abs_cand if abs_cand in global_function_qns else None

    # 3) 裸标识符 foo
    # 3.1 顶层或外层嵌套（当前模块）
    top_level = f"{caller_module}.{raw_callee}"
    if top_level in global_function_qns:
        return top_level
    for i in range(len(scope_chain), 0, -1):
        qual = ".".join(scope_chain[:i] + [raw_callee])
        if qual in global_function_qns:
            return qual
    # 3.2 from-import 的符号
    if raw_callee in imports.names:
        mod, name = imports.names[raw_callee]
        tgt = f"{mod}.{name}"
        if tgt in global_function_qns:
            return tgt
    return None


# ==========================================================
#                    Workspace slicer (cross-file)
# ==========================================================

def slice_functions_in_workspace(
    workspace_root: str | Path,
    *,
    exclude_dirs: Optional[Set[str]] = None,
    max_file_mb: Optional[float] = 2.0,
) -> WorkspaceFunctionSlices:
    """对整个 workspace 进行“函数视角”的切片与整合（支持跨文件解析）。
    步骤：
    - 逐文件提取函数/类切片、import 表
    - 规范化 calls（解析为全局 qualname，跨文件）
    - 回填 called_by（跨文件）
    - 扁平化为 WorkspaceFunction 列表
    """
    root = Path(workspace_root).resolve()

    errors: List[SliceError] = []
    processed = 0

    # -------- 第一遍扫描：收集每个文件的 module、函数/类、imports --------
    per_file_functions: Dict[str, List[FunctionSlice]] = {}
    per_file_classes: Dict[str, Set[str]] = {}
    per_file_imports: Dict[str, _ImportTable] = {}
    module_by_file: Dict[str, str] = {}

    # 全局索引
    global_function_qns: Set[str] = set()
    global_class_qns: Set[str] = set()

    for py_file in _iter_py_files(root, exclude_dirs=exclude_dirs):
        if not _under_size_limit(py_file, max_file_mb):
            errors.append(
                SliceError(
                    file=str(py_file),
                    message=f"Skipped: file too large (> {max_file_mb} MB)",
                )
            )
            continue

        try:
            with tokenize.open(str(py_file)) as f:
                src = f.read()
            module = _module_name_from_path(root, py_file)
            tree = ast.parse(src, filename=str(py_file))
            module_by_file[str(py_file)] = module

            # classes
            class_qns: Set[str] = set()
            if extract_class_slices is not None:
                try:
                    class_qns = {c.qualname if c.qualname.startswith(module) else f"{module}.{c.qualname}" for c in extract_class_slices(str(py_file))}
                except Exception:
                    class_qns = set()
            # 自己收集（兜底/补充）
            cc = _ClassCollector(src, module)
            cc.visit(tree)
            class_qns |= cc.classes
            per_file_classes[str(py_file)] = class_qns
            global_class_qns |= class_qns

            # functions
            fc = _FunctionCollector(src, module)
            fc.visit(tree)
            func_slices = fc.functions
            per_file_functions[str(py_file)] = func_slices
            for fn in func_slices:
                global_function_qns.add(fn.qualname)

            # imports
            per_file_imports[str(py_file)] = _build_import_table(module, tree)

            processed += 1

        except SyntaxError as e:
            errors.append(
                SliceError(
                    file=str(py_file),
                    message=f"SyntaxError: {e.msg}",
                    lineno=getattr(e, "lineno", None),
                    colno=getattr(e, "offset", None),
                )
            )
        except UnicodeDecodeError as e:
            errors.append(SliceError(file=str(py_file), message=f"UnicodeDecodeError: {e.reason}"))
        except Exception as e:  # noqa: BLE001
            errors.append(
                SliceError(
                    file=str(py_file),
                    message=f"UnhandledError: {e.__class__.__name__}: {e}",
                )
            )

    # -------- 第二遍：解析 calls → 全局 qualname；回填 called_by --------
    # 用于回填的全局索引（qualname -> FunctionSlice）
    index: Dict[str, FunctionSlice] = {}
    for file, fns in per_file_functions.items():
        for fn in fns:
            index[fn.qualname] = fn

    # 先清空 called_by
    for fn in index.values():
        fn.called_by = []

    for file, fns in per_file_functions.items():
        module = module_by_file[file]
        file_funcs = {fn.qualname for fn in fns}
        file_classes = per_file_classes.get(file, set())
        imports = per_file_imports[file]

        for fn in fns:
            normalized: List[str] = []
            seen: Set[str] = set()
            for raw in fn.calls:
                tgt = _resolve_callee(
                    caller_qn=fn.qualname,
                    caller_module=module,
                    raw_callee=raw,
                    file_funcs=file_funcs,
                    file_classes=file_classes,
                    imports=imports,
                    global_function_qns=global_function_qns,
                    global_class_qns=global_class_qns,
                )
                if tgt and tgt not in seen:
                    seen.add(tgt)
                    normalized.append(tgt)
            fn.calls = normalized

    # 回填 called_by
    for fn in index.values():
        fn.called_by = []
    for fn in index.values():
        caller_qn = fn.qualname
        for callee_qn in fn.calls:
            callee_fn = index.get(callee_qn)
            if callee_fn and caller_qn not in callee_fn.called_by:
                callee_fn.called_by.append(caller_qn)

    # -------- 扁平化输出 --------
    flat_functions: List[WorkspaceFunction] = []
    num_functions = 0
    for file, fns in per_file_functions.items():
        module = module_by_file[file]
        for fn in fns:
            flat_functions.append(
                WorkspaceFunction(
                    file=file,
                    module=module,
                    name=fn.name,
                    qualname=fn.qualname,
                    source=fn.source,
                    calls=list(fn.calls),
                    called_by=list(fn.called_by),
                )
            )
            num_functions += 1

    return WorkspaceFunctionSlices(
        root=str(root),
        functions=flat_functions,
        errors=errors,
        num_files_processed=processed,
        num_functions=num_functions,
    )
