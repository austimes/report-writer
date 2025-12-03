from abc import ABC, abstractmethod
from typing import Any, Dict
import os


class BaseLLMClient(ABC):
    @abstractmethod
    async def complete(self, messages: list[Dict[str, str]]) -> str:
        pass


class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None, model: str = "gpt-4"):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package is required. Install with: uv add openai"
            )

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key must be provided or set in OPENAI_API_KEY")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            default_headers={"OpenAI-Organization": "user-" + self.api_key[:8]},
        )
        self.model = model

    async def complete(self, messages: list[Dict[str, str]]) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            extra_body={"store": False},
        )
        return response.choices[0].message.content


class AnthropicClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None, model: str = "claude-3-5-sonnet-20241022"):
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError(
                "anthropic package is required. Install with: uv add anthropic"
            )

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key must be provided or set in ANTHROPIC_API_KEY"
            )

        self.client = AsyncAnthropic(
            api_key=self.api_key,
            default_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        )
        self.model = model

    async def complete(self, messages: list[Dict[str, str]]) -> str:
        system_messages = [m for m in messages if m["role"] == "system"]
        conversation_messages = [m for m in messages if m["role"] != "system"]

        system_content = "\n\n".join(m["content"] for m in system_messages)

        response = await self.client.messages.create(
            model=self.model,
            system=system_content if system_content else None,
            messages=conversation_messages,
            max_tokens=4096,
        )

        return response.content[0].text
