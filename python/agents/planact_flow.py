import copy
from typing import Any, Dict, List, Optional
from utils.logger import Logger
from llm.chat_llm import AsyncChatClientWrapper
from tools.tool_factory import get_tool_definitions, set_workspace_dir, execute_tool
from models import ReportEvent, MessageEvent, ToolCallEvent, ToolResultEvent, BaseFlow
from agents.memory import Memory
from prompts.flow_prompt import (
    SEARCH_REPLACE_FAILURE_REFLECTION_PROMPT,
    PLANNING_PROMPT,
    PLAN_REVISION_PROMPT
)

logger = Logger('planact_flow', log_to_file=False)


class PlanActFlow(BaseFlow):
    """
    Plan-Act Flow: A two-phase agent that first creates a plan, then executes it.
    
    Phase 1 (Planning): LLM generates a structured plan with steps
    Phase 2 (Acting): Execute each step, potentially revising the plan based on results
    """
    
    MAX_ITERATION = 40 # Higher limit since planning adds overhead
    MAX_PLANNING_ITERATIONS = 3  # Max times to revise the plan
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
        self.current_plan = None
        self.plan_revision_count = 0
        logger.info(f"PlanAct Flow agent initialized with {len(self.tools_definitions)} tools, is_parent={is_parent}")
    
    async def _generate_plan(self, session_id: str):
        """
        Generate an execution plan by asking the LLM to think through the steps.
        Sets self.current_plan if successful.
        
        Yields:
            MessageEvent for progress updates
        """
        logger.info(f"Generating execution plan for session {session_id}")
        
        # Add planning prompt to messages
        planning_messages = copy.deepcopy(self.memory.get_messages())
        planning_messages.append({
            "role": "user",
            "content": PLANNING_PROMPT
        })
        
        yield MessageEvent(message="📋 Creating execution plan...")
        
        # Ask LLM to generate plan (without tools, just text response)
        result = await self.llm_client.ask(
            messages=planning_messages,
            tools=None,  # No tools during planning phase
        )
        
        # Check if LLM returned a text/answer response (not a tool call)
        if result.get("type") in ["text", "answer"]:
            plan = result.get("answer", "")
            if plan and "EXECUTION PLAN" in plan.upper():
                logger.info(f"Plan generated successfully:\n{plan}")
                self.current_plan = plan
                # Add the plan to memory
                self.memory.messages.append({
                    "role": "assistant",
                    "content": plan
                })
                yield MessageEvent(message=f"📋 Plan created:\n{plan}")
                return  # Plan stored in self.current_plan
        
        logger.warning("Failed to generate a valid plan, proceeding without explicit plan")
        self.current_plan = None
    
    async def _revise_plan(self, session_id: str, reason: str):
        """
        Revise the current plan based on execution results.
        Updates self.current_plan if successful.
        
        Args:
            session_id: Current session ID
            reason: Reason for plan revision (e.g., tool failure, unexpected result)
            
        Yields:
            MessageEvent for progress updates
        """
        if self.plan_revision_count >= self.MAX_PLANNING_ITERATIONS:
            logger.warning(f"Max plan revisions ({self.MAX_PLANNING_ITERATIONS}) reached")
            return
        
        self.plan_revision_count += 1
        logger.info(f"Revising plan (attempt {self.plan_revision_count}): {reason}")
        
        revision_prompt = PLAN_REVISION_PROMPT.format(
            revision_reason=reason,
            original_plan=self.current_plan
        )
        
        self.memory.messages.append({
            "role": "user",
            "content": revision_prompt
        })
        
        yield MessageEvent(message=f"🔄 Revising plan (attempt {self.plan_revision_count})...")
        
        result = await self.llm_client.ask(
            messages=self.memory.get_messages(),
            tools=None,
        )
        
        # Check if LLM returned a text/answer response (not a tool call)
        if result.get("type") in ["text", "answer"]:
            revised_plan = result.get("answer", "")
            if revised_plan and "PLAN" in revised_plan.upper():
                logger.info(f"Plan revised successfully:\n{revised_plan}")
                self.current_plan = revised_plan
                self.memory.messages.append({
                    "role": "assistant",
                    "content": revised_plan
                })
                yield MessageEvent(message=f"🔄 Plan revised:\n{revised_plan}")
                return  # Plan stored in self.current_plan
        
        logger.warning("Failed to revise plan")
    
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
    ):
        logger.debug(f"Processing new message for session {session_id}: {message[:80]}{'...' if len(message) > 80 else ''}")
        
        # Initialize memory
        if parent_history is None:
            self.memory.add_user_message(session_id, message)
            await self.memory.initialize_messages(session_id)
        else:
            self.memory.messages = copy.deepcopy(parent_history)
            self.memory.messages.append({"role": "user", "content": message})
            self.memory.add_user_message(session_id, message)
        
        # Reset counters for new user message
        self.consecutive_search_replace_failures = 0
        self.current_plan = None
        self.plan_revision_count = 0
        
        # Phase 1: Planning
        async for event in self._generate_plan(session_id):
            yield event
        
        if not self.current_plan:
            # If planning failed, fall back to reactive execution
            logger.warning("No plan generated, falling back to reactive mode")
            yield MessageEvent(message="⚠️ Could not generate plan, proceeding with reactive execution...")
        
        # Phase 2: Acting
        iteration = 0
        consecutive_failures = 0
        MAX_CONSECUTIVE_FAILURES = 3
        
        while iteration < self.MAX_ITERATION:
            iteration += 1
            logger.debug(f"PlanAct iteration {iteration}")
            yield MessageEvent(message=f"⚙️ Executing... (Step: {iteration})")
            
            # Add context about the plan to help LLM stay on track
            execution_context = ""
            if self.current_plan:
                execution_context = f"\n\nReminder - Current Plan:\n{self.current_plan}\n\nPlease follow the plan step by step."
                
            # Temporarily add execution context
            if execution_context:
                self.memory.messages.append({
                    "role": "user",
                    "content": execution_context
                })
            
            result = await self.llm_client.ask(
                messages=self.memory.get_messages(),
                tools=self.tools_definitions,
            )
            
            # Remove the temporary context
            if execution_context:
                self.memory.messages.pop()
            
            if result["type"] == "tool_call":
                tool_name = result["tool_name"]
                tool_args = dict(result.get("tool_args") or {})
                
                # Handle parallel tasks
                if tool_name == self.PARALLEL_TOOL_NAME:
                    if not self.is_parent:
                        error_msg = "⚠️ This agent is not allowed to create sub-agents. Only parent agents can use execute_parallel_tasks."
                        logger.warning(f"Blocked parallel task execution: agent is not a parent (session: {session_id})")
                        yield MessageEvent(message=error_msg)
                        self.memory.add_tool_call(session_id, iteration, tool_name, tool_args)
                        self.memory.add_tool_result(session_id, iteration, {"success": False, "error": error_msg})
                        consecutive_failures += 1
                        continue
                    
                    context_messages = copy.deepcopy(self.memory.get_messages())
                    tool_args.setdefault("context_messages", context_messages)
                    tool_args.setdefault("parent_session_id", session_id)
                    tool_args.setdefault("parent_flow_type", "planact")
                
                logger.info(f"Tool call: {tool_name} with args: {tool_args}")
                
                is_report = False
                tool_result = None
                
                # Execute tool
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
                
                if tool_result is None:
                    tool_result = {"error": "Tool execution returned no result"}
                
                self.memory.add_tool_call(session_id, iteration, tool_name, tool_args)
                self.memory.add_tool_result(session_id, iteration, tool_result)
                
                # Check if tool execution was successful
                tool_failed = (
                    isinstance(tool_result, dict) and 
                    (tool_result.get("success") is False or 
                     "error" in tool_result)
                )
                
                if tool_failed:
                    consecutive_failures += 1
                    logger.warning(f"Tool {tool_name} failed. Consecutive failures: {consecutive_failures}")
                    
                    # Consider plan revision after multiple failures
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES and self.current_plan:
                        logger.info("Multiple consecutive failures detected, considering plan revision")
                        revision_reason = f"Multiple tool failures occurred. Last failure: {tool_result.get('error', 'Unknown error')}"
                        async for event in self._revise_plan(session_id, revision_reason):
                            yield event
                        consecutive_failures = 0  # Reset after revision
                else:
                    # Success - reset failure counter
                    consecutive_failures = 0
                
                # Track search_replace tool failures specifically
                if tool_name == self.SEARCH_REPLACE_TOOL_NAME:
                    is_search_replace_failed = (
                        tool_result is not None and 
                        (isinstance(tool_result, dict) and 
                         (tool_result.get("success") is False or 
                          "error" in tool_result or 
                          tool_result.get("status") == "failed"))
                    )
                    
                    if is_search_replace_failed:
                        self.consecutive_search_replace_failures += 1
                        logger.warning(f"Search_replace tool failed. Consecutive failures: {self.consecutive_search_replace_failures}/{self.MAX_SEARCH_REPLACE_FAILURES}")
                        
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
                            yield MessageEvent(message=reflection_message)
                            
                            # Also trigger plan revision
                            if self.current_plan:
                                async for event in self._revise_plan(session_id, "Repeated search_replace failures"):
                                    yield event
                    else:
                        # Search_replace succeeded
                        if self.consecutive_search_replace_failures > 0:
                            logger.info(f"Search_replace tool succeeded. Resetting failure counter from {self.consecutive_search_replace_failures} to 0.")
                        self.consecutive_search_replace_failures = 0
                
                if is_report:
                    # Before returning, validate that if search_replace was used, linter was run after
                    if not self._validate_search_replace_linter_sequence():
                        error_msg = "⚠️ Search_replace tool was used but linter was not run successfully after the last search_replace. Please run the linter tool to verify the code changes."
                        logger.warning(f"Report blocked: {error_msg}")
                        yield MessageEvent(message=error_msg)
                        self.memory.messages.append({
                            "role": "user",
                            "content": error_msg
                        })
                        continue
                    return
                    
            else:
                # Text response (no tool call)
                answer_text = result.get("answer", "") or ""
                if answer_text:
                    self.memory.add_assistant_message(session_id, answer_text)
                yield MessageEvent(message=answer_text)
                return
        
        logger.warning(f"Reached max iterations ({self.MAX_ITERATION}), returning error message")
        error_message = "Sorry. Hit max iterations limit"
        yield ReportEvent(message=error_message)

