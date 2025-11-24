import json
from datetime import datetime
from typing import List, Dict
from utils.logger import Logger
from tools.tool_factory import execute_tool
from models import ToolResultEvent, ToolCallEvent
from prompts.flow_prompt import SYSTEM_PROMPT

logger = Logger('flow.memory', log_to_file=False)


class Memory:

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.messages: List[Dict[str, str]] = []
    
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
        
        return SYSTEM_PROMPT.format(
            current_time=current_time,
            workspace_dir=self.workspace_dir,
            workspace_structure=workspace_structure
        )
    
    async def initialize_messages(self, initial_messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        system_prompt = await self.generate_system_prompt()
        self.messages = [
            {"role": "system", "content": system_prompt},
            *initial_messages
        ]
        return self.messages
    
    def add_tool_call(self, iteration: int, tool_name: str, tool_args: Dict) -> None:
        self.messages.append({
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
    
    def add_tool_result(self, iteration: int, tool_result: Dict) -> None:
        self.messages.append({
            "role": "tool",
            "content": json.dumps(tool_result),
            "tool_call_id": f"call_{iteration}"
        })
    
    def get_messages(self) -> List[Dict[str, str]]:
        return self.messages
