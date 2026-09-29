"""Anthropic client"""
from typing import Any, AsyncGenerator, Dict, Optional

from anthropic import AsyncAnthropic

from app.logger import get_logger
from app.services.ai_config import AIClientConfig, default_config

logger = get_logger(__name__)


class AnthropicClient:
    """Anthropic API client"""

    def __init__(self, api_key: str, base_url: Optional[str] = None, config: Optional[AIClientConfig] = None):
        self.config = config or default_config
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncAnthropic(**kwargs)

    @staticmethod
    def _convert_tools(tools: list) -> list:
        """Đồng thời chấp nhận định dạng OpenAI function tool chung trong dự án. OpenAI function tool định dạng."""
        converted = []
        for tool in tools:
            function = tool.get("function") if isinstance(tool, dict) else None
            if function:
                converted.append({
                    "name": function.get("name"),
                    "description": function.get("description", ""),
                    "input_schema": function.get("parameters") or {
                        "type": "object",
                        "properties": {},
                    },
                })
            else:
                converted.append(tool)
        return converted

    async def chat_completion(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str] = None,
        tools: Optional[list] = None,
        tool_choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
            if tool_choice == "required":
                kwargs["tool_choice"] = {"type": "any"}
            elif tool_choice == "auto":
                kwargs["tool_choice"] = {"type": "auto"}

        response = await self.client.messages.create(**kwargs)

        tool_calls = []
        content = ""
        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {"name": block.name, "arguments": block.input},
                })
            elif block.type == "text":
                content += block.text

        usage = getattr(response, "usage", None)
        return {
            "content": content,
            "tool_calls": tool_calls if tool_calls else None,
            "finish_reason": response.stop_reason,
            "usage": {
                "prompt_tokens": getattr(usage, "input_tokens", None),
                "completion_tokens": getattr(usage, "output_tokens", None),
                "total_tokens": (
                    (getattr(usage, "input_tokens", 0) or 0) +
                    (getattr(usage, "output_tokens", 0) or 0)
                ) if usage else None,
            },
        }

    async def chat_completion_stream(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str] = None,
        tools: Optional[list] = None,
        tool_choice: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Tạo streaming, hỗ trợ gọi công cụ
        
        Yields:
            Dict with keys:
            - content: str - khối nội dung văn bản
            - tool_calls: list - danh sách gọi công cụ (nếu có)
            - done: bool - đã kết thúc hay chưa
        """
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
            if tool_choice == "required":
                kwargs["tool_choice"] = {"type": "any"}
            elif tool_choice == "auto":
                kwargs["tool_choice"] = {"type": "auto"}

        try:
            async with self.client.messages.stream(**kwargs) as stream:
                try:
                    tool_calls = []
                    async for chunk in stream:
                        # Xử lý các loại block khác nhau
                        if chunk.type == "text_delta":
                            yield {"content": chunk.text}
                        elif chunk.type == "tool_use_delta":
                            # Phần tăng thêm của gọi công cụ
                            if not tool_calls or tool_calls[-1].get("id") != chunk.id:
                                tool_calls.append({
                                    "id": chunk.id,
                                    "type": "function",
                                    "function": {
                                        "name": chunk.name,
                                        "arguments": ""
                                    }
                                })
                            # Thêm tham số
                            if tool_calls[-1]["function"]["arguments"] is None:
                                tool_calls[-1]["function"]["arguments"] = ""
                            tool_calls[-1]["function"]["arguments"] += chunk.input_gets_new_text or ""
                        elif chunk.type == "message_delta":
                            if chunk.stop_reason:
                                # Luồng kết thúc
                                if tool_calls:
                                    yield {"tool_calls": tool_calls}
                                yield {"done": True, "finish_reason": chunk.stop_reason}
                except GeneratorExit:
                    # Generator bị đóng, đây là quá trình dọn dẹp bình thường
                    logger.debug("Anthropic Generator phản hồi streaming của Anthropic bị đóng(GeneratorExit)")
                    raise
                except Exception as iter_error:
                    logger.error(f"Anthropic Lặp phản hồi streaming của Anthropic bị lỗi: {str(iter_error)}")
                    raise
        except GeneratorExit:
            # Ném lạiGeneratorExit, để bên gọi xử lý
            raise
        except Exception as e:
            logger.error(f"Anthropic Yêu cầu streaming của Anthropic bị lỗi: {str(e)}")
            raise
