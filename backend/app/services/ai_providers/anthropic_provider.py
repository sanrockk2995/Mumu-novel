"""Anthropic Provider"""
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.logger import get_logger
from app.services.ai_clients.anthropic_client import AnthropicClient
from .base_provider import BaseAIProvider

logger = get_logger(__name__)


class AnthropicProvider(BaseAIProvider):
    """Nhà cung cấp Anthropic"""

    def __init__(self, client: AnthropicClient):
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
        messages = [{"role": "user", "content": prompt}]
        return await self.client.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
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
        # Nếu có tool, dùng gọi tool streaming thực sự
        if tools:
            logger.debug(f"🔧 AnthropicProvider: có {len(tools)} tool, dùng xử lý streaming")
            messages = [{"role": "user", "content": prompt}]
            actual_tool_choice = tool_choice if tool_choice else "auto"
            
            tool_calls_buffer = []
            
            async for chunk in self.client.chat_completion_stream(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                tools=tools,
                tool_choice=actual_tool_choice,
            ):
                # Kiểm tra có gọi tool không
                if chunk.get("tool_calls"):
                    tool_calls_buffer.extend(chunk["tool_calls"])
                    logger.debug(f"🔧 Nhận được gọi tool: {len(chunk['tool_calls'])} cái")

                # Kiểm tra đã kết thúc chưa
                if chunk.get("done"):
                    if tool_calls_buffer:
                        logger.info(f"🔧 Streaming kết thúc, xử lý {len(tool_calls_buffer)} gọi tool")
                        from app.mcp import mcp_client
                        actual_user_id = user_id or ""
                        tool_results = await mcp_client.batch_call_tools(
                            user_id=actual_user_id,
                            tool_calls=tool_calls_buffer
                        )
                        # Đưa kết quả tool vào context
                        tool_context = mcp_client.build_tool_context(tool_results, format="markdown")

                        # Xây dựng prompt cuối, yêu cầu AI trả lời dựa trên kết quả tool
                        final_prompt = f"{prompt}\n\n{tool_context}\n\nHãy dựa trên kết quả truy vấn tool ở trên để đưa ra câu trả lời đầy đủ chi tiết."
                        final_messages = [{"role": "user", "content": final_prompt}]
                        
                        # Gọi đệ quy để sinh kết quả cuối
                        async for final_chunk in self._generate_with_tools(
                            final_messages, model, temperature, max_tokens, system_prompt, tools, user_id
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

        # Không có tool thì sinh streaming thông thường
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self.client.chat_completion_stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
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
        system_prompt: Optional[str] = None,
        tools: list = None,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Phương thức hỗ trợ: sinh streaming có tool"""
        tool_calls_buffer = []
        
        async for chunk in self.client.chat_completion_stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            tools=tools,
            tool_choice="auto",
        ):
            if chunk.get("tool_calls"):
                tool_calls_buffer.extend(chunk["tool_calls"])
                logger.debug(f"🔧 _generate_with_tools nhận được gọi tool: {len(chunk['tool_calls'])} cái")
            
            if chunk.get("done"):
                if tool_calls_buffer:
                    from app.mcp import mcp_client
                    actual_user_id = user_id or ""
                    tool_results = await mcp_client.batch_call_tools(
                        user_id=actual_user_id,
                        tool_calls=tool_calls_buffer
                    )
                    tool_context = mcp_client.build_tool_context(tool_results, format="markdown")
                    
                    messages.append({"role": "user", "content": f"{tool_context}\n\nHãy dựa trên kết quả truy vấn tool ở trên để đưa ra câu trả lời đầy đủ chi tiết."})
                    
                    async for final_chunk in self._generate_with_tools(
                        messages, model, temperature, max_tokens, system_prompt, tools, user_id
                    ):
                        yield final_chunk
                if chunk.get("finish_reason"):
                    yield {"finish_reason": chunk.get("finish_reason"), "done": True}
                break

            if chunk.get("usage"):
                yield {"usage": chunk.get("usage")}
            
            if chunk.get("content"):
                yield chunk["content"]