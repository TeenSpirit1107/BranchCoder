import os
import asyncio
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from pydantic import BaseModel
import json
from dotenv import load_dotenv

from llm.chat_llm import AsyncChatClientWrapper
from rag.function_slicer import FunctionSlice, WorkspaceFunctionSlices, FunctionSlicer
from rag.class_slicer import ClassSlice, ClassSlicer
from utils.logger import Logger

# Load environment variables from .env file
load_dotenv()

# Initialize logger instance
logger = Logger('description_generator', log_to_file=False)

# Concurrency limit for description generation (from .env file, default: 2)
DEFAULT_DESCRIPTION_CONCURRENCY = int(os.getenv("RAG_DESCRIPTION_CONCURRENCY"))

# -------------------------------------
# New models for descriptions & outputs
# -------------------------------------
class DescribedFunction(FunctionSlice):
    """为函数补充自然语言描述。"""
    description: str = ""


class DescribedClass(ClassSlice):
    """为类补充自然语言描述。"""
    description: str = ""


class FileDescription(BaseModel):
    """每个文件级别的描述；可单独存储为 sidecar JSON。"""
    file: str
    description: str


class DescribedWorkspaceFunctions(BaseModel):
    """兼容旧类型定义（不再在最终输出中使用）。"""
    items: List[DescribedFunction]


class DescribedWorkspaceClasses(BaseModel):
    """兼容旧类型定义（不再在最终输出中使用）。"""
    items: List[DescribedClass]


class DescribeOutput(BaseModel):
    """最终返回结果：
    - files: 每个文件的描述列表
    - functions: 直接作为列表
    - classes: 直接作为列表
    """
    files: List[FileDescription]
    functions: List[DescribedFunction]
    classes: List[DescribedClass]

