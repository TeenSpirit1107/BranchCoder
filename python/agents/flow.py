import copy
from typing import Any, Dict, List, Optional
from utils.logger import Logger
from llm.chat_llm import AsyncChatClientWrapper
from tools.tool_factory import get_tool_definitions, set_workspace_dir, execute_tool
from models import ReportEvent, MessageEvent, ToolCallEvent, ToolResultEvent
from agents.memory import Memory

logger = Logger('flow', log_to_file=False)


class FlowAgent:
    MAX_ITERATION = 10
    PARALLEL_TOOL_NAME = "execute_parallel_tasks"

    def __init__(self, workspace_dir: str):
        self.llm_client = AsyncChatClientWrapper()
        logger.info("LLM client initialized successfully")
        self.tools_definitions = get_tool_definitions()
        self.workspace_dir = workspace_dir
        set_workspace_dir(workspace_dir)
        self.memory = Memory(workspace_dir)
        logger.info(f"Flow agent initialized with {len(self.tools_definitions)} tools")
    
    async def process(
        self,
        message: str,
        session_id: str,
        parent_history: Optional[List[Dict[str, Any]]] = None,
    ):
        logger.debug(f"Processing new message for session {session_id}: {message[:80]}{'...' if len(message) > 80 else ''}")
        if parent_history is None:
            self.memory.add_user_message(session_id, message)
            await self.memory.initialize_messages(session_id)
        else:
            self.memory.messages = copy.deepcopy(parent_history)
            self.memory.messages.append({"role": "user", "content": message})
            self.memory.add_user_message(session_id, message)
        iteration = 0
        while iteration < self.MAX_ITERATION:
            iteration += 1
            logger.debug(f"Flow iteration {iteration}")
            yield MessageEvent(message=f"Thinking... (Iteration: {iteration})")
            result = await self.llm_client.ask(
                messages=self.memory.get_messages(),
                tools=self.tools_definitions,
            )
            if result["type"] == "tool_call":
                tool_name = result["tool_name"]
                tool_args = dict(result.get("tool_args") or {})

                if tool_name == self.PARALLEL_TOOL_NAME:
                    # TODO(Yimeng): fix redundant deepcopy (shouldn't have copied when init)
                    context_messages = copy.deepcopy(self.memory.get_messages())
                    tool_args.setdefault("context_messages", context_messages)
                    tool_args.setdefault("parent_session_id", session_id)

                logger.info(f"Tool call: {tool_name} with args: {tool_args}")

                tool_result = None
                async for event in execute_tool(ToolCallEvent(
                    message=f"Calling {tool_name}",
                    tool_name=tool_name,
                    tool_args=tool_args,
                )):
                    if isinstance(event, MessageEvent):
                        yield event
                    elif isinstance(event, ToolCallEvent):
                        yield event
                    elif isinstance(event, ToolResultEvent):
                        yield event
                        tool_result = event.result
                    elif isinstance(event, ReportEvent):
                        yield event
                        return

                # TODO(Yimeng): move this into for loop
                if tool_result is None:
                    tool_result = {"error": "Tool execution returned no result"}

                self.memory.add_tool_call(session_id, iteration, tool_name, tool_args)
                self.memory.add_tool_result(session_id, iteration, tool_result)
            else:
                answer_text = result.get("answer", "") or ""
                if answer_text:
                    self.memory.add_assistant_message(session_id, answer_text)
                yield MessageEvent(message=answer_text)
                return

        logger.warning(f"Reached max iterations ({self.MAX_ITERATION}), returning error message")
        error_message = "Sorry. Hit max iterations limit"
        yield ReportEvent(message=error_message)
