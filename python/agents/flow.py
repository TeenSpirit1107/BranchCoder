import copy
from typing import Any, Dict, List, Optional
from utils.logger import Logger
from llm.chat_llm import AsyncChatClientWrapper
from tools.tool_factory import get_tool_definitions, set_workspace_dir, execute_tool
from models import ReportEvent, MessageEvent, ToolCallEvent, ToolResultEvent
from agents.memory import Memory
from prompts.flow_prompt import PATCH_FAILURE_REFLECTION_PROMPT

logger = Logger('flow', log_to_file=False)


class FlowAgent:
    MAX_ITERATION = 10
    PARALLEL_TOOL_NAME = "execute_parallel_tasks"
    PATCH_TOOL_NAME = "apply_patch"
    MAX_PATCH_FAILURES = 5

    def __init__(self, workspace_dir: str, is_parent: bool = True):
        self.llm_client = AsyncChatClientWrapper()
        logger.info("LLM client initialized successfully")
        self.is_parent = is_parent
        self.tools_definitions = get_tool_definitions(is_parent=is_parent)
        self.workspace_dir = workspace_dir
        set_workspace_dir(workspace_dir)
        self.memory = Memory(workspace_dir)
        self.consecutive_patch_failures = 0
        logger.info(f"Flow agent initialized with {len(self.tools_definitions)} tools, is_parent={is_parent}")
    
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
        
        # Reset patch failure counter for new user message
        self.consecutive_patch_failures = 0
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
                    # Check if this agent is allowed to create sub-agents
                    if not self.is_parent:
                        error_msg = "⚠️ This agent is not allowed to create sub-agents. Only parent agents can use execute_parallel_tasks."
                        logger.warning(f"Blocked parallel task execution: agent is not a parent (session: {session_id})")
                        yield MessageEvent(message=error_msg)
                        self.memory.add_tool_call(session_id, iteration, tool_name, tool_args)
                        self.memory.add_tool_result(session_id, iteration, {"success": False, "error": error_msg})
                        continue
                    
                    # TODO(Yimeng): fix redundant deepcopy (shouldn't have copied when init)
                    context_messages = copy.deepcopy(self.memory.get_messages())
                    tool_args.setdefault("context_messages", context_messages)
                    tool_args.setdefault("parent_session_id", session_id)

                logger.info(f"Tool call: {tool_name} with args: {tool_args}")

                is_report = False
                
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
                        is_report = True
                        yield event
                    # TODO(Yimeng): fix looping logic
                    if tool_result is None:
                        tool_result = {"error": "Tool execution returned no result"}

                    self.memory.add_tool_call(session_id, iteration, tool_name, tool_args)
                    self.memory.add_tool_result(session_id, iteration, tool_result)
                
                # Track patch tool failures
                if tool_name == self.PATCH_TOOL_NAME:
                    is_patch_failed = (
                        tool_result is not None and 
                        (isinstance(tool_result, dict) and 
                         (tool_result.get("success") is False or 
                          "error" in tool_result or 
                          tool_result.get("status") == "failed"))
                    )
                    
                    if is_patch_failed:
                        self.consecutive_patch_failures += 1
                        logger.warning(f"Patch tool failed. Consecutive failures: {self.consecutive_patch_failures}/{self.MAX_PATCH_FAILURES}")
                        
                        if self.consecutive_patch_failures >= self.MAX_PATCH_FAILURES:
                            logger.error(f"Reached max consecutive patch failures ({self.MAX_PATCH_FAILURES}). Triggering reflection.")
                            reflection_message = PATCH_FAILURE_REFLECTION_PROMPT.format(
                                failure_count=self.MAX_PATCH_FAILURES
                            )
                            self.memory.messages.append({
                                "role": "user",
                                "content": reflection_message
                            })
                            self.consecutive_patch_failures = 0  # Reset counter
                            yield MessageEvent(message=reflection_message)
                    else:
                        # Patch succeeded, reset counter
                        if self.consecutive_patch_failures > 0:
                            logger.info(f"Patch tool succeeded. Resetting failure counter from {self.consecutive_patch_failures} to 0.")
                        self.consecutive_patch_failures = 0
                
                if is_report:
                    return
            else:
                answer_text = result.get("answer", "") or ""
                if answer_text:
                    self.memory.add_assistant_message(session_id, answer_text)
                yield MessageEvent(message=answer_text)
                return

        logger.warning(f"Reached max iterations ({self.MAX_ITERATION}), returning error message")
        error_message = "Sorry. Hit max iterations limit"
        yield ReportEvent(message=error_message)
