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
import time
from pathlib import Path
from dotenv import load_dotenv

from utils.logger import Logger
from llm.chat_llm import AsyncChatClientWrapper
from rag.rag_service import RagService
from rag.hash import (
    get_last_update_time,
    save_last_update_time,
    get_pending_changes,
    save_pending_changes,
    clear_pending_changes,
    verify_and_filter_changes,
)

# Load environment variables from .env file
load_dotenv()

# Get update interval from environment variable (in seconds）
UPDATE_INTERVAL_SECONDS = int(os.getenv("RAG_UPDATE_INTERVAL_SECONDS"))

# Initialize logger
logger = Logger('rag_update_service', log_to_file=False)

async def update_rag(
    workspace_dir: str,
    changed_files: list[str],
    deleted_files: list[str],
) -> dict:
    """
    Update RAG service with changed files for the given workspace directory.
    Checks time interval before updating to avoid too frequent updates.
    
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
        
        # Check if indices exist - if not, initialize first (skip interval check)
        from rag.hash import check_indices_exist
        if not check_indices_exist(workspace_dir):
            logger.info("Indices do not exist, initializing first...")
            
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
            
            await rag_service.initiate(workspace_dir=workspace_dir)
            
            # Clear any pending changes and save update time
            clear_pending_changes(workspace_dir)
            save_last_update_time(workspace_dir)
            
            logger.info("RAG service initialized successfully")
            return {
                "status": "success",
                "message": f"RAG service initialized for workspace: {workspace_dir}"
            }
        
        # Get existing pending changes
        pending = get_pending_changes(workspace_dir)
        existing_pending_changed = pending["changed_files"]
        existing_pending_deleted = pending["deleted_files"]
        
        # Merge new changes with existing pending changes
        all_to_verify_changed = list(set(existing_pending_changed + changed_files))
        all_to_verify_deleted = list(set(existing_pending_deleted + deleted_files))
        
        # If there are any changes (new or existing), verify them against actual file hashes
        if len(all_to_verify_changed) > 0 or len(all_to_verify_deleted) > 0:
            logger.info(f"Verifying {len(all_to_verify_changed)} changed and {len(all_to_verify_deleted)} deleted files against actual file hashes...")
            verified = verify_and_filter_changes(
                workspace_dir,
                all_to_verify_changed,
                all_to_verify_deleted,
            )
            
            verified_changed = verified["changed_files"]
            verified_deleted = verified["deleted_files"]
            
            removed_changed = len(all_to_verify_changed) - len(verified_changed)
            removed_deleted = len(all_to_verify_deleted) - len(verified_deleted)
            
            if removed_changed > 0 or removed_deleted > 0:
                logger.info(f"Filtered out {removed_changed} changed files and {removed_deleted} deleted files (no actual changes)")
            
            # Save verified changes as pending (replace, not merge, to remove filtered files)
            # We need to clear and set, since save_pending_changes merges
            clear_pending_changes(workspace_dir)
            if len(verified_changed) > 0 or len(verified_deleted) > 0:
                save_pending_changes(workspace_dir, verified_changed, verified_deleted)
            # Re-fetch to get the updated list
            pending = get_pending_changes(workspace_dir)
        else:
            # No new changes, but we should still verify existing pending changes
            # to remove any that are no longer valid (e.g., file restored with same hash)
            if len(existing_pending_changed) > 0 or len(existing_pending_deleted) > 0:
                logger.info(f"Verifying existing pending changes: {len(existing_pending_changed)} changed, {len(existing_pending_deleted)} deleted")
                verified = verify_and_filter_changes(
                    workspace_dir,
                    existing_pending_changed,
                    existing_pending_deleted,
                )
                
                verified_changed = verified["changed_files"]
                verified_deleted = verified["deleted_files"]
                
                removed_changed = len(existing_pending_changed) - len(verified_changed)
                removed_deleted = len(existing_pending_deleted) - len(verified_deleted)
                
                if removed_changed > 0 or removed_deleted > 0:
                    logger.info(f"Filtered out {removed_changed} changed files and {removed_deleted} deleted files from existing pending (no actual changes)")
                    # Update pending changes to remove filtered files
                    clear_pending_changes(workspace_dir)
                    if len(verified_changed) > 0 or len(verified_deleted) > 0:
                        save_pending_changes(workspace_dir, verified_changed, verified_deleted)
                    pending = get_pending_changes(workspace_dir)
        
        # Get all pending changes (after verification)
        all_pending_changed = pending["changed_files"]
        all_pending_deleted = pending["deleted_files"]
        total_pending = len(all_pending_changed) + len(all_pending_deleted)
        
        if total_pending == 0:
            logger.info("No pending changes after verification, nothing to update")
            return {
                "status": "success",
                "message": "No pending changes after verification, nothing to update"
            }
        
        logger.info(f"Total pending changes (verified): {len(all_pending_changed)} changed, {len(all_pending_deleted)} deleted")
        
        # Check time interval since last update
        last_update_time = get_last_update_time(workspace_dir)
        current_time = time.time()
        
        should_update = False
        
        if last_update_time is None:
            # No previous update, proceed with update
            logger.info("No previous update time found, proceeding with update")
            should_update = True
        else:
            time_since_last_update = current_time - last_update_time
            logger.info(f"Time since last update: {time_since_last_update:.2f} seconds (interval limit: {UPDATE_INTERVAL_SECONDS} seconds)")
            
            if time_since_last_update >= UPDATE_INTERVAL_SECONDS:
                logger.info("Update interval reached, proceeding with update")
                should_update = True
            else:
                remaining_time = UPDATE_INTERVAL_SECONDS - time_since_last_update
                logger.info(f"Update interval not reached yet, waiting. Remaining time: {remaining_time:.2f} seconds")
                logger.info(f"Changes are accumulated and will be updated when interval is reached")
                return {
                    "status": "success",
                    "message": f"Update queued: {total_pending} files waiting. Will update in {remaining_time:.2f}s"
                }
        
        if not should_update:
            return {
                "status": "success",
                "message": "Update conditions not met"
            }
        
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
        
        # Reload existing indices
        await rag_service.reload(workspace_dir)
        
        # Update all pending changed files
        logger.info(f"Updating all pending changes: {len(all_pending_changed)} changed, {len(all_pending_deleted)} deleted")
        result = await rag_service.update_changed_files(
            workspace_dir=workspace_dir,
            changed_files=all_pending_changed,
            deleted_files=all_pending_deleted,
        )
        
        if result.get("updated", False):
            # Clear pending changes and save update time after successful update
            clear_pending_changes(workspace_dir)
            save_last_update_time(workspace_dir)
            
            logger.info("RAG service updated successfully with all pending changes")
            changed_count = len(result.get("changed_files", []))
            deleted_count = len(result.get("deleted_files", []))
            return {
                "status": "success",
                "message": f"Updated {changed_count} changed files and {deleted_count} deleted files (including accumulated changes)"
            }
        else:
            logger.info("Update completed but no files were actually updated")
            # Still clear pending changes and save time since we attempted the update
            clear_pending_changes(workspace_dir)
            save_last_update_time(workspace_dir)
            return {
                "status": "success",
                "message": "Update completed but no files were actually updated"
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

