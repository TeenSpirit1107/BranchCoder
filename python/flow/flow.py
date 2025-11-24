import json
from datetime import datetime
from typing import List, Dict
from utils.logger import Logger
from llm.chat_llm import AsyncChatClientWrapper
from tools.tool_factory import get_tool_definitions, set_workspace_dir, execute_tool
from model import ToolResultEvent, FinalEvent, NotificationEvent, ToolCallEvent

logger = Logger('flow', log_to_file=False)


class FlowAgent:
    SYSTEM_PROMPT = """
    You are a helpful AI coding assistant integrated into VS Code. 
    Your role is to assist developers with:
    - Writing and debugging code
    - Explaining code functionality
    - Suggesting improvements and best practices
    - Answering programming questions
    - Helping with code refactoring

    You have access to various tools that will be provided to you. Use them when appropriate to help the user. 
    Provide clear, concise, and accurate responses.

    Current Information:
    - Current Time: {current_time}
    - Workspace Directory: {workspace_dir}
    - Workspace File Structure: {workspace_structure}
    """
    MAX_ITERATION = 10

    def __init__(self, workspace_dir: str):
        self.llm_client = AsyncChatClientWrapper()
        logger.info("LLM client initialized successfully")
        self.tools_definitions = get_tool_definitions()
        self.workspace_dir = workspace_dir
        set_workspace_dir(workspace_dir)
        logger.info(f"Flow agent initialized with {len(self.tools_definitions)} tools")
    
    async def generate_system_prompt(self) -> str:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        workspace_structure = ''

        async for event in execute_tool(
            ToolCallEvent(
                message="getting workspace structure",
                tool_name="get_workspace_structure",
                tool_args={
                    "max_depth": 5,
                    "include_files": True,
                    "include_hidden": False
                }
            )
        ):
            if isinstance(event, ToolResultEvent):
                workspace_structure = event.result
        
        return self.SYSTEM_PROMPT.format(current_time=current_time, workspace_dir=self.workspace_dir, workspace_structure=workspace_structure)
    
    async def process(self, messages: List[Dict[str, str]]):
        logger.debug(f"Processing {len(messages)} messages through flow agent")
        system_prompt = await self.generate_system_prompt()
        messages_with_system = [
            {"role": "system", "content": system_prompt},
            *messages
        ]
        iteration = 0
        while iteration < self.MAX_ITERATION:
            iteration += 1
            logger.debug(f"Flow iteration {iteration}")
            yield NotificationEvent(message=f"Thinking... (Iteration: {iteration})")
            result = await self.llm_client.ask(
                messages=messages_with_system,
                tools=self.tools_definitions,
            )
            if result["type"] == "tool_call":
                tool_name = result["tool_name"]
                tool_args = result["tool_args"] or {}
                logger.info(f"Tool call: {tool_name} with args: {tool_args}")

                tool_result = None
                async for event in execute_tool(ToolCallEvent(
                    message=f"Calling {tool_name}",
                    tool_name=tool_name,
                    tool_args=tool_args,
                )):
                    if isinstance(event, NotificationEvent):
                        yield event
                    elif isinstance(event, ToolResultEvent):
                        yield event
                        tool_result = event.result
                    elif isinstance(event, FinalEvent):
                        yield event
                        return

                if tool_result is None:
                    tool_result = {"error": "Tool execution returned no result"}

                messages_with_system.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": f"call_{iteration}",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_args)
                        }
                    }]
                })
                messages_with_system.append({
                    "role": "tool",
                    "content": json.dumps(tool_result),
                    "tool_call_id": f"call_{iteration}"
                })
            else:
                yield NotificationEvent(message=result.get("answer", ""))

        logger.warning(f"Reached max iterations ({self.MAX_ITERATION}), returning error message")
        error_message = "Sorry. Hit max iterations limit"
        yield FinalEvent(message=error_message)
