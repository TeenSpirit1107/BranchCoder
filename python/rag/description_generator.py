import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple
from pydantic import BaseModel
import json

from app.domain.external import LLM
from app.domain.services.rag.function_slicer import FunctionSlice, WorkspaceFunctionSlices, FunctionSlicer
from app.domain.services.rag.class_slicer import ClassSlice, ClassSlicer

logger = logging.getLogger(__name__)

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
            llm: LLM,
    ):
        self.llm = llm

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


    async def describe_workspace(self, workspace_dir) -> DescribeOutput:
        """核心入口：
        1) 按文件分组函数
        2) 读取文件源码，调用 LLM 生成文件/函数描述
        3) 把函数描述并回到切片数据
        4) 将每个文件级描述存盘（可选）
        5) 返回归并后的结果
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

        def _normalize_key_global(name: str) -> str:
            s = name.strip()
            if s.startswith("-"):
                s = s.lstrip("-").strip()
            if s.startswith("[") and s.endswith("]"):
                s = s[1:-1].strip()
            return " ".join(s.split())

        # 收集类切片并按文件分组
        classes_by_file: Dict[str, List[ClassSlice]] = {}
        for wc in classes_in_workspace.classes:
            classes_by_file.setdefault(wc.file, []).append(wc)

        # 为了在 DescribeOutput 暴露类信息，我们暂存在本地列表，函数末尾一并返回
        described_items: List[DescribedFunction] = []
        described_classes_acc: List[DescribedClass] = []
        file_descs: List[FileDescription] = []
        total = len(grouped.items())
        current = 0
        for rel_file, fns in grouped.items():
            current += 1
            abs_file = (workspace_dir / rel_file).resolve()
            # 获取该文件对应的类切片（兼容绝对/相对路径）
            file_classes: List[ClassSlice] = []
            # 优先用绝对路径匹配
            file_classes.extend(classes_by_file.get(str(abs_file), []))
            # 回退用相对路径匹配
            file_classes.extend(classes_by_file.get(rel_file, []))
            try:
                file_text = abs_file.read_text(encoding="utf-8")
            except Exception:
                # 如果读取失败，仍然走流程但标记占位文本
                file_text = f"<无法读取文件: {abs_file}>"
                raise Exception(file_text)

            prompt = self._build_prompt(rel_file, file_text, fns, file_classes)
            logger.info(prompt)
            logger.info(current/total)
            resp = await self.llm.custom_ask(
                model='gpt-5-nano',
                # temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            logger.info(resp)
            try:
                content = resp.content  # type: ignore[attr-defined]
            except Exception as e:
                logger.error(e)
                content = ""
            file_desc, fn_descs, cls_descs = self.parse_llm_response(content)

            # 更新全局类描述缓存（既存 qualname，也存类名便于回退）
            for k, v in cls_descs.items():
                key_norm = _normalize_key_global(k)
                global_cls_desc_by_qualname[key_norm] = v
                # 提取末尾类名用于宽松匹配
                simple = key_norm.split(".")[-1]
                if simple:
                    global_cls_desc_by_name[simple] = v

            # 更新全局函数描述缓存（存规范化的 qualname 以及尾部片段）
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

            # 保存文件级描述
            fd = FileDescription(file=rel_file, description=file_desc)
            file_descs.append(fd)

            # 不再为每个文件写 sidecar，仅在函数末尾写聚合文件
            # 合并函数描述（加入全局与宽松匹配）
            for fn in fns:
                desc = fn_descs.get(fn.qualname, "")
                if not desc:
                    q_norm = _normalize_key_global(fn.qualname)
                    parts = q_norm.split(".")
                    tail2 = ".".join(parts[-2:]) if len(parts) >= 2 else ""
                    tail1 = parts[-1] if parts else ""
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

            # 合并类描述（追加到统一聚合结构中，最终写入总文件）
            for cl in file_classes:
                # 优先精确匹配其 qualname
                desc = cls_descs.get(cl.qualname, "")
                if not desc:
                    # 尝试规范化后的键匹配
                    q_norm = _normalize_key_global(cl.qualname)
                    desc = (
                        cls_descs.get(q_norm, "")
                        or global_cls_desc_by_qualname.get(cl.qualname, "")
                        or global_cls_desc_by_qualname.get(q_norm, "")
                    )
                if not desc:
                    # 宽松回退：使用类名尾部匹配（跨文件同名类回填）
                    simple = cl.name or cl.qualname.split(".")[-1]
                    desc = (
                        cls_descs.get(simple, "")
                        or global_cls_desc_by_name.get(simple, "")
                    )

                described_class = DescribedClass(
                    **cl.model_dump(),
                    description=desc,
                )
                described_classes_acc.append(described_class)

        print('finished')
        # 直接构造最终结果，functions 与 classes 为列表
        final_result = DescribeOutput(
            files=file_descs,
            functions=described_items,
            classes=described_classes_acc,
        )

        aggregate_file = Path(os.path.join("app","domain","services","rag","describe_output.json"))

        # 确保父目录存在
        aggregate_file.parent.mkdir(parents=True, exist_ok=True)

        # 写入 JSON 文件
        aggregate_file.write_text(
            json.dumps(final_result.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return final_result

    async def run(self, workspace_dir):
        return await self.describe_workspace(
            workspace_dir=workspace_dir,
        )
