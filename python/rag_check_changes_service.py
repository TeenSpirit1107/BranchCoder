#!/usr/bin/env python3
"""
RAG Check Changes Service for VS Code Extension
This script checks if any files were modified while VSCode was closed.
Receives workspace directory path via stdin and returns list of changed files.
"""

import json
import sys
import asyncio
from pathlib import Path

from utils.logger import Logger
from rag.hash import get_changed_files, check_indices_exist

# Initialize logger
logger = Logger('rag_check_changes_service', log_to_file=False)

async def check_changes(workspace_dir: str) -> dict:
    """
    Check if any files were changed while VSCode was closed.
    
    Args:
        workspace_dir: Path to the workspace directory
    
    Returns:
        Dictionary with status and changed files:
        {
            "status": "success",
            "has_changes": True/False,
            "changed_files": list of changed file paths,
            "added_files": list of newly added file paths,
            "deleted_files": list of deleted file paths,
        }
    """
    try:
        logger.info(f"Checking for file changes in workspace: {workspace_dir}")
        
        # Check if indices exist - if not, there's nothing to check
        if not check_indices_exist(workspace_dir):
            logger.info("No indices exist, skipping change check")
            return {
                "status": "success",
                "has_changes": False,
                "changed_files": [],
                "added_files": [],
                "deleted_files": [],
            }
        
        # Get changed files using hash comparison
        changes = get_changed_files(workspace_dir)
        changed_files = changes.get("changed", [])
        added_files = changes.get("added", [])
        deleted_files = changes.get("deleted", [])
        
        has_changes = len(changed_files) > 0 or len(added_files) > 0 or len(deleted_files) > 0
        
        logger.info(f"Change check completed: {len(changed_files)} changed, {len(added_files)} added, {len(deleted_files)} deleted")
        
        return {
            "status": "success",
            "has_changes": has_changes,
            "changed_files": changed_files,
            "added_files": added_files,
            "deleted_files": deleted_files,
        }
            
    except Exception as e:
        logger.error(f"Error checking file changes: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to check file changes: {str(e)}",
            "has_changes": False,
            "changed_files": [],
            "added_files": [],
            "deleted_files": [],
        }

async def async_main():
    """Async main entry point - reads workspace path from stdin, checks changes, writes to stdout"""
    try:
        logger.info("RAG check changes service started, waiting for input...")
        
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
        
        logger.info(f"Checking changes for workspace: {workspace_dir}")
        
        # Check for changes
        result = await check_changes(workspace_dir)
        
        # Return JSON response
        logger.info("Change check completed, sending response to stdout")
        print(json.dumps(result))
        
    except Exception as e:
        logger.error(f"Error in async_main: {e}", exc_info=True)
        error_output = {
            "status": "error",
            "message": f"Error: {str(e)}",
            "has_changes": False,
            "changed_files": [],
            "added_files": [],
            "deleted_files": [],
        }
        print(json.dumps(error_output))
        sys.exit(1)

def main():
    """Synchronous wrapper for async main"""
    asyncio.run(async_main())

if __name__ == "__main__":
    main()

