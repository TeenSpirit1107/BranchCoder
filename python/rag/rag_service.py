from typing import Optional

from llm.chat_llm import AsyncChatClientWrapper
from rag.description_generator import DescriptionGenerator
from rag.indexing import IndexingService
from rag.hash import (
    compute_workspace_file_hashes,
    get_workspace_storage_path,
    save_workspace_metadata,
    check_indices_exist,
    get_description_output_path,
)
from rag.incremental_updater import update_changed_files_incremental
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
        self.enable_rerank = enable_rerank
        self.rerank_top_n = rerank_top_n
        self.initial_candidates = initial_candidates
        self.indexing_service = None  # Will be initialized with workspace-specific path

    def _initialize_indexing_service(self, workspace_dir: str) -> None:
        """Initialize indexing service with workspace-specific storage path."""
        storage_path = get_workspace_storage_path(workspace_dir)
        self.indexing_service = IndexingService(
            enable_rerank=self.enable_rerank,
            rerank_top_n=self.rerank_top_n,
            initial_candidates=self.initial_candidates,
            persist_root_dir=storage_path,
        )

    async def initiate(self, workspace_dir):
        """
        Initialize RAG service for the workspace.
        Checks if indices already exist for this workspace_dir - if so, calls reload instead of rebuilding.
        
        Args:
            workspace_dir: Path to the workspace directory
            
        Returns:
            True if initialized successfully
        """
        logger.info(f"Initializing RAG service for workspace: {workspace_dir}")
        
        # Check if indices already exist for this workspace_dir
        if check_indices_exist(workspace_dir):
            logger.info("Indices already exist for this workspace, reloading instead of rebuilding")
            return await self.reload(workspace_dir)
        
        # Build new indices
        logger.info("Building new indices for workspace")
        
        # Initialize indexing service with workspace-specific path
        self._initialize_indexing_service(workspace_dir)
        
        # Get path for description_output.json in workspace storage
        description_output_path = get_description_output_path(workspace_dir)
        
        # Generate descriptions and build indices
        description_result = await self.description_generator.run(
            workspace_dir=workspace_dir,
            output_path=description_output_path
        )
        logger.info("Description generation finished")
        await self.indexing_service.load_from_model(description_result)
        logger.info("Indexing initialization finished")
        
        # Compute and save file hashes after successful indexing (for future use)
        file_hashes = compute_workspace_file_hashes(workspace_dir)
        save_workspace_metadata(workspace_dir, file_hashes)
        
        return True

    async def reload(self, workspace_dir):
        """
        Reload RAG service from existing indices.
        Assumes indices already exist for this workspace_dir.
        
        Args:
            workspace_dir: Path to the workspace directory
            
        Returns:
            True if reloaded successfully
        """
        logger.info(f"Reloading RAG service for workspace: {workspace_dir}")
        
        # Initialize indexing service - it will automatically load existing indices
        self._initialize_indexing_service(workspace_dir)
        
        logger.info("Successfully reloaded RAG service from existing indices")
        return True

    async def retrival(self, query):
        if self.indexing_service is None:
            raise RuntimeError("Indexing service not initialized. Please call initiate() or reload() first.")
        logger.info(f"retrival start")
        results = await self.indexing_service.retrieve(query, top_k=5)
        logger.info(f"retrival finish")
        return results

    async def update_changed_files(
        self, 
        workspace_dir: str,
        changed_files: list[str],
        deleted_files: list[str],
    ) -> dict:
        """
        Incrementally update RAG indices for specified files.
        This method processes only the modified files without rebuilding the entire index.
        
        Args:
            workspace_dir: Path to the workspace directory
            changed_files: List of relative file paths that have been changed or added
            deleted_files: List of relative file paths that have been deleted
            
        Returns:
            Dictionary with update statistics:
            {
                "changed_files": list of changed file paths,
                "added_files": list of newly added file paths,
                "deleted_files": list of deleted file paths,
                "updated": True/False
            }
        """
        # Ensure indexing service is initialized
        if self.indexing_service is None:
            logger.info("Indexing service not initialized, initializing now")
            self._initialize_indexing_service(workspace_dir)
        
        # Delegate to incremental_updater module
        return await update_changed_files_incremental(
            description_generator=self.description_generator,
            indexing_service=self.indexing_service,
            workspace_dir=workspace_dir,
            changed_files=changed_files,
            deleted_files=deleted_files,
        )
