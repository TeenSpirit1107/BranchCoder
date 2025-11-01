#!/usr/bin/env python3
"""
AI Service for VS Code Extension
This script receives messages via stdin and returns AI responses via stdout.
Logs are written to stderr to avoid interfering with JSON output on stdout.
"""

import json
import sys
import asyncio
from typing import List, Dict
from logger import Logger
from llm_client import AsyncChatClientWrapper

# Initialize logger (logs to stderr by default, no file logging)
# To enable file logging, set log_to_file=True
logger = Logger('ai_service', log_to_file=False)

# Initialize LLM client
try:
    llm_client = AsyncChatClientWrapper()
    logger.info("LLM client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize LLM client: {e}", exc_info=True)
    llm_client = None

async def get_ai_response(message: str, history: List[Dict[str, str]]) -> str:
    """
    Process the user message and generate an AI response using LLM client.
    
    Args:
        message: The current user message
        history: List of previous messages in format [{"role": "user|assistant", "content": "..."}]
    
    Returns:
        The AI response string
    """
    logger.debug(f"Processing AI request - message length: {len(message)}, history length: {len(history)}")
    
    if not llm_client:
        raise RuntimeError("LLM client is not initialized")
    
    try:
        logger.info(f"Generating response for message: {message[:50]}{'...' if len(message) > 50 else ''}")
        
        # Build messages list from history and current message
        messages = history.copy()
        messages.append({"role": "user", "content": message})
        
        # Call LLM client
        result = await llm_client.create_completion(
            messages=messages,
            temperature=1.0
        )
        
        # Handle tool calls if needed (for now, just return the answer)
        if result["type"] == "tool_call":
            logger.warning(f"Received tool call: {result['tool_name']}, but tool calls are not yet supported in ai_service")
            response = f"Received tool call request: {result['tool_name']}, but tool execution is not implemented."
        else:
            response = result.get("answer", "") or ""
        
        # Log usage statistics
        usage = result.get("usage", {})
        logger.info(f"Token usage - prompt: {usage.get('prompt_tokens', 0)}, "
                   f"completion: {usage.get('completion_tokens', 0)}, "
                   f"total: {usage.get('total_tokens', 0)}")
        
        logger.debug(f"Generated response length: {len(response)}")
        return response
        
    except Exception as e:
        logger.error(f"Error in get_ai_response: {e}", exc_info=True)
        raise

async def async_main():
    """Async main entry point - reads from stdin, processes, writes to stdout"""
    try:
        logger.info("AI service started, waiting for input...")
        
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
        
        message = data.get("message", "")
        history = data.get("history", [])
        
        if not message:
            logger.error("No message provided in input data")
            raise ValueError("No message provided")
        
        logger.info(f"Processing request with message length: {len(message)}")
        
        # Get AI response (async)
        response = await get_ai_response(message, history)
        
        # Return JSON response
        output = {
            "response": response,
            "status": "success"
        }
        
        logger.info("Response generated successfully, sending to stdout")
        print(json.dumps(output))
        
    except Exception as e:
        logger.error(f"Error in async_main: {e}", exc_info=True)
        error_output = {
            "response": f"Error: {str(e)}",
            "status": "error"
        }
        print(json.dumps(error_output))
        sys.exit(1)

def main():
    """Synchronous wrapper for async main"""
    asyncio.run(async_main())

if __name__ == "__main__":
    main()

