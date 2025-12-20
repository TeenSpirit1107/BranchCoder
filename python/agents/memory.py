import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from utils.logger import Logger
from tools.tool_factory import execute_tool
from tools.file_context_manager import get_file_context_manager
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
        # Initialize file context manager
        self.file_context_manager = get_file_context_manager(workspace_dir)
        # Store parent_information and task for child agents (for regenerating system prompt)
        self._parent_information: Optional[str] = None
        self._task: Optional[str] = None
        # Store workspace_structure to avoid reloading it every time
        self._workspace_structure: str = ""
    
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
        
        # Store workspace_structure for later use
        self._workspace_structure = workspace_structure
        
        system_prompt = get_system_prompt(is_parent=self.is_parent)
        
        # Get file context (dynamically loaded file contents)
        file_context = self.file_context_manager.format_files_for_prompt()
        if not file_context:
            file_context = ""  # Empty string if no files are open
        
        format_args = {
            "current_time": current_time,
            "workspace_dir": self.workspace_dir,
            "workspace_structure": workspace_structure,
            "file_context": file_context
        }
        
        # Add parent_information and task for child agents
        if not self.is_parent:
            format_args["parent_information"] = parent_information or "No additional context provided."
            format_args["task"] = task or "Complete the assigned task."
        
        return system_prompt.format(**format_args)
    
    def close_temporary_files(self) -> None:
        """Close all temporary files after an iteration."""
        self.file_context_manager.close_temporary_files()
    
    def inherit_file_context(self, parent_memory: 'Memory') -> None:
        """Inherit file context from parent memory."""
        self.file_context_manager.inherit_from(parent_memory.file_context_manager)
    
    def open_files(self, file_paths: List[str], mode: str = "persistent") -> None:
        """
        Open files for context inclusion.
        
        Args:
            file_paths: List of file paths to open
            mode: "persistent" or "temporary"
        """
        from tools.file_context_manager import FileOpenMode
        open_mode = FileOpenMode.PERSISTENT if mode == "persistent" else FileOpenMode.TEMPORARY
        for file_path in file_paths:
            self.file_context_manager.open_file(file_path, open_mode)
    
    async def initialize_messages(self, session_id: str, parent_information: Optional[str] = None, task: Optional[str] = None) -> List[Dict[str, Any]]:
        # Store parent_information and task for later use in get_messages
        self._parent_information = parent_information
        self._task = task
        
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
        """
        Get messages for LLM, with dynamically updated system prompt.
        System prompt is regenerated each time to include latest file context.
        """
        # Regenerate system prompt with latest file context (synchronous version)
        from datetime import datetime
        from prompts.flow_prompt import get_system_prompt
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        system_prompt = get_system_prompt(is_parent=self.is_parent)
        
        # Get latest file context
        file_context = self.file_context_manager.format_files_for_prompt()
        if not file_context:
            file_context = ""
        
        format_args = {
            "current_time": current_time,
            "workspace_dir": self.workspace_dir,
            "workspace_structure": self._workspace_structure,  # Use stored workspace structure
            "file_context": file_context
        }
        
        # For child agents, use stored parent_information and task
        if not self.is_parent:
            format_args["parent_information"] = self._parent_information or "No additional context provided."
            format_args["task"] = self._task or "Complete the assigned task."
        
        updated_system = system_prompt.format(**format_args)
        
        # Update system message in messages
        messages = self.messages.copy()
        if messages and messages[0].get("role") == "system":
            messages[0] = {"role": "system", "content": updated_system}
        else:
            messages.insert(0, {"role": "system", "content": updated_system})
        
        return messages
