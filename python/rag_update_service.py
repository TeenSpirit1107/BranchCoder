#!/usr/bin/env python3
"""
RAG Update Service for VS Code Extension
This script handles incremental updates to RAG indices when files are changed.
Receives workspace directory and file paths via stdin and updates RAG indices incrementally.
"""

import json
import sys
import os
import asyncio
from pathlib import Path

from utils.logger import Logger
from llm.chat_llm import AsyncChatClientWrapper
from rag.rag_service import RagService

# Initialize logger
logger = Logger('rag_update_service', log_to_file=False)

async def update_rag(
    workspace_dir: str,
    changed_files: list[str],
    deleted_files: list[str],
) -> dict:
    """
    Update RAG service with changed files for the given workspace directory.
    
    Args:
        workspace_dir: Path to the workspace directory
        changed_files: List of relative file paths that have been changed or added
        deleted_files: List of relative file paths that have been deleted
    
    Returns:
        Dictionary with status and message
    """
    try:
        logger.info(f"Updating RAG service for workspace: {workspace_dir}")
        logger.info(f"Changed files: {len(changed_files)}, Deleted files: {len(deleted_files)}")
        
        # Initialize LLM client
        llm_client = AsyncChatClientWrapper()
        logger.info("LLM client initialized successfully")
        
        # Initialize RAG service (it will reload existing indices if they exist)
        rag_service = RagService(
            llm=llm_client,
            enable_rerank=True,
            rerank_top_n=10,
            initial_candidates=30,
        )
        
        # Check if indices exist - if not, initialize first
        from rag.hash import check_indices_exist
        if not check_indices_exist(workspace_dir):
            logger.info("Indices do not exist, initializing first...")
            await rag_service.initiate(workspace_dir=workspace_dir)
            logger.info("RAG service initialized successfully")
            return {
                "status": "success",
                "message": f"RAG service initialized for workspace: {workspace_dir}"
            }
        
        # Reload existing indices
        await rag_service.reload(workspace_dir)
        
        # Update changed files
        result = await rag_service.update_changed_files(
            workspace_dir=workspace_dir,
            changed_files=changed_files,
            deleted_files=deleted_files,
        )
        
        if result.get("updated", False):
            logger.info("RAG service updated successfully")
            changed_count = len(result.get("changed_files", []))
            deleted_count = len(result.get("deleted_files", []))
            return {
                "status": "success",
                "message": f"Updated {changed_count} changed files and {deleted_count} deleted files"
            }
        else:
            logger.info("No files needed updating")
            return {
                "status": "success",
                "message": "No files needed updating"
            }
            
    except Exception as e:
        logger.error(f"Error updating RAG service: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to update RAG service: {str(e)}"
        }

async def async_main():
    """Async main entry point - reads workspace path and file paths from stdin, updates RAG, writes to stdout"""
    try:
        logger.info("RAG update service started, waiting for input...")
        
        # Read input from stdin
        input_data = sys.stdin.read()
        
        if not input_data:
            logger.error("No input data received")
            raise ValueError("No input data received")
        
        logger.debug(f"Received input data length: {len(input_data)}")
        
        # Parse JSON input
        try:
            data = json.loads(input_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON input: {e}")
            raise
        
        workspace_dir = data.get("workspace_dir", "")
        changed_files = data.get("changed_files", [])
        deleted_files = data.get("deleted_files", [])
        
        if not workspace_dir:
            logger.error("No workspace_dir provided in input data")
            raise ValueError("No workspace_dir provided")
        
        if not isinstance(changed_files, list):
            changed_files = []
        if not isinstance(deleted_files, list):
            deleted_files = []
        
        logger.info(f"Updating RAG for workspace: {workspace_dir}")
        logger.info(f"Files to process: {len(changed_files)} changed/added, {len(deleted_files)} deleted")
        
        # Update RAG service
        result = await update_rag(
            workspace_dir=workspace_dir,
            changed_files=changed_files,
            deleted_files=deleted_files,
        )
        
        # Return JSON response
        logger.info("RAG update completed, sending response to stdout")
        print(json.dumps(result))
        
    except Exception as e:
        logger.error(f"Error in async_main: {e}", exc_info=True)
        error_output = {
            "status": "error",
            "message": f"Error: {str(e)}"
        }
        print(json.dumps(error_output))
        sys.exit(1)

def main():
    """Synchronous wrapper for async main"""
    asyncio.run(async_main())

if __name__ == "__main__":
    main()

