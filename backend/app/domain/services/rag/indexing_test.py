from indexing import RAGService

service = RAGService(
    enable_rerank=True,           # enable LLM re-ranking
    rerank_top_n=5,               # top-N after re-ranking
    initial_candidates=20,        # candidates per index before re-ranking
)

# 1) Try retrieving directly from persisted indexes (if already built previously)
results = service.retrieve("flow", top_k=5)

# # 2) If no results at all, build from JSON then retry
if not any(len(results.get(k, [])) for k in ("file", "function", "class")):
    # Build indexes from describe_output.json (only if needed)
    service.load_from_json("describe_output.json")
    results = service.retrieve("你的查询", top_k=5)

# 3) Optional: pretty print for debugging
RAGService.pretty_print(results)