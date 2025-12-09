#!/usr/bin/env python3
"""
Parallel Task Executor Tool
"""

import asyncio
import copy
from typing import Any, Dict, List, Optional

from utils.logger import Logger
from tools.base_tool import MCPTool
from models import MessageEvent, ReportEvent

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
                "description": "Execute a collection of programming tasks in parallel by spinning up sub-agents and summarizing their outputs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tasks": {
                            "type": "array",
                            "description": "List of task descriptions to run in parallel.",
                            "items": {
                                "type": "string"
                            }
                        },
                    },
                    "required": ["tasks"]
                }
            }
        }

    def get_call_notification(self, tool_args: Dict[str, Any]) -> Optional[str]:
        task_count = len(tool_args.get("tasks") or [])
        return f"启动 {task_count} 个并行子任务..."

    def get_result_notification(self, tool_result: Dict[str, Any]) -> Optional[str]:
        return tool_result.get("summary")

    async def execute(
        self,
        tasks: List[str],
        parent_session_id: Optional[str] = None,
        context_messages: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        if not tasks:
            return {
                "success": False,
                "error": "没有提供要并行执行的任务",
            }

        logger.info(f"Executing {len(tasks)} parallel tasks")

        history_snapshot = copy.deepcopy(context_messages) if context_messages else None

        async def run_subtask(index: int, task_description: str) -> Dict[str, Any]:
            sub_session_id = f"{parent_session_id}_sub_{index}" if parent_session_id else f"parallel_sub_{index}"
            final_message = ""

            try:
                from agents.flow import FlowAgent

                agent = FlowAgent(self.workspace_dir or "")
                async for event in agent.process(
                    task_description,
                    sub_session_id,
                    parent_history=copy.deepcopy(history_snapshot) if history_snapshot else None,
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
                "result": final_message or "未收到子代理的回应",
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

        return {
            "success": True,
            "summary": summary,
            "tasks": results,
        }

