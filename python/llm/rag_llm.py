from __future__ import annotations

import os
from dotenv import load_dotenv

# ---- LlamaIndex Core ----
from llama_index.core import Settings

# ---- OpenAI Embedding & LLM ----
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

# Load environment variables
load_dotenv()

# ======= OpenAI 配置（从环境变量读取）=======
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_BASE_URL")
proxy = os.getenv("OPENAI_PROXY")

# Set proxy if provided
if proxy:
    os.environ["HTTP_PROXY"] = proxy
    os.environ["HTTPS_PROXY"] = proxy

# 默认模型名（从环境变量读取，带默认值）
DEFAULT_EMBED_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL")
DEFAULT_LLM_MODEL_FOR_RERANK = os.getenv("OPENAI_RANKING_MODEL")

def init_openai_embedding(model: str) -> None:
    """Initialize OpenAI Embedding model for LlamaIndex Settings.

    This centralizes the embedding initialization so domain code does not
    depend on provider-specific details.
    """
    kwargs = dict(model=model, api_key=OPENAI_API_KEY, api_base=OPENAI_API_BASE)
    Settings.embed_model = OpenAIEmbedding(**kwargs)


def init_openai_llm(model: str) -> None:
    """Initialize OpenAI chat LLM for LlamaIndex Settings.

    Used by LLM-based rerankers and other components that rely on Settings.llm.
    """
    kwargs = dict(model=model, api_key=OPENAI_API_KEY, api_base=OPENAI_API_BASE)
    Settings.llm = OpenAI(**kwargs)


