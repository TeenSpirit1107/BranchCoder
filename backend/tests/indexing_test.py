import pytest
from app.domain.services.rag.indexing import RAGService

def test_rag_service_retrieve(tmp_path):
    # 初始化 RAGService
    service = RAGService(
        enable_rerank=True,
        rerank_top_n=5,
        initial_candidates=20,
    )

    # 1) 直接尝试从已有索引检索
    results = service.retrieve("flow", top_k=5)

    # 断言返回结果是字典
    assert isinstance(results, dict)

    # 断言三个关键结果类别都存在
    for key in ("file", "function", "class"):
        assert key in results

    # 2) 如果没有结果，尝试从 JSON 重新构建
    if not any(len(results.get(k, [])) for k in ("file", "function", "class")):
        service.load_from_json("describe_output.json")
        results = service.retrieve("你的查询", top_k=5)

        # 再次检查是否有结果
        assert any(len(results.get(k, [])) for k in ("file", "function", "class"))

    # 3) 调试输出（pytest -s 时可见）
    RAGService.pretty_print(results)
