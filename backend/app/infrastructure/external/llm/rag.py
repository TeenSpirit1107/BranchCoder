from __future__ import annotations

# ---- LlamaIndex Core ----
from llama_index.core import Settings

# ---- OpenAI Embedding & LLM ----
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

from app.main import settings

# ======= OpenAI 配置（如需改为环境变量，请在此文件中调整）=======
# NOTE: Hard-coded for now to mirror previous behavior. Consider env vars.
OPENAI_API_KEY = settings.api_key
OPENAI_API_BASE = settings.api_base

# 默认模型名
DEFAULT_EMBED_MODEL = settings.embedding_model
DEFAULT_LLM_MODEL_FOR_RERANK = settings.ranking_model

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


