import os
import openai
from .types import EngineConfig, Message

class AIClient:
    def __init__(self, config: EngineConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API Key not found in config or environment")
        
        self.client = openai.OpenAI(api_key=self.api_key)

    def generate_response(self, messages: list[Message]) -> str:
        # Convert pydantic messages to dict
        api_messages = [{"role": m.role, "content": m.content} for m in messages]
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=api_messages,
                temperature=self.config.temperature
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"Error calling OpenAI: {e}")
            raise
