from openai import OpenAI
from app.infrastructure.config import get_settings

class LLMClient:
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI (api_key=settings.api_key,base_url=settings.base_url)

    def ask(self, message):
        result = self.client.chat.completions.create(
            model='gpt-4o',
            messages=message,
        )
        return result