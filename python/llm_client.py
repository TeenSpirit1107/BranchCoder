import json
import os
from typing import Any, Dict, List, Optional, Literal, TypedDict
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

class CompletionResult(TypedDict):
    type: Literal["tool_call", "answer"]
    answer: Optional[str]
    tool_name: Optional[str]
    tool_args: Optional[Dict[str, Any]]
    usage: Dict[str, int]
    raw: Any


class AsyncChatClientWrapper:

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL")
        base_url = os.getenv("OPENAI_BASE_URL")
        proxy = os.getenv("OPENAI_PROXY")

        if not api_key:
            raise ValueError("❌ 缺少 OPENAI_API_KEY")
        if not model:
            raise ValueError("❌ 缺少 OPENAI_MODEL")
        if not base_url:
            raise ValueError("❌ 缺少 OPENAI_BASE_URL")
        if proxy:
            os.environ["HTTP_PROXY"] = proxy
            os.environ["HTTPS_PROXY"] = proxy

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=60.0,
        )
        self.model = model

    async def create_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 1,
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> CompletionResult:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        if tools:
            kwargs["tools"] = tools
        if response_format:
            kwargs["response_format"] = response_format

        completion = await self.client.chat.completions.create(**kwargs)
        return self._parse_completion(completion)

    def _parse_completion(self, completion: Any) -> CompletionResult:
        choice = completion.choices[0]
        message = choice.message

        # token 统计
        usage = getattr(completion, "usage", None) or {}
        usage_dict = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or usage.get("prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0) or usage.get("completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0)
            or usage.get("total_tokens", usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)),
        }

        # tool_calls（新版接口）
        if getattr(message, "tool_calls", None):
            fn = message.tool_calls[0].function
            try:
                args = json.loads(fn.arguments) if isinstance(fn.arguments, str) else fn.arguments
            except json.JSONDecodeError:
                args = {"_raw": fn.arguments}

            return CompletionResult(
                type="tool_call",
                tool_name=fn.name,
                tool_args=args,
                answer=None,
                usage=usage_dict,
                raw=completion,
            )

        # 兼容旧版 function_call
        if getattr(message, "function_call", None):
            fc = message.function_call
            try:
                args = json.loads(fc["arguments"]) if isinstance(fc["arguments"], str) else fc["arguments"]
            except json.JSONDecodeError:
                args = {"_raw": fc["arguments"]}
            return CompletionResult(
                type="tool_call",
                tool_name=fc["name"],
                tool_args=args,
                answer=None,
                usage=usage_dict,
                raw=completion,
            )

        # 普通自然语言回答
        return CompletionResult(
            type="answer",
            tool_name=None,
            tool_args=None,
            answer=getattr(message, "content", "") or "",
            usage=usage_dict,
            raw=completion,
        )
