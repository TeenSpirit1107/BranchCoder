import logging
from typing import Optional

from app.domain.external.llm import LLM
from app.domain.services.rag.description_generator import DescriptionGenerator
from app.domain.services.rag.indexing import IndexingService

logger = logging.getLogger(__name__)

class RagService:

    def __init__(
            self,
            llm: LLM,
            enable_rerank: Optional[bool] = True,
            rerank_top_n: Optional[int] = 10,
            initial_candidates: Optional[int] = 30, # 重排前每类候选数
    ):
        self.description_generator = DescriptionGenerator(
            llm=llm,
        )
        self.indexing_service = IndexingService(
            enable_rerank=enable_rerank,
            rerank_top_n=rerank_top_n,
            initial_candidates=initial_candidates,
        )

    async def initiate(self, workspace_dir='/app/upload'):
        description_result = await self.description_generator.run(workspace_dir=workspace_dir)
        logger.info(f"description generation finish")
        self.indexing_service.load_from_model(description_result)
        logger.info(f"indexing initialization finish")
        return True

    async def retrival(self, query):
        logger.info(f"retrival start")
        results = self.indexing_service.retrieve(query, top_k=5)
        logger.info(f"retrival finish")
        return results
