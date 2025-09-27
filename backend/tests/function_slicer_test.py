import pytest
from app.domain.services.rag.function_slicer import slice_functions_in_workspace
from pydantic import BaseModel

def test_slice_functions_in_workspace():
    # 执行函数
    res = slice_functions_in_workspace("sample_workspace")

    # 断言返回值是 Pydantic 模型
    assert isinstance(res, BaseModel)

    # 打印结果（仅调试用，pytest -s 可见输出）
    print(res.model_dump_json(indent=2))

    # 进一步断言返回内容中应该有关键字段
    data = res.model_dump()
    assert "functions" in data   # 假设结果里有 "functions" 字段
    assert isinstance(data["functions"], list)
