from typing import List, Optional, Union
from app.domain.services.tools.base import tool, BaseTool
from app.domain.models.tool_result import ToolResult

class MessageTool(BaseTool):
    """Message tool class, providing message sending functions for user interaction"""

    name: str = "message"
    
    def __init__(self):
        """Initialize message tool class"""
        super().__init__()
    
    # @tool(
    #     name="message_request_user_clarification",
    #     description="Send a message to user to request clarification. Use for asking for more information, confirming understanding, or requesting specific details.",
    #     parameters={
    #         "text": {
    #             "type": "string",
    #             "description": "Message text to display to user"
    #         }
    #     },
    #     required=["text"]
    # )
    # async def message_request_user_clarification(
    #     self,
    #     text: str
    # ) -> ToolResult:
    #     """Send message to user to request clarification
        
    #     Args:
    #         text: Message text to display to user
            
    #     Returns:
    #         Message sending result
    #     """
            
    #     # Return success result, actual UI display logic implemented by caller
    #     return ToolResult(
    #         success=True,
    #         data=text
    #     )
    @tool(
        name="message_done",
        description="A special tool to indicate the task is done, and stop the execution immediately.",
        parameters={
            "text": {
                "type": "string",
                "description": "Message text to display to user"
            }
        },
        required=["text"]
    )
    async def message_done(
        self,
        text: str
    ) -> ToolResult:
        """Send message to user to indicate the task is done
        
        Args:
            text: Message text to display to user

        Returns:
            Message sending result
        """
            
        # Return success result, actual UI display logic implemented by caller
        result = {
            "text": text
        }
        return ToolResult(
            success=True,
            data=result
        )

class MessageNotifyUserTool(BaseTool):
    """Message notify user tool class, providing message sending functions for user interaction"""

    name: str = "message_notify_user"
    
    def __init__(self):
        """Initialize message notify user tool class"""
        super().__init__()
            
    @tool(
        name="message_notify_user",
        description="Send a message to user without requiring a response. Use for acknowledging receipt of messages, providing progress updates, reporting task completion, or explaining changes in approach.",
        parameters={
            "text": {
                "type": "string",
                "description": "Message text to display to user"
            }
        },
        required=["text"]
    )
    async def message_notify_user(
        self,
        text: str
    ) -> ToolResult:
        """Send notification message to user, no response needed
        
        Args:
            text: Message text to display to user
            
        Returns:
            Message sending result
        """
            
        # Return success result, actual UI display logic implemented by caller
        return ToolResult(
            success=True,
            data=text
        )


class MessageDeliverArtifactTool(BaseTool):
    """Message deliver artifact tool class, providing message sending functions for user interaction"""

    name: str = "message_deliver_artifact"
    
    def __init__(self):
        """Initialize message deliver artifact tool class"""
        super().__init__()

    @tool(
        name="message_deliver_artifact",
        description="Send a message to user to deliver artifact. Use for delivering files, images, or other binary data.",
        parameters={
            "text": {
                "type": "string",
                "description": "Message text to display to user"
            },
            "artifacts": {
                "type": "array",
                "description": "(Optional) Array of the paths of the artifacts to deliver",
                "items": {
                    "type": "string",
                    "description": "Artifact file path"
                }
            }
        },
        required=["text"]
    )
    async def message_deliver_artifact(
        self,
        text: str,
        artifacts: Optional[List[str]] = None
    ) -> ToolResult:
        """Send message to user to deliver artifact
        
        Args:
            text: Message text to display to user
            artifacts: Array of the paths of the artifacts to deliver

        Returns:
            Message sending result
        """
            
        # Return success result, actual UI display logic implemented by caller
        result = {
            "text": text,
            "artifacts": artifacts
        }
        return ToolResult(
            success=True,
            data=result
        )