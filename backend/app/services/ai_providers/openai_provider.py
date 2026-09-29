"""OpenAI Provider"""
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.logger import get_logger
from app.services.ai_clients.openai_client import OpenAIClient
from .base_provider import BaseAIProvider

logger = get_logger(__name__)


class OpenAIProvider(BaseAIProvider):
    """OpenAI Nhà cung cấp"""

    def __init__(self, client: OpenAIClient):
        self.client = client

    async def generate(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return await self.client.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )

    async def generate_stream(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Nếu có công cụ, dùng gọi công cụ streaming thực sự
        if tools:
            logger.debug(f"🔧 OpenAIProvider: Có {len(tools)} công cụ, xử lý streaming")
            actual_tool_choice = tool_choice if tool_choice else "auto"
            
            tool_calls_buffer = []
            
            async for chunk in self.client.chat_completion_stream(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=actual_tool_choice,
            ):
                # Kiểm tra có gọi công cụ hay không
                if chunk.get("tool_calls"):
                    tool_calls_buffer.extend(chunk["tool_calls"])
                    logger.debug(f"🔧 Nhận gọi công cụ: {len(chunk['tool_calls'])} ")
                
                # Kiểm tra đã kết thúc hay chưa
                if chunk.get("done"):
                    if tool_calls_buffer:
                        logger.info(f"🔧 Streaming kết thúc, xử lý {len(tool_calls_buffer)} lượt gọi công cụ")
                        from app.mcp import mcp_client
                        actual_user_id = user_id or ""
                        tool_results = await mcp_client.batch_call_tools(
                            user_id=actual_user_id,
                            tool_calls=tool_calls_buffer
                        )
                        # Tiêm kết quả công cụ vào ngữ cảnh
                        tool_context = mcp_client.build_tool_context(tool_results, format="markdown")
                        
                        # Xây dựng prompt cuối cùng, yêu cầuAItrả lời dựa trên kết quả công cụ
                        final_prompt = f"{prompt}\n\n{tool_context}\n\nVui lòng dựa trên kết quả truy vấn công cụ ở trên để đưa ra câu trả lời đầy đủ chi tiết."
                        final_messages = messages.copy()
                        final_messages.append({"role": "user", "content": final_prompt})
                        
                        # Gọi đệ quy để tạo kết quả cuối cùng
                        async for final_chunk in self._generate_with_tools(
                            final_messages, model, temperature, max_tokens, tools, user_id
                        ):
                            yield final_chunk
                    if chunk.get("finish_reason"):
                        yield {"finish_reason": chunk.get("finish_reason"), "done": True}
                    break
                
                if chunk.get("usage"):
                    yield {"usage": chunk.get("usage")}

                # Xuất nội dung văn bản
                if chunk.get("content"):
                    yield chunk["content"]
            return
        
        # Tạo streaming thông thường khi không có công cụ
        async for chunk in self.client.chat_completion_stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if isinstance(chunk, dict):
                if chunk.get("usage"):
                    yield {"usage": chunk.get("usage")}
                if chunk.get("finish_reason"):
                    yield {"finish_reason": chunk.get("finish_reason")}
                if chunk.get("content"):
                    yield chunk["content"]
            else:
                yield chunk

    async def _generate_with_tools(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Phương thức hỗ trợ: tạo streaming kèm công cụ (khôngtool_choice,AI, AI tự quyết định)"""
        async for chunk in self.client.chat_completion_stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice="auto",
        ):
            if chunk.get("tool_calls"):
                from app.mcp import mcp_client
                actual_user_id = user_id or ""
                tool_results = await mcp_client.batch_call_tools(
                    user_id=actual_user_id,
                    tool_calls=chunk["tool_calls"]
                )
                tool_context = mcp_client.build_tool_context(tool_results, format="markdown")
                
                # Gọi lại để lấy câu trả lời cuối cùng
                messages.append({"role": "user", "content": f"{tool_context}\n\nVui lòng dựa trên kết quả truy vấn công cụ ở trên để đưa ra câu trả lời đầy đủ chi tiết."})
                
                async for final_chunk in self._generate_with_tools(
                    messages, model, temperature, max_tokens, tools, user_id
                ):
                    yield final_chunk
                break
            
            if chunk.get("done"):
                if chunk.get("finish_reason"):
                    yield {"finish_reason": chunk.get("finish_reason"), "done": True}
                break

            if chunk.get("usage"):
                yield {"usage": chunk.get("usage")}
            
            if chunk.get("content"):
                yield chunk["content"]