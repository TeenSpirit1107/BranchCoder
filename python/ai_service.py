import json
import sys
import asyncio
from typing import Dict, Any
from dataclasses import asdict
from utils.logger import Logger
from utils.conversation_history import ConversationHistory
from agents.flow import FlowAgent

logger = Logger('ai_service', log_to_file=False)

# Initialize conversation history manager
history_manager = ConversationHistory()
logger.info("Conversation history manager initialized")

# Global flow agent (lazy initialization on first request)
flow_agent = None
flow_agent_workspace_dir = None

def _message_to_dict(message: Any) -> Dict[str, Any]:
    """
    Convert message to dictionary format for JSON serialization.
    Handles both dict and model instances (dataclasses with to_dict() or asdict).
    
    Args:
        message: Message dict or model instance
    
    Returns:
        Dictionary representation of the message
    """
    if isinstance(message, dict):
        return message
    elif hasattr(message, 'to_dict'):
        return message.to_dict()
    else:
        # Try asdict for dataclass instances
        try:
            return asdict(message)
        except (TypeError, ValueError):
            # Fallback: try to convert to dict
            return dict(message) if hasattr(message, '__dict__') else {"type": "unknown", "content": str(message)}

async def get_ai_response(message: str, session_id: str = "default", workspace_dir: str = None):
    """
    Process the user message by combining it with history and delegating to flow agent.
    This is an async generator that yields streamed messages.
    
    Args:
        message: The current user message
        session_id: Session identifier for conversation history (default: "default")
        workspace_dir: Optional workspace directory (used for RAG tool initialization and system prompt)
    
    Yields:
        Dict with message type and content for streaming to frontend
    """
    logger.debug(f"Processing AI request - message length: {len(message)}, session: {session_id}")
    
    if not workspace_dir:
        raise ValueError("workspace_dir is required for FlowAgent initialization")
    
    global flow_agent, flow_agent_workspace_dir
    
    # Lazy initialization: create FlowAgent on first request or if workspace_dir changed
    if flow_agent is None or flow_agent_workspace_dir != workspace_dir:
        try:
            flow_agent = FlowAgent(workspace_dir)
            flow_agent_workspace_dir = workspace_dir
            logger.info(f"Flow agent initialized successfully for workspace: {workspace_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize flow agent: {e}", exc_info=True)
            raise RuntimeError(f"Flow agent initialization failed: {e}")
    
    if flow_agent is None:
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
        
        # Track final message for history
        final_message = None
        
        # Delegate to flow agent for processing (async generator)
        async for msg in flow_agent.process(messages=messages):
            # Convert message to dict for JSON serialization
            msg_dict = _message_to_dict(msg)
            # Yield message to frontend
            yield msg_dict
            
            # Track final message
            if msg_dict.get("type") == "final_message":
                final_message = msg_dict.get("message", "")
        
        # Save user message and assistant response to history
        history_manager.add_message("user", message, session_id)
        if final_message:
            history_manager.add_message("assistant", final_message, session_id)
            logger.debug(f"Generated response length: {len(final_message)}")
        
    except Exception as e:
        logger.error(f"Error in get_ai_response: {e}", exc_info=True)
        # Yield error message
        yield {"type": "final_message", "message": f"错误: {str(e)}"}
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
        
        # Get AI response (async generator) - stream messages to frontend
        # Each message is sent as a JSON line (for streaming)
        async for msg in get_ai_response(message, session_id, workspace_dir):
            # msg is already a dict from get_ai_response (converted via _message_to_dict)
            # Send each message as a JSON line to stdout
            # Frontend will read line by line
            output_line = json.dumps(msg, ensure_ascii=False)
            print(output_line, flush=True)
        
        logger.info("Response stream completed")
        
    except Exception as e:
        logger.error(f"Error in async_main: {e}", exc_info=True)
        # Send error as streaming message
        error_msg = {"type": "final_message", "message": f"错误: {str(e)}"}
        print(json.dumps(error_msg, ensure_ascii=False), flush=True)
        sys.exit(1)

def main():
    """Synchronous wrapper for async main"""
    asyncio.run(async_main())

if __name__ == "__main__":
    main()

