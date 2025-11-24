import json
import os
from typing import Any, Dict, List, Optional, Literal, TypedDict
from openai import AsyncOpenAI
from dotenv import load_dotenv
from utils.logger import Logger

load_dotenv()

logger = Logger('chat_llm', log_to_file=False)

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

    async def ask(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 1,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Literal["none", "auto", Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> CompletionResult:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        if tools:
            kwargs["tools"] = tools
            # Set tool_choice to "auto" if tools are provided and tool_choice not explicitly set
            if tool_choice is None:
                kwargs["tool_choice"] = "auto"
            else:
                kwargs["tool_choice"] = tool_choice
        if response_format:
            kwargs["response_format"] = response_format

        completion = await self.client.chat.completions.create(**kwargs)
        result = self._parse_completion(completion)
        
        # Log LLM response
        logger.info("=" * 80)
        logger.info("LLM Response:")
        logger.info(f"Type: {result.get('type', 'unknown')}")
        if result.get("type") == "tool_call":
            logger.info(f"Tool Name: {result.get('tool_name', 'unknown')}")
            logger.info(f"Tool Args: {json.dumps(result.get('tool_args', {}), ensure_ascii=False, indent=2)}")
        else:
            response_text = result.get("answer", "") or ""
            # Truncate very long responses for readability
            if len(response_text) > 1000:
                logger.info(f"Response (length: {len(response_text)}):")
                logger.info(response_text[:500] + "\n... [truncated] ...\n" + response_text[-500:])
            else:
                logger.info(f"Response (length: {len(response_text)}):")
                logger.info(response_text)
        
        # Log token usage
        usage = result.get("usage", {})
        if usage:
            logger.info(f"Token Usage: prompt={usage.get('prompt_tokens', 0)}, completion={usage.get('completion_tokens', 0)}, total={usage.get('total_tokens', 0)}")
        logger.info("=" * 80)
        
        return result

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
