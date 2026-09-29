"""Gemini client"""
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx
from app.services.ai_config import AIClientConfig, default_config
from app.logger import get_logger

logger = get_logger(__name__)


class GeminiClient:
    """Google Gemini API client"""

    def __init__(self, api_key: str, base_url: Optional[str] = None, config: Optional[AIClientConfig] = None):
        self.api_key = api_key
        self.base_url = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        self.config = config or default_config
        http_cfg = self.config.http
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=http_cfg.connect_timeout,
                read=http_cfg.read_timeout,
                write=http_cfg.write_timeout,
                pool=http_cfg.pool_timeout
            )
        )

    @classmethod
    def _convert_schema_to_gemini(cls, schema: dict) -> dict:
        converted = {}
        for key, value in schema.items():
            if key in {"$schema", "additionalProperties"}:
                continue
            if key == "type" and isinstance(value, list):
                non_null = [item for item in value if item != "null"]
                converted["type"] = non_null[0] if non_null else "string"
                if "null" in value:
                    converted["nullable"] = True
                continue
            if isinstance(value, dict):
                converted[key] = cls._convert_schema_to_gemini(value)
            elif isinstance(value, list):
                converted[key] = [
                    cls._convert_schema_to_gemini(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                converted[key] = value
        return converted

    def _convert_tools_to_gemini(self, tools: list) -> list:
        """Chuyển tool định dạng OpenAI sang định dạng Gemini"""
        gemini_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                params = self._convert_schema_to_gemini(func.get("parameters", {})) if func.get("parameters") else {}
                if params and "type" not in params:
                    params["type"] = "object"
                decl = {
                    "name": func["name"],
                    "description": func.get("description") or func["name"],
                }
                if params:
                    decl["parameters"] = params
                gemini_tools.append(decl)
        return [{"functionDeclarations": gemini_tools}] if gemini_tools else []

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
        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
        
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        
        payload = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if tools:
            payload["tools"] = self._convert_tools_to_gemini(tools)

        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        candidates = data.get("candidates", [])
        if not candidates or len(candidates) == 0:
            # Trả về nội dung rỗng thay vì báo lỗi, để luồng tiếp tục
            return {
                "content": "",
                "tool_calls": None,
                "finish_reason": "stop"
            }
        
        parts = candidates[0].get("content", {}).get("parts", [])
        text = ""
        tool_calls = []
        
        for part in parts:
            if "text" in part:
                text += part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append({
                    "id": f"call_{fc['name']}",
                    "type": "function",
                    "function": {"name": fc["name"], "arguments": fc.get("args", {})}
                })
        
        usage = data.get("usageMetadata") or {}
        prompt_tokens = usage.get("promptTokenCount")
        completion_tokens = usage.get("candidatesTokenCount")
        total_tokens = usage.get("totalTokenCount")
        return {
            "content": text,
            "tool_calls": tool_calls if tool_calls else None,
            "finish_reason": "tool_calls" if tool_calls else "stop",
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
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
        Sinh streaming, hỗ trợ gọi tool

        Yields:
            Dict with keys:
            - content: str - block nội dung văn bản
            - tool_calls: list - danh sách gọi tool (nếu có)
            - done: bool - đã kết thúc hay chưa
        """
        url = f"{self.base_url}/models/{model}:streamGenerateContent?key={self.api_key}&alt=sse"
        
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        
        payload = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if tools:
            payload["tools"] = self._convert_tools_to_gemini(tools)

        try:
            async with self.client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                try:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            import json
                            try:
                                data = json.loads(line[6:])
                                usage = data.get("usageMetadata") or {}
                                if usage:
                                    yield {
                                        "usage": {
                                            "prompt_tokens": usage.get("promptTokenCount"),
                                            "completion_tokens": usage.get("candidatesTokenCount"),
                                            "total_tokens": usage.get("totalTokenCount"),
                                        }
                                    }
                                candidates = data.get("candidates", [])
                                if candidates and len(candidates) > 0:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    if parts and len(parts) > 0:
                                        text = ""
                                        function_calls = []
                                        for part in parts:
                                            if "text" in part:
                                                text += part["text"]
                                            elif "functionCall" in part:
                                                fc = part["functionCall"]
                                                function_calls.append({
                                                    "id": f"call_{fc['name']}",
                                                    "type": "function",
                                                    "function": {
                                                        "name": fc["name"],
                                                        "arguments": fc.get("args", {})
                                                    }
                                                })
                                        
                                        if text:
                                            yield {"content": text}
                                        if function_calls:
                                            yield {"tool_calls": function_calls}
                            except json.JSONDecodeError:
                                continue
                except GeneratorExit:
                    # Generator bị đóng, đây là quá trình dọn dẹp bình thường
                    logger.debug("Gemini generator response streaming bị đóng (GeneratorExit)")
                    raise
                except Exception as iter_error:
                    logger.error(f"Lỗi khi lặp response streaming Gemini: {str(iter_error)}")
                    raise
        except GeneratorExit:
            # Ném lại GeneratorExit để phía gọi xử lý
            raise
        except Exception as e:
            logger.error(f"Lỗi request streaming Gemini: {str(e)}")
            raise
