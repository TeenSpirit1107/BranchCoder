#!/usr/bin/env python3
"""
RAG Initialization Service for VS Code Extension
This script initializes the RAG service with the current workspace directory.
It checks if indices exist, builds if not, and updates if there are changes while VSCode was closed.
Receives workspace directory path via stdin and initializes/updates RAG indexing.
"""

import json
import sys
import asyncio

from utils.logger import Logger
from llm.chat_llm import AsyncChatClientWrapper
from rag.rag_service import RagService
from rag.hash import get_changed_files, check_indices_exist

# Initialize logger
logger = Logger('rag_init_service', log_to_file=False)

async def initialize_rag(workspace_dir: str) -> dict:
    """
    Initialize or update RAG service with the given workspace directory.
    
    This function:
    1. Checks if indices exist - if not, builds them
    2. If indices exist, checks for changes while VSCode was closed
    3. Updates if there are changes, otherwise just reloads
    
    Args:
        workspace_dir: Path to the workspace directory to index
    
    Returns:
        Dictionary with status, message, and operation details
    """
    try:
        logger.info(f"Initializing RAG service for workspace: {workspace_dir}")
        
        # Initialize LLM client
        llm_client = AsyncChatClientWrapper()
        logger.info("LLM client initialized successfully")
        
        # Initialize RAG service
        rag_service = RagService(
            llm=llm_client,
            enable_rerank=True,
            rerank_top_n=10,
            initial_candidates=30,
        )
        
        # Check if indices exist
        indices_exist = check_indices_exist(workspace_dir)
        
        if not indices_exist:
            # No indices exist, build them
            logger.info("No indices exist, building new indices")
            result = await rag_service.initiate(workspace_dir=workspace_dir)
            
            if result:
                logger.info("RAG service initialized successfully")
                return {
                    "status": "success",
                    "message": f"RAG service initialized for workspace: {workspace_dir}",
                    "operation": "build",
                    "has_changes": False,
                    "updated": False,
                }
            else:
                logger.error("RAG service initialization failed")
                return {
                    "status": "error",
                    "message": "RAG service initialization returned False",
                    "operation": "build",
                    "has_changes": False,
                    "updated": False,
                }
        else:
            # Indices exist, reload first
            logger.info("Indices exist, reloading RAG service")
            await rag_service.reload(workspace_dir)
            
            # Check for changes while VSCode was closed
            logger.info("Checking for file changes while VSCode was closed")
            changes = get_changed_files(workspace_dir)
            changed_files = changes.get("changed", [])
            added_files = changes.get("added", [])
            deleted_files = changes.get("deleted", [])
            
            has_changes = len(changed_files) > 0 or len(added_files) > 0 or len(deleted_files) > 0
            
            if has_changes:
                # There are changes, update the indices
                logger.info(
                    f"Found changes while VSCode was closed: "
                    f"{len(changed_files)} changed, {len(added_files)} added, {len(deleted_files)} deleted"
                )
                
                # Combine changed and added files as they both need updating
                all_changed_files = list(set(changed_files + added_files))
                
                update_result = await rag_service.update(
                    workspace_dir=workspace_dir,
                    changed_files=all_changed_files,
                    deleted_files=deleted_files,
                )
                
                if update_result.get("updated", False):
                    logger.info("RAG service updated successfully with changes")
                    return {
                        "status": "success",
                        "message": f"RAG service reloaded and updated: {len(changed_files)} changed, {len(added_files)} added, {len(deleted_files)} deleted",
                        "operation": "reload_and_update",
                        "has_changes": True,
                        "updated": True,
                        "changed_files": changed_files,
                        "added_files": added_files,
                        "deleted_files": deleted_files,
                    }
                else:
                    logger.info("Update completed but no files were actually updated")
                    return {
                        "status": "success",
                        "message": f"RAG service reloaded. Found changes but update returned no changes: {len(changed_files)} changed, {len(added_files)} added, {len(deleted_files)} deleted",
                        "operation": "reload_and_update",
                        "has_changes": True,
                        "updated": False,
                        "changed_files": changed_files,
                        "added_files": added_files,
                        "deleted_files": deleted_files,
                    }
            else:
                # No changes, just reloaded
                logger.info("No changes found while VSCode was closed, RAG service reloaded")
                return {
                    "status": "success",
                    "message": f"RAG service reloaded. No changes detected.",
                    "operation": "reload",
                    "has_changes": False,
                    "updated": False,
                    "changed_files": [],
                    "added_files": [],
                    "deleted_files": [],
                }
            
    except Exception as e:
        logger.error(f"Error initializing RAG service: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to initialize RAG service: {str(e)}",
            "operation": "unknown",
            "has_changes": False,
            "updated": False,
        }

async def async_main():
    """Async main entry point - reads workspace path from stdin, initializes RAG, writes to stdout"""
    try:
        logger.info("RAG init service started, waiting for input...")
        
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
        
        if not workspace_dir:
            logger.error("No workspace_dir provided in input data")
            raise ValueError("No workspace_dir provided")
        
        logger.info(f"Initializing RAG for workspace: {workspace_dir}")
        
        # Initialize RAG service
        result = await initialize_rag(workspace_dir)
        
        # Return JSON response
        logger.info("RAG initialization completed, sending response to stdout")
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

