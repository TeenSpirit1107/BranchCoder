from typing import Optional

from llm.chat_llm import AsyncChatClientWrapper
from rag.description_generator import DescriptionGenerator
from rag.indexing import IndexingService
from utils.logger import Logger

# Initialize logger instance
logger = Logger('rag_service', log_to_file=False)

class RagService:

    def __init__(
            self,
            llm: AsyncChatClientWrapper,
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

    async def initiate(self, workspace_dir):
        description_result = await self.description_generator.run(workspace_dir=workspace_dir)
        logger.info(f"description generation finish")
        await self.indexing_service.load_from_model(description_result)
        logger.info(f"indexing initialization finish")
        return True

    async def retrival(self, query):
        logger.info(f"retrival start")
        results = await self.indexing_service.retrieve(query, top_k=5)
        logger.info(f"retrival finish")
        return results
