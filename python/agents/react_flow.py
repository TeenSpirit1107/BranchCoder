import copy
from typing import Any, Dict, List, Optional
from utils.logger import Logger
from llm.chat_llm import AsyncChatClientWrapper
from tools.tool_factory import get_tool_definitions, set_workspace_dir, execute_tool
from models import ReportEvent, MessageEvent, ToolCallEvent, ToolResultEvent, BaseFlow
from agents.memory import Memory
from prompts.flow_prompt import SEARCH_REPLACE_FAILURE_REFLECTION_PROMPT

logger = Logger('flow', log_to_file=False)


class ReActFlow(BaseFlow):
    MAX_ITERATION = 30
    PARALLEL_TOOL_NAME = "execute_parallel_tasks"
    SEARCH_REPLACE_TOOL_NAME = "search_replace"
    LINTER_TOOL_NAME = "lint_code"
    MAX_SEARCH_REPLACE_FAILURES = 5

    def __init__(self, workspace_dir: str, is_parent: bool = True):
        self.llm_client = AsyncChatClientWrapper()
        logger.info("LLM client initialized successfully")
        self.is_parent = is_parent
        self.tools_definitions = get_tool_definitions(is_parent=is_parent)
        self.workspace_dir = workspace_dir
        set_workspace_dir(workspace_dir)
        self.memory = Memory(workspace_dir, is_parent=is_parent)
        self.consecutive_search_replace_failures = 0
        # Track recent search_replace results for child agents (last 2 attempts)
        self.recent_search_replace_results: List[bool] = []
        logger.info(f"Flow agent initialized with {len(self.tools_definitions)} tools, is_parent={is_parent}")
    
    def _validate_search_replace_linter_sequence(self) -> bool:
        """
        Validate that if search_replace tool was used, linter tool was run successfully after the last search_replace.
        
        Returns:
            True if validation passes (no search_replace calls or linter ran successfully after last search_replace)
            False if validation fails (search_replace exists but no successful linter after last search_replace)
        """
        messages = self.memory.get_messages()
        
        last_search_replace_index = -1
        last_linter_index = -1
        last_linter_result = None
        
        # Find the last search_replace tool call and last linter tool call
        for i, msg in enumerate(messages):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                tool_calls = msg.get("tool_calls", [])
                for tool_call in tool_calls:
                    function_name = tool_call.get("function", {}).get("name", "")
                    if function_name == self.SEARCH_REPLACE_TOOL_NAME:
                        last_search_replace_index = i
                    elif function_name == self.LINTER_TOOL_NAME:
                        last_linter_index = i
                        # Get the result of this linter call (should be in the next tool message)
                        if i + 1 < len(messages) and messages[i + 1].get("role") == "tool":
                            import json
                            try:
                                last_linter_result = json.loads(messages[i + 1].get("content", "{}"))
                            except:
                                last_linter_result = None
        
        # If no search_replace tool was used, validation passes
        if last_search_replace_index == -1:
            logger.debug("No search_replace tool calls found, validation passes")
            return True
        
        # If search_replace was used but no linter was run after it, validation fails
        if last_linter_index <= last_search_replace_index:
            logger.warning(f"Search_replace tool used at index {last_search_replace_index}, but no linter call after it (last linter at {last_linter_index})")
            return False
        
        # Check if the last linter call was successful
        if last_linter_result is None:
            logger.warning("Last linter result is None")
            return False
        
        # Check if linter tool itself failed to execute
        if last_linter_result.get("success") is False or "error" in last_linter_result:
            logger.warning(f"Linter tool execution failed: {last_linter_result}")
            return False
        
        # Check if linter found any syntax errors in the code
        error_count = last_linter_result.get("error_count", 0)
        if error_count > 0:
            logger.warning(f"Linter found {error_count} error(s) in the code")
            return False
        
        logger.info("Search_replace-linter sequence validation passed: no syntax errors found")
        return True
    
    async def process(
        self,
        message: str,
        session_id: str,
        parent_history: Optional[List[Dict[str, Any]]] = None,
        parent_information: Optional[str] = None,
    ):
        logger.debug(f"Processing new message for session {session_id}: {message[:80]}{'...' if len(message) > 80 else ''}")
        if parent_history is None and parent_information is None:
            self.memory.add_user_message(session_id, message)
            await self.memory.initialize_messages(session_id)
        elif parent_information is not None:
            # Child agent: use parent_information and task in system prompt
            self.memory.add_user_message(session_id, message)
            await self.memory.initialize_messages(session_id, parent_information=parent_information, task=message)
        else:
            # Legacy support: if parent_history is provided, use it
            self.memory.messages = copy.deepcopy(parent_history)
            self.memory.messages.append({"role": "user", "content": message})
            self.memory.add_user_message(session_id, message)
        
        # Reset search_replace failure counter for new user message
        self.consecutive_search_replace_failures = 0
        self.recent_search_replace_results = []
        iteration = 0
        while iteration < self.MAX_ITERATION:
            iteration += 1
            logger.debug(f"Flow iteration {iteration}")
            event = MessageEvent(message=f"Thinking... (Iteration: {iteration})")
            event.is_parent = self.is_parent
            yield event
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
                        event = MessageEvent(message=error_msg)
                        event.is_parent = self.is_parent
                        yield event
                        self.memory.add_tool_call(session_id, iteration, tool_name, tool_args)
                        self.memory.add_tool_result(session_id, iteration, {"success": False, "error": error_msg})
                        continue
                    
                    # Extract parent_information from tool_args (should be provided by LLM)
                    # If not provided, generate a summary from current context
                    parent_information = tool_args.get("parent_information")
                    if not parent_information:
                        # Fallback: create a summary from recent messages
                        messages = self.memory.get_messages()
                        # Extract key information from recent assistant and tool messages
                        recent_context = []
                        for msg in messages[-10:]:  # Last 10 messages
                            if msg.get("role") == "assistant" and msg.get("content"):
                                recent_context.append(f"Assistant: {msg['content'][:200]}")
                            elif msg.get("role") == "tool" and msg.get("content"):
                                try:
                                    import json
                                    tool_result = json.loads(msg.get("content", "{}"))
                                    if tool_result.get("success") and tool_result.get("result"):
                                        recent_context.append(f"Tool result: {str(tool_result.get('result'))[:200]}")
                                except:
                                    pass
                        parent_information = "\n".join(recent_context) if recent_context else "No specific context available."
                        logger.warning("parent_information not provided, using fallback summary")
                    
                    tool_args.setdefault("parent_information", parent_information)
                    tool_args.setdefault("parent_session_id", session_id)
                    tool_args.setdefault("parent_flow_type", "react")

                logger.info(f"Tool call: {tool_name} with args: {tool_args}")

                is_report = False
                
                tool_result = None
                async for event in execute_tool(ToolCallEvent(
                    message=f"Calling {tool_name}",
                    tool_name=tool_name,
                    tool_args=tool_args,
                )):
                    # Set agent information for parent agent if not already set
                    if event.is_parent is None:
                        event.is_parent = self.is_parent
                    if event.is_parent and event.agent_index is None:
                        event.agent_index = None  # Parent agent has no index
                    
                    if isinstance(event, MessageEvent):
                        yield event
                    elif isinstance(event, ToolCallEvent):
                        yield event
                    elif isinstance(event, ToolResultEvent):
                        yield event
                        tool_result = event.result
                    elif isinstance(event, ReportEvent):
                        # Only treat as parent's report if is_parent is True or None (not False)
                        # Child agents' reports (is_parent=False) should not cause parent to exit
                        if event.is_parent is not False:
                            is_report = True
                        yield event
                
                # Check if tool execution returned a result (after loop completes)
                if tool_result is None:
                    tool_result = {"error": "Tool execution returned no result"}
                
                # Add tool call and result to memory (only once, after loop completes)
                self.memory.add_tool_call(session_id, iteration, tool_name, tool_args)
                self.memory.add_tool_result(session_id, iteration, tool_result)
                
                if is_report:
                    return
                
                # Track search_replace tool failures
                if tool_name == self.SEARCH_REPLACE_TOOL_NAME:
                    is_search_replace_failed = (
                        tool_result is not None and 
                        (isinstance(tool_result, dict) and 
                         (tool_result.get("success") is False or 
                          "error" in tool_result or 
                          tool_result.get("status") == "failed"))
                    )
                    
                    # Track recent results (keep last 2 for child agents)
                    self.recent_search_replace_results.append(not is_search_replace_failed)  # True for success, False for failure
                    if len(self.recent_search_replace_results) > 2:
                        self.recent_search_replace_results.pop(0)
                    
                    if is_search_replace_failed:
                        self.consecutive_search_replace_failures += 1
                        logger.warning(f"Search_replace tool failed. Consecutive failures: {self.consecutive_search_replace_failures}/{self.MAX_SEARCH_REPLACE_FAILURES}")
                        
                        # Check if failure is due to function not found (anchor not found)
                        error_msg = tool_result.get("error", "") if isinstance(tool_result, dict) else ""
                        is_anchor_not_found = (
                            "anchor not found" in error_msg.lower() or 
                            ("not found" in error_msg.lower() and ("start line" in error_msg.lower() or "end line" in error_msg.lower()))
                        )
                        
                        if is_anchor_not_found:
                            file_path = tool_args.get("file_path", "")
                            new_string = tool_args.get("new_string", "")
                            logger.info(f"Search_replace failed because function/block not found. Suggesting to re-read file and reconsider approach.")
                            suggestion_message = (
                                f"⚠️ search_replace failed: Could not find the function/code block to modify.\n\n"
                                f"Please follow these steps:\n"
                                f"1. First, use `cat {file_path}` to re-read the file and see its current actual content\n"
                                f"2. Based on the file's actual content, decide on a strategy:\n"
                                f"   - Option (1): If the function exists but the content is slightly different, adjust the start_line_content and end_line_content in search_replace to match the actual code in the current file\n"
                                f"   - Option (2): If the function truly doesn't exist, use append to add new code:\n"
                                f"     * Use `execute_command` with `echo '...' >> {file_path}` to append single-line content\n"
                                f"     * Or use `execute_command` with a here-document to append multi-line content\n"
                                f"3. The content you wanted to add/modify is:\n{new_string[:500]}{'...' if len(new_string) > 500 else ''}\n\n"
                                f"Please re-read the file first, then choose the appropriate approach based on the actual situation."
                            )
                            self.memory.messages.append({
                                "role": "user",
                                "content": suggestion_message
                            })
                            event = MessageEvent(message="💡 search_replace failed - target not found. Please re-read the file first, then decide whether to adjust parameters or use append.")
                            event.is_parent = self.is_parent
                            yield event
                            # Continue to next iteration to let LLM re-read file and decide
                            continue
                        
                        # For child agents: trigger reflection if last 2 attempts both failed
                        if not self.is_parent and len(self.recent_search_replace_results) >= 2:
                            last_two_failed = not self.recent_search_replace_results[-1] and not self.recent_search_replace_results[-2]
                            if last_two_failed:
                                logger.warning(f"Child agent: Last 2 search_replace attempts failed. Triggering reflection to fix approach.")
                                reflection_message = SEARCH_REPLACE_FAILURE_REFLECTION_PROMPT.format(
                                    failure_count=2,
                                    workspace_dir=self.workspace_dir
                                )
                                # Add a more specific prompt for child agents
                                child_reflection_prompt = (
                                    f"⚠️ CRITICAL: Your last 2 search_replace attempts on this file have failed. "
                                    f"You need to stop and think about why they failed before trying again.\n\n"
                                    f"{reflection_message}\n\n"
                                    f"Please analyze the error messages from the failed attempts, re-read the file to see its current state, "
                                    f"and develop a better strategy before attempting another search_replace."
                                )
                                self.memory.messages.append({
                                    "role": "user",
                                    "content": child_reflection_prompt
                                })
                                event = MessageEvent(message="🤔 Reflecting on search_replace failures... Analyzing the issue to develop a better approach.")
                                event.is_parent = self.is_parent
                                yield event
                                # Continue to next iteration to let LLM think and respond
                                continue
                        
                        if self.consecutive_search_replace_failures >= self.MAX_SEARCH_REPLACE_FAILURES:
                            logger.error(f"Reached max consecutive search_replace failures ({self.MAX_SEARCH_REPLACE_FAILURES}). Triggering reflection.")
                            reflection_message = SEARCH_REPLACE_FAILURE_REFLECTION_PROMPT.format(
                                failure_count=self.MAX_SEARCH_REPLACE_FAILURES,
                                workspace_dir=self.workspace_dir
                            )
                            self.memory.messages.append({
                                "role": "user",
                                "content": reflection_message
                            })
                            self.consecutive_search_replace_failures = 0
                            event = MessageEvent(message=reflection_message)
                            event.is_parent = self.is_parent
                            yield event
                            # Continue iteration after reflection
                            continue
                    else:
                        # Search_replace succeeded
                        if self.consecutive_search_replace_failures > 0:
                            logger.info(f"Search_replace tool succeeded. Resetting failure counter from {self.consecutive_search_replace_failures} to 0.")
                        self.consecutive_search_replace_failures = 0
            else:
                # LLM returned text response without tool calls
                answer_text = result.get("answer", "") or ""
                if answer_text:
                    # According to the prompt, LLM should use send_message tool for messages
                    # But handle gracefully if it doesn't
                    logger.warning(f"LLM returned text response without calling send_message tool: {answer_text[:100]}")
                    self.memory.add_assistant_message(session_id, answer_text)
                    event = MessageEvent(message=answer_text)
                    event.is_parent = self.is_parent
                    yield event
                return

        logger.warning(f"Reached max iterations ({self.MAX_ITERATION}), returning error message")
        error_message = "Sorry. Hit max iterations limit"
        event = ReportEvent(message=error_message)
        event.is_parent = self.is_parent
        yield event


# Backward compatibility alias
FlowAgent = ReActFlow
