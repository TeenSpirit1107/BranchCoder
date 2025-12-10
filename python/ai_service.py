import json
import sys
import asyncio
from typing import Dict, Any, Optional
from dataclasses import asdict
from utils.logger import Logger
from agents.flow import ReActFlow
from agents.planact_flow import PlanActFlow

logger = Logger('ai_service', log_to_file=False)

# Global flow agent (lazy initialization on first request)
flow_agent = None
flow_agent_workspace_dir = None
flow_agent_type = None  # Track current agent type

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

async def ensure_flow_agent(workspace_dir: str, agent_type: str = "react") -> ReActFlow:
    """
    Ensure flow agent is initialized with the specified type.
    
    Args:
        workspace_dir: Workspace directory path
        agent_type: Type of agent to use - "react" or "planact" (default: "react")
        
    Returns:
        Initialized flow agent instance
    """
    global flow_agent, flow_agent_workspace_dir, flow_agent_type
    
    # Reinitialize if workspace or agent type changed
    if flow_agent is None or flow_agent_workspace_dir != workspace_dir or flow_agent_type != agent_type:
        try:
            if agent_type.lower() == "planact":
                flow_agent = PlanActFlow(workspace_dir)
                logger.info(f"PlanActFlow agent initialized for workspace: {workspace_dir}")
            else:  # Default to react
                flow_agent = ReActFlow(workspace_dir)
                logger.info(f"ReActFlow agent initialized for workspace: {workspace_dir}")
            
            flow_agent_workspace_dir = workspace_dir
            flow_agent_type = agent_type
        except Exception as e:
            logger.error(f"Failed to initialize flow agent: {e}", exc_info=True)
            flow_agent = None
            raise RuntimeError(f"Flow agent initialization failed: {e}")
    
    if flow_agent is None:
        raise RuntimeError("Flow agent is not initialized")
    
    return flow_agent


async def get_ai_response(
    message: str, 
    session_id: str = "default", 
    workspace_dir: str = None,
    agent_type: str = "react"
):
    """
    Process the user message by delegating to FlowAgent, which owns the conversation context.
    This is an async generator that yields streamed messages.
    
    Args:
        message: The current user message
        session_id: Session identifier for conversation history (default: "default")
        workspace_dir: Optional workspace directory (used for RAG tool initialization and system prompt)
        agent_type: Type of agent to use - "react" or "planact" (default: "react")
    
    Yields:
        Dict with message type and content for streaming to frontend
    """
    logger.debug(f"Processing AI request - message length: {len(message)}, session: {session_id}, agent_type: {agent_type}")
    
    if not workspace_dir:
        raise ValueError("workspace_dir is required for FlowAgent initialization")

    agent = await ensure_flow_agent(workspace_dir, agent_type)

    try:
        logger.info(f"Processing message: {message[:50]}{'...' if len(message) > 50 else ''}")
        
        # Delegate to flow agent for processing (async generator)
        async for msg in agent.process(message=message, session_id=session_id):
            msg_dict = _message_to_dict(msg)
            yield msg_dict

    except Exception as e:
        logger.error(f"Error in get_ai_response: {e}", exc_info=True)
        yield {"type": "final_message", "message": f"错误: {str(e)}"}
        raise


async def get_session_history(session_id: str, workspace_dir: str, agent_type: str = "react"):
    """
    Get session history from the flow agent.
    
    Args:
        session_id: Session identifier
        workspace_dir: Workspace directory path
        agent_type: Type of agent to use - "react" or "planact" (default: "react")
        
    Returns:
        Session history
    """
    if not workspace_dir:
        raise ValueError("workspace_dir is required for FlowAgent initialization")
    agent = await ensure_flow_agent(workspace_dir, agent_type)
    history = agent.memory.get_session_history(session_id)
    return history

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
        request_type = data.get("request_type", "response")
        # DEBUG: Hard-coded to planact for testing until frontend implements agent selection
        agent_type = "planact"  # data.get("agent_type", "react")  # TODO(Yimeng): Uncomment when frontend is ready
        
        if request_type == "response":
            if not message:
                logger.error("No message provided in input data")
                raise ValueError("No message provided")
        
        logger.info(f"Processing request with message length: {len(message)}, session: {session_id}, agent_type: {agent_type}")
        
        if request_type == "response":
            async for msg in get_ai_response(message, session_id, workspace_dir, agent_type):
                output_line = json.dumps(msg, ensure_ascii=False)
                print(output_line, flush=True)
        elif request_type == "history":
            history = await get_session_history(session_id, workspace_dir, agent_type)
            output_line = json.dumps({
                "type": "history",
                "session_id": session_id,
                "history": history
            }, ensure_ascii=False)
            print(output_line, flush=True)
        else:
            raise ValueError(f"Unsupported request_type: {request_type}")
        if request_type == "response":
            logger.info("Response stream completed")
        else:
            logger.info("History request completed")
        
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

