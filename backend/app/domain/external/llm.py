from typing import List, Dict, Any, Optional, Protocol

class LLM(Protocol):
    """AI service gateway interface for interacting with AI services"""
    
    async def ask(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send chat request to AI service
        
        Args:
            messages: List of messages, including conversation history
            tools: Optional list of tools for function calling
            response_format: Optional response format configuration
            
        Returns:
            Response message from AI service
        """
        pass 

class ImageLLM(Protocol):
    pass

class AudioLLM(Protocol):
    async def audio_to_text(
        self,
        audio_path: str,
        filename: str
    ) -> str:
        pass

class VideoLLM(Protocol):
    async def video_to_text(
        self,
        video_uri: str,
    ) -> str:
        pass

    async def ask_video(
        self,
        video_uri: str,
        query: str
    ) -> str:
        pass

class ReasonLLM(Protocol):
    async def deep_reasoning(
        self,
        problem: str,
        context: Optional[str] = None
    ) -> str:
        pass