class DescriptionGenerator:
    # -----------------------------
    # Core pipeline
    # -----------------------------
    PROMPT_TEMPLATE = """
    You are a senior software engineer. Please read the following source file and generate two levels of English descriptions:
    1) File-level summary (3–6 sentences): summarize the responsibilities of the file, key types/functions, external dependencies, and collaboration relationships.
    2) Function-level summary: write 1–2 sentences for each listed function, focusing on inputs/outputs, side effects, and call relationships.
    3) Class-level summary: write 1–2 sentences for each listed class, focusing on core responsibilities, key methods, or interacting objects.
    
    Be sure to use the fixed output format:
    [FILE]
    <File-level summary>
    [FUNCTIONS]
    <qualname>: <function description>
    <qualname>: <function description>
    ...
    [CLASSES]
    <qualname>: <class description>
    <qualname>: <class description>
    ...
    
    File content:
    --- BEGIN FILE ---
    File: {file}
    {file_text}
    --- END FILE ---
    
    Function list (qualname):
    Functions:
    {functions_bulleted}
    Class list (qualname):
    Classes:
    {classes_bulleted}
    """.strip()

    def __init__(
            self,
            llm: AsyncChatClientWrapper,
    ):
        self.llm = llm
        # Semaphore to limit concurrent LLM calls (from .env file, default: 2)
        self._llm_semaphore = asyncio.Semaphore(DEFAULT_DESCRIPTION_CONCURRENCY)
        # Lock to protect shared caches during concurrent processing
        self._cache_lock = asyncio.Lock()

    def _build_prompt(
        self,
        file: str,
        file_text: str,
        functions: List[FunctionSlice],
        classes: List[ClassSlice],
    ) -> str:
        func_bullets = "\n".join(f"- {fn.qualname}" for fn in functions) or "- <none>"
        class_bullets = "\n".join(f"- {cl.qualname}" for cl in classes) or "- <none>"
        return self.PROMPT_TEMPLATE.format(
            file=file,
            file_text=file_text,
            functions_bulleted=func_bullets,
            classes_bulleted=class_bullets,
        )


    def _group_functions_by_file(self, _result: WorkspaceFunctionSlices) -> Dict[str, List[FunctionSlice]]:
        grouped: Dict[str, List[FunctionSlice]] = {}
        for fn in _result.items:
            grouped.setdefault(fn.file, []).append(fn)
        return grouped


    def parse_llm_response(self, raw: str) -> Tuple[str, Dict[str, str], Dict[str, str]]:
        """将 LLM 输出解析为 (file_description, {qualname: fn_description}, {qualname: class_description}).
        约定格式见 PROMPT_TEMPLATE。鲁棒处理：忽略无法识别的行。"""
        file_desc = ""
        fn_descs: Dict[str, str] = {}
        cls_descs: Dict[str, str] = {}

        section = None

        def _normalize_key(name: str) -> str:
            """Normalize qualname parsed from LLM output.

            - Trim whitespace
            - Remove leading bullet '-' if present
            - Strip surrounding square brackets [ ... ] if present
            - Collapse remaining extra spaces
            """
            _s = name.strip()
            # remove leading dash bullets
            if _s.startswith("-"):
                _s = _s.lstrip("-").strip()
            # strip surrounding brackets like [<module>.Class]
            if _s.startswith("[") and _s.endswith("]"):
                _s = _s[1:-1].strip()
            # normalize internal whitespace
            return " ".join(_s.split())
        for line in raw.splitlines():
            s = line.strip()
            if s == "[FILE]":
                section = "FILE"
                continue
            if s == "[FUNCTIONS]":
                section = "FUNCTIONS"
                continue
            if s == "[CLASSES]":
                section = "CLASSES"
                continue
            if not s:
                continue
            if section == "FILE":
                file_desc = (file_desc + " " + s).strip()
            elif section == "FUNCTIONS":
                if ":" in s:
                    q, d = s.split(":", 1)
                    q = _normalize_key(q)
                    d = d.strip()
                    if q:
                        fn_descs[q] = d
            elif section == "CLASSES":
                if ":" in s:
                    q, d = s.split(":", 1)
                    q = _normalize_key(q)
                    d = d.strip()
                    if q:
                        cls_descs[q] = d
        return file_desc, fn_descs, cls_descs

    async def _process_single_file(
        self,
        rel_file: str,
        fns: List[FunctionSlice],
        workspace_dir: Path,
        classes_by_file: Dict[str, List[ClassSlice]],
        global_fn_desc_by_qualname: Dict[str, str],
        global_fn_desc_by_tail2: Dict[str, str],
        global_fn_desc_by_tail1: Dict[str, str],
        global_cls_desc_by_qualname: Dict[str, str],
        global_cls_desc_by_name: Dict[str, str],
        total_files: int,
        file_index: int,
    ) -> Tuple[FileDescription, List[DescribedFunction], List[DescribedClass]]:
        """Process a single file concurrently with semaphore limiting."""
        def _normalize_key_global(name: str) -> str:
            s = name.strip()
            if s.startswith("-"):
                s = s.lstrip("-").strip()
            if s.startswith("[") and s.endswith("]"):
                s = s[1:-1].strip()
            return " ".join(s.split())

        abs_file = (workspace_dir / rel_file).resolve()
        # Get class slices for this file (support both absolute and relative paths)
        file_classes: List[ClassSlice] = []
        file_classes.extend(classes_by_file.get(str(abs_file), []))
        file_classes.extend(classes_by_file.get(rel_file, []))

        try:
            file_text = abs_file.read_text(encoding="utf-8")
        except Exception:
            file_text = f"<无法读取文件: {abs_file}>"
            raise Exception(file_text)

        prompt = self._build_prompt(rel_file, file_text, fns, file_classes)
        logger.info(f"Processing file {file_index}/{total_files}: {rel_file}")
        logger.info(prompt)

        # Use semaphore to limit concurrent LLM calls
        async with self._llm_semaphore:
            resp = await self.llm.ask(
                messages=[{"role": "user", "content": prompt}],
            )
        logger.info(resp)

        try:
            content = resp.get("answer", "") if isinstance(resp, dict) else ""
        except Exception as e:
            logger.error(e)
            content = ""
        
        file_desc, fn_descs, cls_descs = self.parse_llm_response(content)

        # Update global caches with lock protection
        async with self._cache_lock:
            # Update global class description cache
            for k, v in cls_descs.items():
                key_norm = _normalize_key_global(k)
                global_cls_desc_by_qualname[key_norm] = v
                simple = key_norm.split(".")[-1]
                if simple:
                    global_cls_desc_by_name[simple] = v

            # Update global function description cache
            for k, v in fn_descs.items():
                key_norm = _normalize_key_global(k)
                global_fn_desc_by_qualname[key_norm] = v
                parts = key_norm.split(".")
                if len(parts) >= 2:
                    tail2 = ".".join(parts[-2:])
                    global_fn_desc_by_tail2[tail2] = v
                if parts:
                    tail1 = parts[-1]
                    global_fn_desc_by_tail1[tail1] = v

        # Create file description
        fd = FileDescription(file=rel_file, description=file_desc)

        # Merge function descriptions (with global and fallback matching)
        described_items: List[DescribedFunction] = []
        for fn in fns:
            desc = fn_descs.get(fn.qualname, "")
            if not desc:
                q_norm = _normalize_key_global(fn.qualname)
                parts = q_norm.split(".")
                tail2 = ".".join(parts[-2:]) if len(parts) >= 2 else ""
                tail1 = parts[-1] if parts else ""
                # Access global cache with lock
                async with self._cache_lock:
                    desc = (
                        fn_descs.get(tail2, "")
                        or fn_descs.get(tail1, "")
                        or global_fn_desc_by_tail2.get(tail2, "")
                        or global_fn_desc_by_tail1.get(tail1, "")
                    )

            described_items.append(
                DescribedFunction(
                    **fn.model_dump(),
                    description=desc,
                )
            )

        # Merge class descriptions
        described_classes: List[DescribedClass] = []
        for cl in file_classes:
            desc = cls_descs.get(cl.qualname, "")
            if not desc:
                q_norm = _normalize_key_global(cl.qualname)
                # Access global cache with lock
                async with self._cache_lock:
                    desc = (
                        cls_descs.get(q_norm, "")
                        or global_cls_desc_by_qualname.get(cl.qualname, "")
                        or global_cls_desc_by_qualname.get(q_norm, "")
                    )
            if not desc:
                simple = cl.name or cl.qualname.split(".")[-1]
                async with self._cache_lock:
                    desc = (
                        cls_descs.get(simple, "")
                        or global_cls_desc_by_name.get(simple, "")
                    )

            described_classes.append(
                DescribedClass(
                    **cl.model_dump(),
                    description=desc,
                )
            )

        return fd, described_items, described_classes

    async def describe_workspace(self, workspace_dir, output_path: Optional[str] = None) -> DescribeOutput:
        """核心入口（并发版本）：
        1) 按文件分组函数
        2) 并发读取文件源码，调用 LLM 生成文件/函数描述（使用信号量限制并发数）
        3) 把函数描述并回到切片数据
        4) 将每个文件级描述存盘（可选）
        5) 返回归并后的结果
        
        Args:
            workspace_dir: Path to the workspace directory
            output_path: Optional path to save description_output.json. If None, uses default path.
        """
        # Ensure workspace_dir is a Path to support path joining with '/'
        workspace_dir = Path(workspace_dir)
        function_slice = FunctionSlicer().slice_workspace(workspace_dir)
        classes_in_workspace = ClassSlicer().slice_workspace(workspace_dir)

        grouped = self._group_functions_by_file(function_slice)

        # 全局函数描述缓存，便于跨文件回填/宽松匹配
        global_fn_desc_by_qualname: Dict[str, str] = {}
        global_fn_desc_by_tail2: Dict[str, str] = {}
        global_fn_desc_by_tail1: Dict[str, str] = {}
        # 全局类描述缓存，便于跨文件回填
        global_cls_desc_by_qualname: Dict[str, str] = {}
        global_cls_desc_by_name: Dict[str, str] = {}

        # 收集类切片并按文件分组
        classes_by_file: Dict[str, List[ClassSlice]] = {}
        for wc in classes_in_workspace.classes:
            classes_by_file.setdefault(wc.file, []).append(wc)

        # Create concurrent tasks for processing all files
        total = len(grouped.items())
        tasks = []
        for file_index, (rel_file, fns) in enumerate(grouped.items(), 1):
            task = self._process_single_file(
                rel_file=rel_file,
                fns=fns,
                workspace_dir=workspace_dir,
                classes_by_file=classes_by_file,
                global_fn_desc_by_qualname=global_fn_desc_by_qualname,
                global_fn_desc_by_tail2=global_fn_desc_by_tail2,
                global_fn_desc_by_tail1=global_fn_desc_by_tail1,
                global_cls_desc_by_qualname=global_cls_desc_by_qualname,
                global_cls_desc_by_name=global_cls_desc_by_name,
                total_files=total,
                file_index=file_index,
            )
            tasks.append(task)

        # Execute all file processing tasks concurrently
        results = await asyncio.gather(*tasks)

        # Aggregate results from all files
        file_descs: List[FileDescription] = []
        described_items: List[DescribedFunction] = []
        described_classes_acc: List[DescribedClass] = []

        for fd, items, classes in results:
            file_descs.append(fd)
            described_items.extend(items)
            described_classes_acc.extend(classes)

        logger.info('Description generation finished')
        # 直接构造最终结果，functions 与 classes 为列表
        final_result = DescribeOutput(
            files=file_descs,
            functions=described_items,
            classes=described_classes_acc,
        )

        # Determine output file path
        if output_path:
            aggregate_file = Path(output_path)
        else:
            # Default path for backward compatibility
            aggregate_file = Path(os.path.join("app","domain","services","rag","description_output.json"))

        # 确保父目录存在
        aggregate_file.parent.mkdir(parents=True, exist_ok=True)

        # 写入 JSON 文件
        aggregate_file.write_text(
            json.dumps(final_result.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Saved description_output.json to: {aggregate_file}")

        return final_result

    async def run(self, workspace_dir, output_path: Optional[str] = None):
        return await self.describe_workspace(
            workspace_dir=workspace_dir,
            output_path=output_path,
        )
