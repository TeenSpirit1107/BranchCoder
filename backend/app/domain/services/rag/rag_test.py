# test_rag_indexer.py
import argparse
from typing import Any, Dict

from rag import TripleRAG, DEFAULT_LLM_MODEL_FOR_RERANK, DEFAULT_EMBED_MODEL


def pretty_print(results: Dict[str, Any]) -> None:
    for kind in ("file", "function", "class"):
        rows = results.get(kind, [])
        print(f"\n=== {kind.upper()} (top {len(rows)}) ===")
        for i, r in enumerate(rows, 1):
            md = r.get("metadata", {})
            if kind == "file":
                label = md.get("file", "")
            elif kind == "function":
                label = f"{md.get('qualname','')}  [{md.get('file','')}]"
            else:
                label = f"{md.get('name','')} ({md.get('qualname','')})  [{md.get('file','')}]"
            text = (r.get("text") or "").replace("\n", " ")
            print(f"{i}. score={r.get('score',0.0):.4f} | {label}")
            print(f"   {text[:240]}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Manual tester for TripleRAG (OpenAI Embeddings + optional LLM Rerank)")
    parser.add_argument("--data", type=str, default="descriptions/describe_output.json", help="Path to describe_output.json")
    parser.add_argument("--topk", type=int, default=5, help="Result top-k per index (final)")
    parser.add_argument("--embed", type=str, default=DEFAULT_EMBED_MODEL, help="OpenAI embedding model / Azure 部署名")
    parser.add_argument("--rerank", action="store_true", help="启用 LLM Re-rank")
    parser.add_argument("--rerank-topn", type=int, default=5, help="重排后保留的 Top-N")
    parser.add_argument("--initial-k", type=int, default=20, help="重排前每类召回候选数（> rerank-topn）")
    parser.add_argument("--llm", type=str, default=DEFAULT_LLM_MODEL_FOR_RERANK, help="用于 Re-rank 的 LLM 模型")
    args = parser.parse_args()

    rag = TripleRAG(
        embed_model_name=args.embed,
        llm_model_for_rerank=args.llm,
        enable_rerank=args.rerank,
        rerank_top_n=args.rerank_topn,
        initial_candidates=args.initial_k,
    )
    report = rag.build_from_json(args.data)

    print("✅ 索引构建完成（仅使用 description；缺失即跳过）：")
    print(
        f"  files: {report.files_indexed}/{report.files_total} (skipped {report.files_skipped}) | "
        f"functions: {report.functions_indexed}/{report.functions_total} (skipped {report.functions_skipped}) | "
        f"classes: {report.classes_indexed}/{report.classes_total} (skipped {report.classes_skipped})"
    )

    print("\n输入查询开始检索（Ctrl+C 退出）")
    while True:
        try:
            q = input("\n🔎 Query> ").strip()
            if not q:
                continue
            res = rag.retrieve(q, top_k=args.topk)
            pretty_print(res)
        except KeyboardInterrupt:
            print("\nBye!")
            break

if __name__ == "__main__":
    main()
