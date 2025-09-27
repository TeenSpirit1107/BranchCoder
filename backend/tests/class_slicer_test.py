import pytest
from app.domain.services.rag.class_slicer import slice_classes_in_workspace
from pydantic import BaseModel

def test_slice_classes_in_workspace():
    # 执行函数
    res = slice_classes_in_workspace("sample_workspace")

    # 断言返回值是一个 Pydantic 模型
    assert isinstance(res, BaseModel)

    # 打印结果（调试时可见）
    print(res.model_dump_json(indent=2))

    # 进一步断言返回内容中应该有关键字段
    data = res.model_dump()
    assert "classes" in data   # 假设返回结果里有 "classes" 字段
    assert isinstance(data["classes"], list)
