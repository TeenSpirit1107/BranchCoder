#!/usr/bin/env python3
"""
RAG Initialization Service for VS Code Extension
This script initializes the RAG service with the current workspace directory.
Receives workspace directory path via stdin and initializes RAG indexing.
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
logger = Logger('rag_init_service', log_to_file=False)

async def initialize_rag(workspace_dir: str) -> dict:
    """
    Initialize RAG service with the given workspace directory.
    
    Args:
        workspace_dir: Path to the workspace directory to index
    
    Returns:
        Dictionary with status and message
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
        
        # Run initialization
        result = await rag_service.initiate(workspace_dir=workspace_dir)
        
        if result:
            logger.info("RAG service initialized successfully")
            return {
                "status": "success",
                "message": f"RAG service initialized for workspace: {workspace_dir}"
            }
        else:
            logger.error("RAG service initialization failed")
            return {
                "status": "error",
                "message": "RAG service initialization returned False"
            }
            
    except Exception as e:
        logger.error(f"Error initializing RAG service: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to initialize RAG service: {str(e)}"
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

