#!/usr/bin/env python3
"""
Workspace RAG Tool - Retrieve code from workspace using RAG
"""

from typing import Dict, Any, Optional
from utils.logger import Logger
from llm.chat_llm import AsyncChatClientWrapper
from rag.rag_service import RagService
from tools.base_tool import MCPTool

logger = Logger('workspace_rag_tool', log_to_file=False)


class WorkspaceRAGTool(MCPTool):
    """Tool for retrieving code from workspace using RAG."""
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "workspace_rag_retrieve"
    
    def __init__(self):
        """Initialize workspace RAG tool."""
        self.rag_service: Optional[RagService] = None
        self.workspace_dir: Optional[str] = None
        self._llm_client: Optional[AsyncChatClientWrapper] = None
    
    def set_workspace_dir(self, workspace_dir: str):
        """
        Set the workspace directory. RAG service will be initialized lazily on first use.
        
        Args:
            workspace_dir: Path to workspace directory
        """
        if self.workspace_dir == workspace_dir:
            return  # Already set
        
        self.workspace_dir = workspace_dir
        logger.info(f"Setting workspace directory: {workspace_dir}")
        # Note: rag_service instance is reused, but indexing_service will be re-initialized
        # when reload() is called with the new workspace_dir
    
    async def _ensure_rag_service_initialized(self, workspace_dir: str) -> bool:
        """
        Ensure RAG service is initialized for the given workspace.
        Reuses RagService instance and LLM client to avoid unnecessary re-initialization.
        
        Args:
            workspace_dir: Path to workspace directory
        
        Returns:
            True if initialized successfully, False otherwise
        """
        # If already initialized for this workspace, return
        if self.rag_service is not None and self.workspace_dir == workspace_dir:
            # Check if indexing_service is initialized for this workspace
            if self.rag_service.indexing_service is not None:
                return True
        
        # Initialize LLM client if not already done (reuse if exists)
        if self._llm_client is None:
            try:
                self._llm_client = AsyncChatClientWrapper()
                logger.info("LLM client initialized for RAG tool")
            except Exception as e:
                logger.error(f"Failed to initialize LLM client: {e}", exc_info=True)
                return False
        
        # Initialize RAG service instance if not exists (reuse if exists)
        if self.rag_service is None:
            try:
                self.rag_service = RagService(
                    llm=self._llm_client,
                    enable_rerank=True,
                    rerank_top_n=10,
                    initial_candidates=30,
                )
                logger.info("RAG service instance created")
            except Exception as e:
                logger.error(f"Failed to initialize RAG service: {e}", exc_info=True)
                return False
        
        # Reload RAG service for this workspace (re-initializes indexing_service)
        # This is safe even if already loaded for a different workspace
        try:
            await self.rag_service.reload(workspace_dir)
            self.workspace_dir = workspace_dir
            logger.info(f"RAG service reloaded for workspace: {workspace_dir}")
            return True
        except Exception as e:
            logger.warning(f"Failed to reload RAG service: {e}")
            return False
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": "workspace_rag_retrieve",
                "description": "Search and retrieve code from the workspace using RAG (Retrieval Augmented Generation). Use this to find relevant code, functions, classes, or documentation within the current workspace. This is useful for understanding the codebase, finding implementations, or locating specific functionality.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find relevant code in the workspace"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    
    async def execute(self, query: str) -> Dict[str, Any]:
        """
        Retrieve code from workspace using RAG.
        
        Args:
            query: The search query
        
        Returns:
            Dictionary with retrieved code results
        """
        logger.info(f"RAG retrieval: {query}")
        
        # Use workspace directory set during initialization
        if not self.workspace_dir:
            return {
                "success": False,
                "error": "Workspace directory not set. Please set workspace directory during initialization.",
                "query": query
            }
        
        # Ensure RAG service is initialized
        if not await self._ensure_rag_service_initialized(self.workspace_dir):
            return {
                "success": False,
                "error": "Failed to initialize RAG service. Please ensure workspace directory is set and RAG indices exist.",
                "query": query
            }
        
        try:
            # Perform retrieval - returns dict with "file", "function", "class" keys
            results = await self.rag_service.retrieve(query)
            
            # Format results - flatten all types into a single list
            formatted_results = []
            total_count = 0
            
            for result_type in ["file", "function", "class"]:
                type_results = results.get(result_type, [])
                for result in type_results:
                    metadata = result.get("metadata", {})
                    file_path = metadata.get("file", "")
                    
                    formatted_results.append({
                        "type": result_type,
                        "content": result.get("text", ""),
                        "file_path": file_path,
                        "score": result.get("score", 0.0),
                        "metadata": metadata
                    })
                    total_count += 1
            
            logger.info(f"Retrieved {total_count} results from workspace ({len(results.get('file', []))} files, {len(results.get('function', []))} functions, {len(results.get('class', []))} classes)")
            
            return {
                "success": True,
                "query": query,
                "results": formatted_results,
                "count": total_count,
                "by_type": {
                    "file": len(results.get("file", [])),
                    "function": len(results.get("function", [])),
                    "class": len(results.get("class", []))
                }
            }
        except Exception as e:
            logger.error(f"Error in RAG retrieval: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

