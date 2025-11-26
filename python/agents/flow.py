from utils.logger import Logger
from llm.chat_llm import AsyncChatClientWrapper
from tools.tool_factory import get_tool_definitions, set_workspace_dir, execute_tool
from models import ReportEvent, MessageEvent, ToolCallEvent, ToolResultEvent
from agents.memory import Memory

logger = Logger('flow', log_to_file=False)


class FlowAgent:
    MAX_ITERATION = 10

    def __init__(self, workspace_dir: str):
        self.llm_client = AsyncChatClientWrapper()
        logger.info("LLM client initialized successfully")
        self.tools_definitions = get_tool_definitions()
        self.workspace_dir = workspace_dir
        set_workspace_dir(workspace_dir)
        self.memory = Memory(workspace_dir)
        logger.info(f"Flow agent initialized with {len(self.tools_definitions)} tools")
    
    async def process(self, message: str, session_id: str):
        logger.debug(f"Processing new message for session {session_id}: {message[:80]}{'...' if len(message) > 80 else ''}")
        self.memory.add_user_message(session_id, message)
        await self.memory.initialize_messages(session_id)
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
                tool_args = result["tool_args"] or {}
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

                if tool_result is None:
                    tool_result = {"error": "Tool execution returned no result"}

                self.memory.add_tool_call(iteration, tool_name, tool_args)
                self.memory.add_tool_result(iteration, tool_result)
            else:
                answer_text = result.get("answer", "") or ""
                if answer_text:
                    self.memory.add_assistant_message(session_id, answer_text)
                yield MessageEvent(message=answer_text)
                return

        logger.warning(f"Reached max iterations ({self.MAX_ITERATION}), returning error message")
        error_message = "Sorry. Hit max iterations limit"
        yield ReportEvent(message=error_message)
