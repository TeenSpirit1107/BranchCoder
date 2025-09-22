import base64

from app.domain.services.tools.base import tool, BaseTool
from app.domain.models.tool_result import ToolResult
from app.domain.external.llm import ImageLLM
from app.domain.external.sandbox import Sandbox

class ImageTool(BaseTool):
    """Image tool class, providing image generation functions"""

    name: str = "image"
    
    def __init__(self, sandbox: Sandbox, image_llm: ImageLLM):
        """Initialize image tool class
        
        Args:
            sandbox: Sandbox service
            image_llm: Image LLM service
        """
        super().__init__()
        self.sandbox = sandbox
        self.image_llm = image_llm
    
    @tool(
        name="image_to_text",
        description="Generate text from image. Use for generating text from image.",
        parameters={
            "image_path": {
                "type": "string",
                "description": "Image file path"
            }
        },
        required=["image_path"]
    )
    async def image_to_text(
        self,
        image_path: str
    ) -> ToolResult:
        """Generate text from image
        
        Args:
            image_path: Image file path
            
        Returns:
            Text from image
        """
        image_file = await self.sandbox.file_download(image_path)
        image_base64 = base64.b64encode(image_file).decode('utf-8')
        messages = [
            {"role": "system", "content": "You are a helpful assistant that can describe the content of images."},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}", "detail": "auto"}},
                {"type": "text", "text": "Please describe the content of the image."}
            ]}
        ]
        response = await self.image_llm.ask(messages) 
        return ToolResult(
            success=True,
            data=response.content
        )
    
    @tool(
        name="ask_question_about_image",
        description="Ask a question about the image. Use for asking a question about the image.",
        parameters={
            "image_path": {
                "type": "string",
                "description": "Image file path"
            },
            "text": {
                "type": "string",
                "description": "Question about the image"
            }
        },
        required=["image_path", "text"]
    )
    async def ask_question_about_image(
        self,
        image_path: str,
        text: str
    ) -> ToolResult:
        """Ask a question about the image
        
        Args:
            image_path: Image file path
            text: Question about the image
            
        Returns:
            Answer to the question
        """
        image_file = await self.sandbox.file_download(image_path)
        image_base64 = base64.b64encode(image_file).decode('utf-8')
        messages = [
            {"role": "system", "content": "You are a helpful assistant that can answer questions about images."},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}", "detail": "auto"}},
                {"type": "text", "text": text}
            ]}
        ]
        response = await self.image_llm.ask(messages) 
        return ToolResult(
            success=True,
            data=response.content
        )
