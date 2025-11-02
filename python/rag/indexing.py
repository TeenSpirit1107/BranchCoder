# rag_indexer.py
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---- LlamaIndex Core ----
from llama_index.core import Document, VectorStoreIndex, StorageContext, load_index_from_storage

# ---- Postprocessor: LLM Rerank ----
from llama_index.core.postprocessor import LLMRerank


from llm.rag_llm import (
    init_openai_embedding,
    init_openai_llm,
    DEFAULT_EMBED_MODEL,
    DEFAULT_LLM_MODEL_FOR_RERANK,
)

# Concurrency limit for async indexing operations (from .env file, default: 2)
DEFAULT_BUILD_CONCURRENCY = int(os.getenv("RAG_BUILD_CONCURRENCY", "2"))


@dataclass
class RAGBuildReport:
    files_total: int
    functions_total: int
    classes_total: int
    files_indexed: int
    functions_indexed: int
    classes_indexed: int
    files_skipped: int
    functions_skipped: int
    classes_skipped: int


# 模型初始化由 infrastructure 层统一提供


class Indexing:
    """
    三套独立索引：file / function / class（仅用 description 建索引；缺失即跳过）
    可选：LLM Re-rank（基于 OpenAI 对话模型的交叉编码式重排）
    """

    def __init__(
        self,
        embed_model_name: str = DEFAULT_EMBED_MODEL,
        llm_model_for_rerank: str = DEFAULT_LLM_MODEL_FOR_RERANK,
        enable_rerank: bool = False,
        rerank_top_n: int = 5,
        initial_candidates: int = 20,
        persist_root_dir: Optional[str] = None,
    ) -> None:
        """
        :param embed_model_name: Embedding 模型（或 Azure 部署名）
        :param llm_model_for_rerank: 用于重排的 LLM 模型名（如 gpt-4o-mini / gpt-4o）
        :param enable_rerank: 是否启用重排
        :param rerank_top_n: 重排后截断的 Top-N
        :param initial_candidates: 重排前每类索引召回的候选数（> rerank_top_n）
        """
        # 初始化 OpenAI Embedding（必须）
        init_openai_embedding(embed_model_name)

        # 是否启用重排
        self.enable_rerank = enable_rerank
        self.rerank_top_n = rerank_top_n
        self.initial_candidates = max(initial_candidates, rerank_top_n)

        # 如果启用重排，则初始化 LLM & Reranker
        self.llm_reranker: Optional[LLMRerank] = None
        if self.enable_rerank:
            init_openai_llm(llm_model_for_rerank)
            # 使用全局 Settings.llm；这里也可传 llm=Settings.llm 显式绑定
            self.llm_reranker = LLMRerank(top_n=self.rerank_top_n)

        # 三个索引
        self.file_index: Optional[VectorStoreIndex] = None
        self.func_index: Optional[VectorStoreIndex] = None
        self.class_index: Optional[VectorStoreIndex] = None

        self.report: Optional[RAGBuildReport] = None

        # 并发锁：保护索引的构建和检索操作
        self._build_lock = asyncio.Lock()
        self._retrieve_lock = asyncio.Lock()
        
        # 并发信号量：限制异步构建时的并发数量（从 .env 文件读取，默认: 2）
        self._build_semaphore = asyncio.Semaphore(DEFAULT_BUILD_CONCURRENCY)

        # 设置持久化目录
        self.persist_root_dir = self._resolve_persist_root(persist_root_dir)
        self._ensure_dirs()

        # 启动时尝试从磁盘加载已有索引
        self._autoload_indexes()

    # ---------- 持久化与加载辅助 ----------

    def _resolve_persist_root(self, persist_root_dir: Optional[str]) -> str:
        """Resolve persist directory; default to .rag_store under this module folder."""
        if persist_root_dir:
            return str(Path(persist_root_dir).expanduser().absolute())
        module_dir = Path(__file__).parent
        return str((module_dir / ".rag_store").absolute())

    def _ensure_dirs(self) -> None:
        Path(self._dir_for_kind("file")).mkdir(parents=True, exist_ok=True)
        Path(self._dir_for_kind("function")).mkdir(parents=True, exist_ok=True)
        Path(self._dir_for_kind("class")).mkdir(parents=True, exist_ok=True)

    def _dir_for_kind(self, kind: str) -> str:
        return str(Path(self.persist_root_dir) / kind)

    def _persist_index(self, index: Optional[VectorStoreIndex], kind: str) -> None:
        if index is None:
            return
        storage_dir = self._dir_for_kind(kind)
        index.storage_context.persist(persist_dir=storage_dir)

    def _load_index(self, kind: str) -> Optional[VectorStoreIndex]:
        storage_dir = self._dir_for_kind(kind)
        if not Path(storage_dir).exists():
            return None
        try:
            storage_ctx = StorageContext.from_defaults(persist_dir=storage_dir)
            return load_index_from_storage(storage_ctx)
        except Exception:
            return None

    def _autoload_indexes(self) -> None:
        self.file_index = self._load_index("file") or self.file_index
        self.func_index = self._load_index("function") or self.func_index
        self.class_index = self._load_index("class") or self.class_index

    # ---------- 建索引 ----------

    @staticmethod
    def _docs_from_items(
        items: List[Dict[str, Any]],
        kind: str,
    ) -> Tuple[List[Document], int, int]:
        """
        仅抽取 description 构造 Document；没有 description 的条目直接跳过
        """
        docs: List[Document] = []
        skipped = 0
        for i, it in enumerate(items or []):
            desc = (it.get("description") or "").strip()
            if not desc:
                skipped += 1
                continue
            meta: Dict[str, Any] = {"type": kind, "idx": i}
            if kind == "file":
                meta["file"] = it.get("file", "")
            elif kind == "function":
                meta["file"] = it.get("file", "")
                meta["qualname"] = it.get("qualname", "")
            elif kind == "class":
                meta["file"] = it.get("file", "")
                meta["name"] = it.get("name", "")
                meta["qualname"] = it.get("qualname", "")
            docs.append(Document(text=desc, metadata=meta, doc_id=f"{kind}::{i}"))
        return docs, len(docs), skipped

    async def _build_index_async(self, docs: List[Document]) -> Optional[VectorStoreIndex]:
        """异步构建单个索引，使用信号量限制并发。"""
        if not docs:
            return None
        async with self._build_semaphore:
            # Run synchronous from_documents in executor to make it async
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, VectorStoreIndex.from_documents, docs
            )

    async def build_from_dict(self, data: Dict[str, Any]) -> RAGBuildReport:
        """异步构建索引，使用锁保护并发访问，并使用信号量限制构建并发数。"""
        async with self._build_lock:
            files = data.get("files", []) or []
            functions = data.get("functions", []) or []
            classes = data.get("classes", []) or []

            file_docs, file_indexed, file_skipped = self._docs_from_items(files, "file")
            func_docs, func_indexed, func_skipped = self._docs_from_items(functions, "function")
            class_docs, class_indexed, class_skipped = self._docs_from_items(classes, "class")

            # Build three indexes concurrently with semaphore limiting
            build_tasks = [
                self._build_index_async(file_docs),
                self._build_index_async(func_docs),
                self._build_index_async(class_docs),
            ]
            results = await asyncio.gather(*build_tasks)
            self.file_index, self.func_index, self.class_index = results

            # 持久化到磁盘
            self._persist_index(self.file_index, "file")
            self._persist_index(self.func_index, "function")
            self._persist_index(self.class_index, "class")

            self.report = RAGBuildReport(
                files_total=len(files),
                functions_total=len(functions),
                classes_total=len(classes),
                files_indexed=file_indexed,
                functions_indexed=func_indexed,
                classes_indexed=class_indexed,
                files_skipped=file_skipped,
                functions_skipped=func_skipped,
                classes_skipped=class_skipped,
            )
            return self.report

    async def build_from_json(self, json_path: str) -> RAGBuildReport:
        """异步从 JSON 文件构建索引。"""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return await self.build_from_dict(data)

    async def build_from_model(self, obj: Any) -> RAGBuildReport:
        """支持直接从 Pydantic/类似对象构建，自动使用 model_dump()/dict()。"""
        if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
            data = obj.model_dump()
        elif hasattr(obj, "dict") and callable(getattr(obj, "dict")):
            data = obj.dict()
        else:
            raise TypeError("Unsupported object type: expected Pydantic-like with model_dump()/dict().")
        return await self.build_from_dict(data)

    # ---------- 检索 +（可选）重排 ----------

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        - 如果未开启重排：对每类索引直接召回 top_k
        - 如果开启重排：先召回 initial_candidates，再用 LLMRerank 重排并截断到 rerank_top_n
        返回：
        {
          "file":     [{"score": float, "text": str, "metadata": {...}}, ...],
          "function": [...],
          "class":    [...]
        }
        
        使用异步锁保护并发检索操作。
        """
        async with self._retrieve_lock:
            out: Dict[str, List[Dict[str, Any]]] = {"file": [], "function": [], "class": []}

            def _do_search(index: Optional[VectorStoreIndex], kind: str) -> None:
                if index is None:
                    return

                k = self.initial_candidates if self.enable_rerank else top_k
                nodes = index.as_retriever(similarity_top_k=k).retrieve(query)

                # 进行 LLM 重排
                if self.enable_rerank and self.llm_reranker is not None and nodes:
                    nodes = self.llm_reranker.postprocess_nodes(nodes, query_str=query)

                # 截断（未开启重排时 nodes 已是 top_k；开启时 nodes 已是 rerank_top_n）
                if not self.enable_rerank:
                    nodes = nodes[:top_k]

                for n in nodes:
                    out[kind].append(
                        {
                            "score": float(getattr(n, "score", 0.0) or 0.0),
                            "text": n.text or "",
                            "metadata": n.metadata or {},
                        }
                    )

            _do_search(self.file_index, "file")
            _do_search(self.func_index, "function")
            _do_search(self.class_index, "class")
            return out


class IndexingService:
    """
    高层封装：负责加载 `describe_output.json`、构建索引，并提供函数式的查询接口。
    所有方法都是异步的，支持并发调用。

    用法示例：
    
    service = IndexingService(enable_rerank=True)
    await service.load_from_json("/abs/path/to/describe_output.json")
    results = await service.retrieve("如何调用XXX函数?", top_k=5)
    """

    def __init__(
        self,
        embed_model_name: str = DEFAULT_EMBED_MODEL,
        llm_model_for_rerank: str = DEFAULT_LLM_MODEL_FOR_RERANK,
        enable_rerank: bool = False,
        rerank_top_n: int = 5,
        initial_candidates: int = 20,
        persist_root_dir: Optional[str] = None,
    ) -> None:
        # 组合底层 TripleRAG
        self._indexing = Indexing(
            embed_model_name=embed_model_name,
            llm_model_for_rerank=llm_model_for_rerank,
            enable_rerank=enable_rerank,
            rerank_top_n=rerank_top_n,
            initial_candidates=initial_candidates,
            persist_root_dir=persist_root_dir,
        )

    async def load_from_json(self, json_path: str) -> RAGBuildReport:
        """异步加载 describe_output.json 并构建三个索引。"""
        return await self._indexing.build_from_json(json_path)

    async def load_from_dict(self, data: Dict[str, Any]) -> RAGBuildReport:
        """异步支持直接从内存字典构建。"""
        return await self._indexing.build_from_dict(data)

    async def load_from_model(self, obj: Any) -> RAGBuildReport:
        """异步支持直接传入 Pydantic/类似对象（如 DescribeOutput）。"""
        return await self._indexing.build_from_model(obj)

    async def retrieve(self, query: str, top_k: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """异步对已构建的索引执行查询，返回 file/function/class 三类结果。"""
        return await self._indexing.retrieve(query, top_k=top_k)

    @staticmethod
    def pretty_print(results: Dict[str, Any]) -> None:
        """简易打印工具，便于调试。"""
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
