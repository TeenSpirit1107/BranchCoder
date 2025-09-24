from indexing import RAGService

service = RAGService(
    enable_rerank=True,           # 是否启用 LLM 重排
    rerank_top_n=5,               # 重排后保留的 Top-N
    initial_candidates=20,        # 重排前每类候选数
)

# 1) 加载并建索引（只依赖 description 字段）
report = service.load_from_json("describe_output.json")

# 2) 查询（函数调用，不再使用 CLI）
results = service.retrieve("你的查询", top_k=5)

# 3) 可选：打印调试
RAGService.pretty_print(results)