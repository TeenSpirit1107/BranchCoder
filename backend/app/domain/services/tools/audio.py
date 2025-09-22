import os

from app.domain.services.tools.base import tool, BaseTool
from app.domain.models.tool_result import ToolResult
from app.domain.external.llm import AudioLLM, LLM
from app.domain.external.sandbox import Sandbox

class AudioTool(BaseTool):
    """Audio tool class, providing audio generation functions"""

    name: str = "audio"
    
    def __init__(self, sandbox: Sandbox, audio_llm: AudioLLM, llm: LLM):
        """Initialize audio tool class
        
        Args:
            sandbox: Sandbox service
            audio_llm: Audio LLM service
        """
        super().__init__()
        self.sandbox = sandbox
        self.audio_llm = audio_llm
        self.llm = llm

    @tool(
        name="audio_to_text",
        description="Generate text from audio. Use for generating text from audio.",
        parameters={
            "audio_path": {
                "type": "string",
                "description": "Audio file path"
            }
        },
        required=["audio_path"]
    )
    async def audio_to_text(
        self,
        audio_path: str
    ) -> ToolResult:
        """Generate text from audio
        
        Args:
            audio_path: Audio file path
            
        Returns:
            Text from audio
        """
        audio_file = await self.sandbox.file_download(audio_path)
        filename = os.path.basename(audio_path)
        response = await self.audio_llm.audio_to_text(audio_file, filename) 
        return ToolResult(
            success=True,
            data=response
        )
    
    @tool(
        name="ask_question_about_audio",
        description="Ask a question about the audio. Use for asking a question about the audio.",
        parameters={
            "audio_path": {
                "type": "string",
                "description": "Audio file path"
            },
            "text": {
                "type": "string",
                "description": "Question about the audio"
            }
        },
        required=["audio_path", "text"]
    )
    async def ask_question_about_audio(
        self,
        audio_path: str,
        text: str
    ) -> ToolResult:
        """Ask a question about the audio
        
        Args:
            audio_path: Audio file path
            text: Question about the audio
            
        Returns:
            Answer to the question
        """
        audio_file = await self.sandbox.file_download(audio_path)
        filename = os.path.basename(audio_path)
        transcript = await self.audio_llm.audio_to_text(audio_file, filename) 
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that can answer questions about audios transcript."},
            {"role": "user", "content": [
                {"type": "text", "text": transcript},
                {"type": "text", "text": text}
            ]}
        ]
        response = await self.llm.ask(messages) 
        return ToolResult(
            success=True,
            data=response
        )
