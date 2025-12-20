#!/usr/bin/env python3
"""
Parallel Task Executor Tool
"""

import asyncio
import copy
from typing import Any, Dict, List, Optional, AsyncGenerator

from utils.logger import Logger
from tools.base_tool import MCPTool
from models import MessageEvent, ReportEvent, ToolCallEvent, ToolResultEvent, BaseEvent

logger = Logger('parallel_task_executor', log_to_file=False)


class ParallelTaskExecutorTool(MCPTool):
    """Tool that runs multiple FlowAgent subtasks concurrently."""

    def __init__(self):
        self.workspace_dir: Optional[str] = None

    @property
    def name(self) -> str:
        return "execute_parallel_tasks"

    def set_workspace_dir(self, workspace_dir: str) -> None:
        if self.workspace_dir == workspace_dir:
            return
        self.workspace_dir = workspace_dir
        logger.info(f"Parallel task executor workspace set to: {workspace_dir}")

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "execute_parallel_tasks",
                "description": (
                    "⚡ Execute multiple independent programming tasks SIMULTANEOUSLY for maximum efficiency. "
                    "MANDATORY when request has 2+ independent subtasks (different files, different functions/classes in same file, multiple bugs/features). "
                    "Example: 'Fix bug in auth.py and add logging to utils.py' → 2 parallel tasks. "
                    "Example: 'Optimize func_a() and func_b() in helpers.py' → 2 parallel tasks (same file is OK!). "
                    "Creates sub-agents that work concurrently, dramatically reducing execution time."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tasks": {
                            "type": "array",
                            "description": (
                                "Array of independent task descriptions. Each must be clear and self-contained. "
                                "Be specific: include file names, function names, and exact actions. "
                                "Example: ['Add type hints to utils.py', 'Fix memory leak in cache.py', 'Optimize query_db() in database.py']"
                            ),
                            "items": {
                                "type": "string"
                            },
                            "minItems": 2
                        },
                        "parent_information": {
                            "type": "string",
                            "description": (
                                "Summary of information and context that all child agents need to know. "
                                "This should include: key findings, important context, relevant code patterns, "
                                "dependencies, or any other information that will help child agents complete their tasks efficiently. "
                                "This information is shared by ALL child agents."
                            )
                        },
                    },
                    "required": ["tasks", "parent_information"]
                }
            }
        }

    def get_call_notification(self, tool_args: Dict[str, Any]) -> Optional[str]:
        task_count = len(tool_args.get("tasks") or [])
        return f"Starting {task_count} parallel subtasks..."

    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[str]:
        return tool_result.get("summary")

    async def execute_streaming(
        self,
        tasks: List[str],
        parent_session_id: Optional[str] = None,
        context_messages: Optional[List[Dict[str, Any]]] = None,
        parent_flow_type: Optional[str] = None,
        parent_information: Optional[str] = None
    ) -> AsyncGenerator[BaseEvent, None]:
        """
        Execute tasks in parallel and yield all events from subtasks.
        This is used when we want to stream events to the UI.
        """
        if not tasks:
            yield MessageEvent(message="No tasks provided for parallel execution")
            return

        logger.info(f"Executing {len(tasks)} parallel tasks with streaming")

        # Create queues for each subtask to collect events
        event_queues: List[asyncio.Queue] = [asyncio.Queue() for _ in tasks]
        
        async def run_subtask(index: int, task_description: str, event_queue: asyncio.Queue) -> Dict[str, Any]:
            sub_session_id = f"{parent_session_id}_sub_{index}" if parent_session_id else f"parallel_sub_{index}"
            final_message = ""

            try:
                # Determine child flow type based on parent flow type
                if parent_flow_type == "planact" or parent_flow_type == "PlanActFlow":
                    from agents.planact_flow import PlanActFlow
                    agent = PlanActFlow(self.workspace_dir or "", is_parent=False)
                else:
                    # Default to ReActFlow (for "react", "ReActFlow", or None)
                    from agents.react_flow import ReActFlow
                    agent = ReActFlow(self.workspace_dir or "", is_parent=False)
                async for event in agent.process(
                    task_description,
                    sub_session_id,
                    parent_information=parent_information,
                ):
                    # Put all events into the queue
                    await event_queue.put((index, event))
                    
                    # Track final message
                    if isinstance(event, MessageEvent):
                        if event.message and not event.message.startswith("Thinking"):
                            final_message = event.message
                    elif isinstance(event, ReportEvent):
                        final_message = event.message
            except Exception as exc:  # pragma: no cover - best-effort handling
                logger.error(f"Subtask {index} failed: {exc}", exc_info=True)
                final_message = f"Error: {exc}"
                await event_queue.put((index, MessageEvent(message=f"Subtask {index + 1} failed: {exc}")))
            finally:
                # Signal completion
                await event_queue.put((index, None))

            return {
                "task_id": index,
                "task": task_description,
                "result": final_message or "No response from sub-agent",
            }

        # Start all subtasks
        subtask_coroutines = [
            run_subtask(i, task, event_queues[i]) 
            for i, task in enumerate(tasks)
        ]
        subtask_tasks = [asyncio.create_task(coro) for coro in subtask_coroutines]
        
        # Track which subtasks are still running
        active_tasks = set(range(len(tasks)))
        
        # Yield events as they come from any subtask
        while active_tasks:
            # Create tasks to wait for events from all active queues
            queue_tasks = {
                i: asyncio.create_task(event_queues[i].get())
                for i in active_tasks
            }
            
            # Wait for the first event from any queue
            done, pending = await asyncio.wait(
                queue_tasks.values(),
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Process completed queue tasks
            for task in done:
                # Find which queue this task belongs to
                queue_index = None
                for i, qt in queue_tasks.items():
                    if qt == task:
                        queue_index = i
                        break
                
                if queue_index is None:
                    continue
                
                index, event = task.result()
                
                if event is None:
                    # Subtask completed
                    active_tasks.remove(index)
                    logger.debug(f"Subtask {index} completed")
                else:
                    # Filter out "Thinking" messages to avoid UI spam
                    if isinstance(event, MessageEvent) and event.message.startswith("Thinking"):
                        continue  # Skip this event entirely
                    
                    # Add task identifier to event message for clarity
                    if isinstance(event, (ToolCallEvent, ToolResultEvent)):
                        # Prefix tool events with subtask number
                        original_message = event.message or ""
                        event.message = f"[Subtask {index + 1}] {original_message}"
                    elif isinstance(event, MessageEvent):
                        original_message = event.message or ""
                        event.message = f"[Subtask {index + 1}] {original_message}"
                    
                    # Set agent information for child agents
                    # Use index % 8 to cycle through 8 colors for child agents
                    event.is_parent = False
                    event.agent_index = index % 8
                    
                    yield event
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
        
        # Wait for all subtasks to complete and collect results
        results = await asyncio.gather(*subtask_tasks)
        
        # Generate summary for display
        summary_lines = ["Parallel Execution Results:"]
        for res in results:
            summary_lines.append(f"--- Task {res['task_id'] + 1} ---")
            summary_lines.append(f"Description: {res['task']}")
            summary_lines.append(f"Result: {res['result']}")
            summary_lines.append("")

        summary = "\n".join(summary_lines).strip()
        
        # Yield final summary as a message for UI display
        yield MessageEvent(message=summary)
        
        # Yield ToolResultEvent with only final reports for parent's memory
        # This ensures parent's context only contains child reports, not intermediate tool calls/results
        child_reports = {
            "success": True,
            "summary": summary,
            "tasks": [
                {
                    "task_id": res['task_id'],
                    "task": res['task'],
                    "report": res['result']  # Only the final report
                }
                for res in results
            ]
        }
        yield ToolResultEvent(
            message="Parallel tasks completed",
            tool_name="execute_parallel_tasks",
            result=child_reports
        )

    async def execute(
        self,
        tasks: List[str],
        parent_session_id: Optional[str] = None,
        context_messages: Optional[List[Dict[str, Any]]] = None,
        parent_flow_type: Optional[str] = None,
        parent_information: Optional[str] = None
    ) -> Dict[str, Any]:
        if not tasks:
            return {
                "success": False,
                "error": "No tasks provided for parallel execution",
            }

        logger.info(f"Executing {len(tasks)} parallel tasks")

        async def run_subtask(index: int, task_description: str) -> Dict[str, Any]:
            sub_session_id = f"{parent_session_id}_sub_{index}" if parent_session_id else f"parallel_sub_{index}"
            final_message = ""

            try:
                # Determine child flow type based on parent flow type
                if parent_flow_type == "planact" or parent_flow_type == "PlanActFlow":
                    from agents.planact_flow import PlanActFlow
                    agent = PlanActFlow(self.workspace_dir or "", is_parent=False)
                else:
                    # Default to ReActFlow (for "react", "ReActFlow", or None)
                    from agents.react_flow import ReActFlow
                    agent = ReActFlow(self.workspace_dir or "", is_parent=False)
                async for event in agent.process(
                    task_description,
                    sub_session_id,
                    parent_information=parent_information,
                ):
                    if isinstance(event, MessageEvent):
                        if event.message and not event.message.startswith("Thinking"):
                            final_message = event.message
                    elif isinstance(event, ReportEvent):
                        final_message = event.message
            except Exception as exc:  # pragma: no cover - best-effort handling
                logger.error(f"Subtask {index} failed: {exc}", exc_info=True)
                final_message = f"Error: {exc}"

            return {
                "task_id": index,
                "task": task_description,
                "result": final_message or "No response from sub-agent",
            }

        coroutines = [run_subtask(i, task) for i, task in enumerate(tasks)]
        results = await asyncio.gather(*coroutines)

        summary_lines = ["Parallel Execution Results:"]
        for res in results:
            summary_lines.append(f"--- Task {res['task_id'] + 1} ---")
            summary_lines.append(f"Description: {res['task']}")
            summary_lines.append(f"Result: {res['result']}")
            summary_lines.append("")

        summary = "\n".join(summary_lines).strip()

        # Return only final reports for parent's memory
        return {
            "success": True,
            "summary": summary,
            "tasks": [
                {
                    "task_id": res['task_id'],
                    "task": res['task'],
                    "report": res['result']  # Only the final report
                }
                for res in results
            ],
        }

