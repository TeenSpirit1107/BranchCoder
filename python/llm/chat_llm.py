import json
import os
from typing import Any, Dict, List, Optional, Literal, TypedDict
from openai import AsyncOpenAI
from dotenv import load_dotenv
from utils.logger import Logger

load_dotenv()

logger = Logger('chat_llm', log_to_file=True)

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
            raise ValueError("❌ Missing OPENAI_API_KEY")
        if not model:
            raise ValueError("❌ Missing OPENAI_MODEL")
        if not base_url:
            raise ValueError("❌ Missing OPENAI_BASE_URL")
        if proxy:
            os.environ["HTTP_PROXY"] = proxy
            os.environ["HTTPS_PROXY"] = proxy

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=300.0,
        )
        self.model = model

    async def ask(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0,
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

        # Log LLM request
        logger.info("=" * 80)
        logger.info("LLM Request:")
        logger.info(f"Model: {self.model}")
        logger.info(f"Temperature: {temperature}")
        logger.info(f"Tool Choice: {kwargs.get('tool_choice', 'none')}")
        logger.info(f"Tools Count: {len(tools) if tools else 0}")
        if tools:
            tool_names = [tool.get('function', {}).get('name', 'unknown') for tool in tools if isinstance(tool, dict)]
            logger.info(f"Available Tools: {', '.join(tool_names[:10])}{'...' if len(tool_names) > 10 else ''}")
        
        # Log messages (with truncation for very long messages)
        logger.info(f"Messages Count: {len(messages)}")
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if isinstance(content, str):
                content_preview = content[:200] + "..." if len(content) > 200 else content
                logger.info(f"  Message {i+1} [{role}]: {content_preview}")
            elif isinstance(content, list):
                logger.info(f"  Message {i+1} [{role}]: [Complex content with {len(content)} parts]")
            else:
                logger.info(f"  Message {i+1} [{role}]: [Non-string content]")
        
        logger.info("-" * 80)
        
        completion = await self.client.chat.completions.create(**kwargs)
        result = self._parse_completion(completion)
        
        # Log LLM response
        logger.info("LLM Response:")
        logger.info(f"Type: {result.get('type', 'unknown')}")
        if result.get("type") == "tool_call":
            logger.info(f"Tool Name: {result.get('tool_name', 'unknown')}")
            tool_args = result.get('tool_args', {})
            tool_args_str = json.dumps(tool_args, ensure_ascii=False, indent=2)
            # Truncate very long tool args
            if len(tool_args_str) > 2000:
                logger.info(f"Tool Args (length: {len(tool_args_str)}):")
                logger.info(tool_args_str[:1000] + "\n... [truncated] ...\n" + tool_args_str[-1000:])
            else:
                logger.info(f"Tool Args:")
                logger.info(tool_args_str)
        else:
            response_text = result.get("answer", "") or ""
            # Log full response, but truncate if extremely long
            if len(response_text) > 5000:
                logger.info(f"Response (length: {len(response_text)}):")
                logger.info(response_text[:2500] + "\n... [truncated] ...\n" + response_text[-2500:])
            elif len(response_text) > 1000:
                logger.info(f"Response (length: {len(response_text)}):")
                logger.info(response_text[:500] + "\n... [truncated] ...\n" + response_text[-500:])
            else:
                logger.info(f"Response (length: {len(response_text)}):")
                logger.info(response_text)
        
        # Log token usage
        usage = result.get("usage", {})
        if usage:
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            total_tokens = usage.get('total_tokens', 0)
            logger.info(f"Token Usage: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
        else:
            logger.warning("No token usage information available")
        logger.info("=" * 80)
        
        return result

    def _parse_completion(self, completion: Any) -> CompletionResult:
        choice = completion.choices[0]
        message = choice.message

        # token 统计
        usage = getattr(completion, "usage", None)
        if usage:
            # usage 可能是 Pydantic 对象或字典
            if hasattr(usage, "prompt_tokens"):
                # Pydantic 对象，使用 getattr
                usage_dict = {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                }
            else:
                # 字典对象，使用 .get()
                usage_dict = {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                }
        else:
            # 没有 usage 信息
            usage_dict = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
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
