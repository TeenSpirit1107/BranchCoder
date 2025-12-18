import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from utils.logger import Logger
from tools.tool_factory import execute_tool
from models import ToolResultEvent, ToolCallEvent
from prompts.flow_prompt import get_system_prompt

logger = Logger('flow.memory', log_to_file=False)

DEFAULT_HISTORY_DIR = Path.home() / ".vscode-branch-coder"
DEFAULT_HISTORY_FILE = DEFAULT_HISTORY_DIR / "conversation_history.json"
MAX_HISTORY_MESSAGES = 50


class Memory:

    def __init__(self, workspace_dir: str, history_file: Optional[str] = None, is_parent: bool = True):
        self.workspace_dir = workspace_dir
        self.is_parent = is_parent
        self.history_file = Path(history_file) if history_file else DEFAULT_HISTORY_FILE
        self._ensure_history_dir()
        self._histories: Dict[str, List[Dict[str, Any]]] = {}
        self._load_all_histories()
        self.messages: List[Dict[str, Any]] = []
    
    def _ensure_history_dir(self) -> None:
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.error(f"Failed to create history directory: {exc}")

    def _load_all_histories(self) -> None:
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self._histories = json.load(f)
                logger.debug(f"Loaded {len(self._histories)} conversation histories")
            else:
                self._histories = {}
                logger.debug("No existing history file found, starting fresh")
        except Exception as exc:
            logger.error(f"Failed to load history file: {exc}")
            self._histories = {}

    def _save_all_histories(self) -> None:
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self._histories, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved {len(self._histories)} conversation histories")
        except Exception as exc:
            logger.error(f"Failed to save history file: {exc}")

    def _add_history_entry(self, session_id: str, entry: Dict[str, Any]) -> None:
        if session_id not in self._histories:
            self._histories[session_id] = []
        entry_copy = dict(entry)
        self._histories[session_id].append(entry_copy)

        if len(self._histories[session_id]) > MAX_HISTORY_MESSAGES:
            self._histories[session_id] = self._histories[session_id][-MAX_HISTORY_MESSAGES:]

        self._save_all_histories()
        logger.debug(
            f"Added {entry_copy.get('role', 'unknown')} message to session {session_id} "
            f"(total: {len(self._histories[session_id])})"
        )

    def get_history(self, session_id: str = "default") -> List[Dict[str, Any]]:
        return self._histories.get(session_id, []).copy()

    def clear_history(self, session_id: str = "default") -> None:
        if session_id in self._histories:
            del self._histories[session_id]
            self._save_all_histories()
            logger.info(f"Cleared history for session {session_id}")

    def clear_all_histories(self) -> None:
        self._histories = {}
        self._save_all_histories()
        logger.info("Cleared all conversation histories")

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        return self.get_history(session_id)

    async def generate_system_prompt(self, parent_information: Optional[str] = None, task: Optional[str] = None) -> str:
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
        
        system_prompt = get_system_prompt(is_parent=self.is_parent)
        format_args = {
            "current_time": current_time,
            "workspace_dir": self.workspace_dir,
            "workspace_structure": workspace_structure
        }
        
        # Add parent_information and task for child agents
        if not self.is_parent:
            format_args["parent_information"] = parent_information or "No additional context provided."
            format_args["task"] = task or "Complete the assigned task."
        
        return system_prompt.format(**format_args)
    
    async def initialize_messages(self, session_id: str, parent_information: Optional[str] = None, task: Optional[str] = None) -> List[Dict[str, Any]]:
        system_prompt = await self.generate_system_prompt(parent_information=parent_information, task=task)
        session_history = self.get_history(session_id)
        self.messages = [
            {"role": "system", "content": system_prompt},
            *session_history
        ]
        return self.messages

    def add_user_message(self, session_id: str, content: str) -> None:
        self._add_history_entry(session_id, {"role": "user", "content": content})

    def add_assistant_message(self, session_id: str, content: str) -> None:
        self._add_history_entry(session_id, {"role": "assistant", "content": content})
        self.messages.append({
            "role": "assistant",
            "content": content
        })

    def add_tool_call(self, session_id: str, iteration: int, tool_name: str, tool_args: Dict) -> None:
        tool_call_message = {
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
        }
        self.messages.append(tool_call_message)
        self._add_history_entry(session_id, tool_call_message)
    
    def add_tool_result(self, session_id: str, iteration: int, tool_result: Dict) -> None:
        tool_result_message = {
            "role": "tool",
            "content": json.dumps(tool_result),
            "tool_call_id": f"call_{iteration}"
        }
        self.messages.append(tool_result_message)
        self._add_history_entry(session_id, tool_result_message)
    
    def get_messages(self) -> List[Dict[str, Any]]:
        return self.messages
