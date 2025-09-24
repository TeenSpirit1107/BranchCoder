from pathlib import Path
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import json
import os

# -----------------------------
# Given models (from your code)
# -----------------------------
class WorkspaceFunction(BaseModel):
    file: str                       # 来自于哪个文件（相对路径）
    qualname: str                   # 函数（或方法）限定名
    source: str                     # 函数源代码
    calls: List[str] = Field(default_factory=list)
    called_by: List[str] = Field(default_factory=list)


class WorkspaceResult(BaseModel):
    # WorkspaceResult 就是 function slice（函数切片）的集合
    items: List[WorkspaceFunction]


# -------------------------------------
# New models for descriptions & outputs
# -------------------------------------
class DescribedWorkspaceFunction(WorkspaceFunction):
    """为函数补充自然语言描述。"""
    description: str = ""


class FileDescription(BaseModel):
    """每个文件级别的描述；可单独存储为 sidecar JSON。"""
    file: str
    description: str


class DescribedWorkspaceResult(WorkspaceResult):
    """与 WorkspaceResult 结构一致，但 items 升级为带 description 的版本，保持向后兼容。"""
    items: List[DescribedWorkspaceFunction]


class DescribeOutput(BaseModel):
    """最终返回结果：
    - files: 每个文件的描述列表（可独立落盘）
    - functions: 与 WorkspaceResult 兼容的函数切片（仅在 WorkspaceFunction 基础上多了 description 字段）
    """
    files: List[FileDescription]
    functions: DescribedWorkspaceResult


# -----------------------------
# Core pipeline
# -----------------------------
PROMPT_TEMPLATE = """
你是资深软件工程师，请阅读以下源文件并生成两个层级的中文描述：
1) 文件级别简介（3-6 句），概述该文件的职责、关键类型/函数、外部依赖与协作关系；
2) 函数级别简介：对列出的每个函数写 1-2 句用途说明，聚焦输入/输出、副作用与调用关系。

务必使用固定输出格式：
[FILE]
<文件级别简介>
[FUNCTIONS]
<qualname>: <函数描述>
<qualname>: <函数描述>
...

文件内容：
--- BEGIN FILE ---
File: {file}
{file_text}
--- END FILE ---

函数清单（qualname）：
Functions:
{functions_bulleted}
""".strip()


def _build_prompt(file: str, file_text: str, functions: List[WorkspaceFunction]) -> str:
    bullets = "\n".join(f"- {fn.qualname}" for fn in functions)
    return PROMPT_TEMPLATE.format(file=file, file_text=file_text, functions_bulleted=bullets)


def _group_functions_by_file(result: WorkspaceResult) -> Dict[str, List[WorkspaceFunction]]:
    grouped: Dict[str, List[WorkspaceFunction]] = {}
    for fn in result.items:
        grouped.setdefault(fn.file, []).append(fn)
    return grouped


def parse_llm_response(raw: str) -> Tuple[str, Dict[str, str]]:
    """将 LLM 输出解析为 (file_description, {qualname: fn_description}).
    约定格式见 PROMPT_TEMPLATE。鲁棒处理：忽略无法识别的行。"""
    file_desc = ""
    fn_descs: Dict[str, str] = {}

    section = None
    for line in raw.splitlines():
        s = line.strip()
        if s == "[FILE]":
            section = "FILE"
            continue
        if s == "[FUNCTIONS]":
            section = "FUNCTIONS"
            continue
        if not s:
            continue
        if section == "FILE":
            # 累积多行
            file_desc = (file_desc + " " + s).strip()
        elif section == "FUNCTIONS":
            # 形如：qualname: 描述
            if ":" in s:
                q, d = s.split(":", 1)
                q = q.strip()
                d = d.strip()
                if q:
                    fn_descs[q] = d
    return file_desc, fn_descs


def describe_workspace(
    function_slice: WorkspaceResult,
    base_dir: str | Path,
    llm = None,
    output_dir: Optional[str | Path] = None,
) -> DescribeOutput:
    """核心入口：
    1) 按文件分组函数
    2) 读取文件源码，调用 LLM 生成文件/函数描述
    3) 把函数描述并回到切片数据
    4) 将每个文件级描述存盘（可选）
    5) 返回归并后的结果
    """
    base_path = Path(base_dir)
    if output_dir is not None:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = None

    grouped = _group_functions_by_file(function_slice)

    described_items: List[DescribedWorkspaceFunction] = []
    file_descs: List[FileDescription] = []

    for rel_file, fns in grouped.items():
        abs_file = (base_path / rel_file).resolve()
        try:
            file_text = abs_file.read_text(encoding="utf-8")
        except Exception:
            # 如果读取失败，仍然走流程但标记占位文本
            file_text = f"<无法读取文件: {abs_file}>"
            raise Exception(file_text)

        prompt = _build_prompt(rel_file, file_text, fns)
        print(prompt)
        resp = llm.chat.completions.create(
            model='gpt-5-nano',
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            content = resp.choices[0].message.content  # type: ignore[attr-defined]
        except Exception:
            content = ""
        print(content)
        file_desc, fn_descs = parse_llm_response(content)

        # 保存文件级描述
        fd = FileDescription(file=rel_file, description=file_desc)
        file_descs.append(fd)

        # 不再为每个文件写 sidecar，仅在函数末尾写聚合文件

        # 合并函数描述
        for fn in fns:
            described_items.append(
                DescribedWorkspaceFunction(
                    **fn.model_dump(),
                    description=fn_descs.get(fn.qualname, ""),
                )
            )

    result = DescribeOutput(
        files=file_descs,
        functions=DescribedWorkspaceResult(items=described_items)
    )

    # 将完整的 DescribeOutput 落盘（如果指定了 output_dir）
    if output_path is not None:
        aggregate_file = output_path / "describe_output.json"
        aggregate_file.write_text(
            json.dumps(result.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return result


# -----------------------------
# CLI / 示例
# -----------------------------
if __name__ == "__main__":
    # 你已有的切片逻辑
    from function_slicer import slice_functions_in_workspace

    workspace_dir = "sample_workspace"  # 你的代码中已有示例
    WorkspaceResult = slice_functions_in_workspace(workspace_dir)

    # 选择一个 LLM 实现
    from openai import OpenAI
    llm = OpenAI(api_key='sk-8L8llDs3K8DZ7FOv00527a79Af714904A7D8C06a7e389d46',base_url='https://api.shubiaobiao.cn/v1')
    result = describe_workspace(
        function_slice=WorkspaceResult,
        base_dir=workspace_dir,
        llm=llm,
        output_dir="descriptions",  # 可改为 None 以跳过写盘
    )

    # 控制台输出
    print("=== File Descriptions ===")
    for fd in result.files:
        print(f"[FILE] {fd.file}{fd.description}")

    print("=== Function Items (with description) ===")
    for item in result.functions.items:
        print(json.dumps(item.model_dump(), ensure_ascii=False, indent=2))
