#!/usr/bin/env python3
"""
AI Service for VS Code Extension
This script receives messages via stdin and returns AI responses via stdout.
Acts as a simple entry point that receives frontend messages, combines them with history,
and delegates to the flow module for processing.
Logs are written to stderr to avoid interfering with JSON output on stdout.
"""

import json
import sys
import asyncio
from typing import List, Dict
from utils.logger import Logger
from utils.conversation_history import ConversationHistory
from flow.flow_agent import FlowAgent

# Initialize logger (logs to stderr by default, no file logging)
# To enable file logging, set log_to_file=True
logger = Logger('ai_service', log_to_file=False)

# Initialize conversation history manager
history_manager = ConversationHistory()
logger.info("Conversation history manager initialized")

# Initialize flow agent
try:
    flow_agent = FlowAgent()
    logger.info("Flow agent initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize flow agent: {e}", exc_info=True)
    flow_agent = None

async def get_ai_response(message: str, session_id: str = "default", workspace_dir: str = None) -> str:
    """
    Process the user message by combining it with history and delegating to flow agent.
    
    Args:
        message: The current user message
        session_id: Session identifier for conversation history (default: "default")
        workspace_dir: Optional workspace directory (used for RAG tool initialization and system prompt)
    
    Returns:
        The AI response string
    """
    logger.debug(f"Processing AI request - message length: {len(message)}, session: {session_id}")
    
    if not flow_agent:
        raise RuntimeError("Flow agent is not initialized")
    
    try:
        logger.info(f"Processing message: {message[:50]}{'...' if len(message) > 50 else ''}")
        
        # Get conversation history from internal storage
        history = history_manager.get_history(session_id)
        
        # Build messages list: history + current message (no system prompt here)
        messages = [
            *history,
            {"role": "user", "content": message}
        ]
        
        # Delegate to flow agent for processing
        response = await flow_agent.process(messages=messages, workspace_dir=workspace_dir)
        
        # Save user message and assistant response to history
        history_manager.add_message("user", message, session_id)
        history_manager.add_message("assistant", response, session_id)
        
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
        session_id = data.get("session_id", "default")  # Optional session ID
        workspace_dir = data.get("workspace_dir", None)  # Optional workspace directory
        
        if not message:
            logger.error("No message provided in input data")
            raise ValueError("No message provided")
        
        logger.info(f"Processing request with message length: {len(message)}, session: {session_id}")
        
        # Get AI response (async) - history is managed internally
        response = await get_ai_response(message, session_id, workspace_dir)
        
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

