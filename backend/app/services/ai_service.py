"""Đóng gói dịch vụ AI - giao diện AI thống nhất

Sau khi tái cấu trúc hỗ trợ tự động tải công cụ MCP:
- Mọi phương thức AI đều tự động kiểm tra cấu hình MCP của người dùng trước khi gửi yêu cầu
- Nếu có plugin MCP đang bật và có công cụ khả dụng, tự động gửi tools
- thông qua auto_mcp Tham số điều khiển có bật tự động tải công cụ không
"""
from typing import Optional, AsyncGenerator, List, Dict, Any, Union

from app.config import settings as app_settings
from app.logger import get_logger
from app.services.ai_config import AIClientConfig, default_config
from app.services.ai_metrics import AICallMetrics, TokenUsage, ToolCallMetrics
from app.services.ai_clients.openai_client import OpenAIClient
from app.services.ai_clients.anthropic_client import AnthropicClient
from app.services.ai_clients.gemini_client import GeminiClient
from app.services.ai_clients.base_client import cleanup_all_clients
from app.services.ai_providers.openai_provider import OpenAIProvider
from app.services.ai_providers.anthropic_provider import AnthropicProvider
from app.services.ai_providers.gemini_provider import GeminiProvider
from app.services.ai_providers.base_provider import BaseAIProvider
from app.services.json_helper import clean_json_response, parse_json

# Xuất hàm dọn dẹp
cleanup_http_clients = cleanup_all_clients

logger = get_logger(__name__)


def normalize_provider(provider: Optional[str]) -> Optional[str]:
    """Chuẩn hóa provider tên, tương thích OpenAI bí danh kênh định dạng.

    Bộ điều hợp tích hợp (ví dụ Xiaomi MiMo) nên được phân giải ở tầng API thành provider,
    AIService tương thích ở tầng dưới, chỉ nhận provider.
    """
    if provider is None:
        return None

    normalized = provider.lower().strip()
    if normalized == "mumu":
        return "openai"
    return normalized


class AIService:
    """
    AIGiao diện thống nhất của dịch vụ
    
    MCPHỗ trợ công cụ:
    - Truyền vào khi tạo dịch vụ user_id và db_session
    - TheoMCPcủa người dùngenabledtrạng thái plugin tự động quyết định có bật khôngMCP
    - Nếu có bất kỳ mộtMCPplugin nào được bật, thì tải và dùng công cụ
    - Nếu mọi plugin đều tắt, thì không dùng bất kỳMCPcông cụ
    - thông qua auto_mcp=False Có thể tạm thời tắt tự động tải công cụ
    - thông qua mcp_max_rounds Điều khiển số vòng gọi công cụ
    - thông qua clear_mcp_cache() Có thể dọn dẹpMCPcông cụbộ nhớ đệm
    
    MCPLogic bật (backend/app/api/settings.py trong get_user_ai_service):
    - Truy vấn mọiMCPplugin
    - Nếu có plugin đang bật (enabled=True), thì enable_mcp=True
    - Nếu mọi plugin đều tắt hoặc không có plugin, thì enable_mcp=False
    
    Ví dụ dùng:
        # Tạo dịch vụ AI hỗ trợ MCP (tự động quyết định bật/tắt theo trạng thái plugin)
        ai_service = create_user_ai_service_with_mcp(
            api_provider="openai",
            api_key="...",
            user_id="user123",
            db_session=db
        )
        
        # tự độngtảiMCPcông cụ (nếu có plugin đang bật)
        result = await ai_service.generate_text(prompt="...")
        
        # Tạm thời tắtMCPcông cụ
        result = await ai_service.generate_text(prompt="...", auto_mcp=False)
        
        # Số vòng tùy chỉnh
        result = await ai_service.generate_text(prompt="...", mcp_max_rounds=3)
    """

    def __init__(
        self,
        api_provider: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        default_temperature: Optional[float] = None,
        default_max_tokens: Optional[int] = None,
        default_system_prompt: Optional[str] = None,
        config: Optional[AIClientConfig] = None,
        # MCPTham số hỗ trợ
        user_id: Optional[str] = None,
        db_session: Optional[Any] = None,
        enable_mcp: bool = True,
        disable_thinking: bool = False,
    ):
        self.raw_api_provider = (api_provider or app_settings.default_ai_provider or "openai").lower().strip()
        self.api_provider = normalize_provider(self.raw_api_provider)
        self.default_model = default_model or app_settings.default_model
        self.default_temperature = default_temperature or app_settings.default_temperature
        self.default_max_tokens = default_max_tokens or app_settings.default_max_tokens
        self.default_system_prompt = default_system_prompt
        self.config = config or default_config
        
        # MCPcấu hình
        self.user_id = user_id
        self.db_session = db_session
        self._enable_mcp = enable_mcp
        # Tắt suy nghĩ (vLLM/Qwen mô hình suy nghĩ tương tự): thông qua chat_template_kwargs tiêm
        self.disable_thinking = disable_thinking
        self._cached_tools: Optional[List[Dict]] = None
        self._tools_loaded = False
        
        self._openai_provider: Optional[OpenAIProvider] = None
        self._anthropic_provider: Optional[AnthropicProvider] = None
        self._gemini_provider: Optional[GeminiProvider] = None
        
        # khởi tạo OpenAI Giao diện tương thích
        openai_key = None
        openai_base_url = None
        if self.api_provider == "openai":
            openai_key = api_key or app_settings.openai_api_key
            openai_base_url = api_base_url or app_settings.openai_base_url
        else:
            openai_key = app_settings.openai_api_key
            openai_base_url = app_settings.openai_base_url

        if openai_key:
            # Tắt suy nghĩ: vLLM Cách viết chuẩn, không hỗ trợ trường này sẽ bỏ qua OpenAI phía máy chủ tương thích
            openai_extra_body = (
                {"chat_template_kwargs": {"enable_thinking": False}}
                if disable_thinking else None
            )
            client = OpenAIClient(openai_key, openai_base_url or "https://api.openai.com/v1", self.config, extra_body=openai_extra_body)
            self._openai_provider = OpenAIProvider(client)
        
        # khởi tạo Anthropic
        anthropic_key = api_key if self.api_provider == "anthropic" else app_settings.anthropic_api_key
        if anthropic_key:
            base_url = api_base_url if self.api_provider == "anthropic" else app_settings.anthropic_base_url
            client = AnthropicClient(anthropic_key, base_url, self.config)
            self._anthropic_provider = AnthropicProvider(client)
        
        # khởi tạo Gemini
        if self.api_provider == "gemini" and api_key:
            client = GeminiClient(api_key, api_base_url, self.config)
            self._gemini_provider = GeminiProvider(client)

    @property
    def enable_mcp(self) -> bool:
        """có hay khôngbậtMCPcông cụ"""
        return self._enable_mcp
    
    @enable_mcp.setter
    def enable_mcp(self, value: bool):
        """cài đặtMCPtrạng thái bật, nếu tắt thì dọn bộ nhớ đệm"""
        if value is False and self._enable_mcp is True:
            # Chuyển từ bật sang tắt, dọn bộ nhớ đệm
            self.clear_mcp_cache()
        self._enable_mcp = value
    
    def clear_mcp_cache(self):
        """
        dọn dẹpMCPcông cụbộ nhớ đệm
        
        Khi tắtMCPgọi phương thức này, đảm bảo các lần gọi sauAIkhông dùng công cụ đã lưu trong bộ nhớ đệm.
        Đồng thời cập nhật _tools_loaded trạng thái, để lần gọi sau kiểm tra lại.
        """
        if self._cached_tools is not None:
            logger.info(f"🔧 dọn dẹpMCPbộ nhớ đệm công cụ, loại bỏ {len(self._cached_tools)} công cụ")
            self._cached_tools = None
        else:
            logger.debug(f"🔧 MCPBộ nhớ đệm công cụ đã trống, không cần dọn")
        
        # Cập nhật trạng thái tải, đảm bảo lần gọi sau sẽ kiểm tra lại
        self._tools_loaded = False
        logger.debug(f"🔧 MCPTrạng thái công cụ đã được đặt lại: enable_mcp={self._enable_mcp}, _tools_loaded=False")
    
    def _get_provider(self, provider: Optional[str] = None) -> BaseAIProvider:
        """Lấy Provider"""
        p = normalize_provider(provider or self.api_provider)
        if p == "openai" and self._openai_provider:
            return self._openai_provider
        if p == "anthropic" and self._anthropic_provider:
            return self._anthropic_provider
        if p == "gemini" and self._gemini_provider:
            return self._gemini_provider
        raise ValueError(f"Provider {p} chưa khởi tạo")

    def _build_call_metrics(
        self,
        *,
        request_mode: str,
        provider: Optional[str],
        model: Optional[str],
        prompt: str,
        auto_mcp: bool,
        tools_count: int,
        stream: bool,
    ) -> AICallMetrics:
        return AICallMetrics(
            request_mode=request_mode,
            provider=normalize_provider(provider or self.api_provider) or "unknown",
            model=model or self.default_model,
            user_id=self.user_id,
            stream=stream,
            auto_mcp=auto_mcp,
            tools_count=tools_count,
            prompt_length=len(prompt or ""),
        )

    def _log_call_metrics(self, metrics: AICallMetrics, title: Optional[str] = None):
        log_title = title or ("AIGọi hoàn tất" if metrics.success else "AIgọithất bại")
        message = metrics.to_log_message(log_title)
        if metrics.success:
            logger.info(message)
        else:
            logger.error(message)

    async def _prepare_mcp_tools(self, auto_mcp: bool = True, force_refresh: bool = False) -> Optional[List[Dict]]:
        """
        Tiền xử lýMCPcông cụ
        
        Kiểm tra người dùngMCPcấu hình và tải các công cụ khả dụng.
        Kết quả sẽ được lưu đệm, tránh tải lặp lại.
        
        Args:
            auto_mcp: Có tự động tải khôngMCPcông cụ (từ tham số của bên gọi)
            force_refresh: Có buộc làm mới bộ nhớ đệm không
            
        Returns:
            - None: Không có công cụ khả dụng (chưa cấu hình/chưa bật/tải thất bại)
            - List[Dict]: Danh sách công cụ định dạng OpenAI
        """
        # Kiểm tra điều kiện tiên quyết
        if not self._enable_mcp:
            logger.debug(f"🔧 Công cụ MCP chưa bật (_enable_mcp=False)")
            # Dù có bộ nhớ đệm cũng dọn sạch, đảm bảo không dùng
            self._cached_tools = None
            self._tools_loaded = False
            return None
        
        if not auto_mcp:
            logger.debug(f"🔧 auto_mcp=False, bỏ qua tải công cụ MCP")
            # Dù có bộ nhớ đệm cũng dọn sạch, đảm bảo không dùng
            self._cached_tools = None
            self._tools_loaded = False
            return None
        
        if not self.user_id:
            logger.debug(f"🔧 Bỏ qua tải công cụ MCP: user_id chưa thiết lập")
            return None
        
        if not self.db_session:
            logger.debug(f"🔧 Bỏ qua tải công cụ MCP: db_session chưa thiết lập")
            return None
        
        # Dùng bộ nhớ đệm (chỉ khi enable_mcp=True mới dùng bộ nhớ đệm)
        if self._tools_loaded and not force_refresh:
            if self._cached_tools:
                logger.debug(f"🔧 Dùng bộ nhớ đệmMCPcông cụ ({len(self._cached_tools)})")
            return self._cached_tools
        
        try:
            from app.services.mcp_tools_loader import mcp_tools_loader
            
            self._cached_tools = await mcp_tools_loader.get_user_tools(
                user_id=self.user_id,
                db_session=self.db_session,
                use_cache=True,
                force_refresh=force_refresh
            )
            self._tools_loaded = True
            
            if self._cached_tools:
                logger.info(f"🔧 đã tải {len(self._cached_tools)} MCPcông cụ")
            else:
                logger.debug(f"📭 người dùng {self.user_id} Không cóMCPcông cụ")
            
            return self._cached_tools
            
        except Exception as e:
            logger.warning(f"⚠️ tảiMCPcông cụ thất bại: {e}")
            self._tools_loaded = True
            self._cached_tools = None
            return None

    async def _handle_tool_calls(
        self,
        original_prompt: str,
        response: Dict[str, Any],
        max_rounds: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """
        xử lýAIgọi công cụ trả về
        
        Args:
            original_prompt: Prompt gốc
            response: AIphản hồi (bao gồmtool_calls)
            max_rounds: Số vòng gọi công cụ tối đa
            **kwargs: Truyền chogenerate_textcác tham số khác
            
        Returns:
            cuối cùngAIphản hồi
        """
        from app.mcp import mcp_client
        
        tool_calls = response.get("tool_calls", [])
        if not tool_calls or not self.user_id:
            return response

        tool_metrics = ToolCallMetrics()
        tool_metrics.usage.add(TokenUsage.from_response(response))
        
        result = {
            "content": response.get("content", ""),
            "tool_calls_made": 0,
            "tools_used": [],
            "finish_reason": response.get("finish_reason", ""),
            "mcp_enhanced": True,
            "usage": response.get("usage"),
        }
        
        prompt = original_prompt
        
        for round_num in range(max_rounds):
            logger.info(f"🔧 Gọi công cụ - vòng {round_num+1}/{max_rounds}, {len(tool_calls)} công cụ")
            tool_metrics.mcp_rounds += 1
            
            try:
                # Thực thi hàng loạt gọi công cụ
                tool_results = await mcp_client.batch_call_tools(
                    user_id=self.user_id,
                    tool_calls=tool_calls
                )
                
                # Ghi nhận công cụ đã dùng
                for tc in tool_calls:
                    name = tc["function"]["name"]
                    tool_metrics.add_tool_name(name)
                    if name not in result["tools_used"]:
                        result["tools_used"].append(name)
                result["tool_calls_made"] += len(tool_calls)
                tool_metrics.tool_calls_count += len(tool_calls)
                
                # Xây dựng ngữ cảnh công cụ
                tool_context = mcp_client.build_tool_context(tool_results, format="markdown")
                
                # Cập nhật prompt
                if round_num == max_rounds - 1:
                    # Vòng cuối cùng, bắt buộc phải trả lời
                    prompt = f"{original_prompt}\n\n{tool_context}\n\n⚠️ Quan trọng: dựa trên kết quả truy vấn công cụ ở trên, đưa ra câu trả lời cuối cùng đầy đủ chi tiết. Không gọi thêm công cụ nữa."
                    tool_choice = "none"
                else:
                    prompt = f"{original_prompt}\n\n{tool_context}\n\nVui lòng dựa trên kết quả truy vấn công cụ ở trên để tiếp tục hoàn thành nhiệm vụ."
                    tool_choice = kwargs.get("tool_choice", "auto")
                
                # Tiếp tục gọiAI
                prov = self._get_provider(kwargs.get("provider"))
                next_response = await prov.generate(
                    prompt=prompt,
                    model=kwargs.get("model") or self.default_model,
                    temperature=kwargs.get("temperature") or self.default_temperature,
                    max_tokens=kwargs.get("max_tokens") or self.default_max_tokens,
                    system_prompt=kwargs.get("system_prompt") or self.default_system_prompt,
                    tools=None if tool_choice == "none" else self._cached_tools,
                    tool_choice=tool_choice,
                )
                tool_metrics.usage.add(TokenUsage.from_response(next_response))
                
                tool_calls = next_response.get("tool_calls", [])
                
                if not tool_calls:
                    # Không còn gọi công cụ nào, trả về kết quả
                    result["content"] = next_response.get("content", "")
                    result["finish_reason"] = next_response.get("finish_reason", "stop")
                    result["usage"] = {
                        "prompt_tokens": tool_metrics.usage.prompt_tokens,
                        "completion_tokens": tool_metrics.usage.completion_tokens,
                        "total_tokens": tool_metrics.usage.total_tokens,
                    }
                    break
                    
            except Exception as e:
                logger.error(f"❌ Gọi công cụthất bại: {e}")
                tool_metrics.tool_error_count += 1
                result["content"] = response.get("content", "")
                result["finish_reason"] = "tool_error"
                result["usage"] = {
                    "prompt_tokens": tool_metrics.usage.prompt_tokens,
                    "completion_tokens": tool_metrics.usage.completion_tokens,
                    "total_tokens": tool_metrics.usage.total_tokens,
                }
                break

        result["__tool_metrics"] = tool_metrics
        
        return result

    async def generate_text(
        self,
        prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        auto_mcp: bool = True,
        handle_tool_calls: bool = True,
        mcp_max_rounds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Tạo văn bản (tự động hỗ trợMCPcông cụ)
        
        Args:
            prompt: Prompt người dùng
            provider: AINhà cung cấp
            model: Tên mô hình
            temperature: nhiệt độ
            max_tokens: Số token tối đa
            system_prompt: Prompt hệ thống
            tools: Danh sách công cụ chỉ định thủ công (ưu tiên cao hơn tự động tải)
            tool_choice: Chiến lược chọn công cụ
            auto_mcp: Có tự động tải khôngMCPcông cụ (mặc địnhTrue)
            handle_tool_calls: Có tự động xử lý gọi công cụ không (mặc địnhTrue)
            mcp_max_rounds: Số vòng gọi công cụ tối đa(NoneDùng giá trị mặc định3)
            
        Returns:
            Dict chứa nội dung đã tạo
        """
        # DùngMCPsố vòng của cấu hình toàn cục (nếu chưa chỉ định)
        if mcp_max_rounds is None:
            mcp_max_rounds = app_settings.mcp_max_rounds
        
        # tự độngtảiMCPcông cụ
        if auto_mcp and tools is None:
            tools = await self._prepare_mcp_tools(auto_mcp=auto_mcp)

        metrics = self._build_call_metrics(
            request_mode="văn bản",
            provider=provider,
            model=model,
            prompt=prompt,
            auto_mcp=auto_mcp,
            tools_count=len(tools) if tools else 0,
            stream=False,
        )
        
        try:
            prov = self._get_provider(provider)
            response = await prov.generate(
                prompt=prompt,
                model=model or self.default_model,
                temperature=temperature or self.default_temperature,
                max_tokens=max_tokens or self.default_max_tokens,
                system_prompt=system_prompt or self.default_system_prompt,
                tools=tools,
                tool_choice=tool_choice,
            )
            usage = TokenUsage.from_response(response)
            
            # Xử lý gọi công cụ
            if handle_tool_calls and response.get("tool_calls"):
                response = await self._handle_tool_calls(
                    original_prompt=prompt,
                    response=response,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                    tool_choice=tool_choice,
                    max_rounds=mcp_max_rounds,
                )
                usage = TokenUsage.from_response(response)
                tool_metrics = response.get("__tool_metrics")
                if tool_metrics:
                    metrics.merge_tool_metrics(tool_metrics)

            metrics.finish(
                success=True,
                response_length=len(response.get("content", "") or ""),
                finish_reason=response.get("finish_reason"),
                usage=usage,
            )
            self._log_call_metrics(metrics)
            return response
        except Exception as e:
            metrics.finish(success=False, error=e)
            self._log_call_metrics(metrics)
            raise

    async def generate_text_stream(
        self,
        prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        tool_choice: Optional[str] = None,
        auto_mcp: bool = True,
        mcp_max_rounds: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Tạo văn bản streaming (tự động hỗ trợ công cụ MCP)
        
        Việc gọi công cụ được xử lý ở tầng Provider bằng streaming, hỗ trợ gọi công cụ streaming thực sự.
        
        Args:
            prompt: Prompt người dùng
            provider: AINhà cung cấp
            model: Tên mô hình
            temperature: nhiệt độ
            max_tokens: Số token tối đa
            system_prompt: Prompt hệ thống
            tool_choice: Chiến lược chọn công cụ ("auto"/"none"/"required")
            auto_mcp: Có tự động tải khôngMCPcông cụ
            mcp_max_rounds: Số vòng gọi công cụ tối đa(NoneDùng giá trị mặc định3)
            
        Yields:
            khối văn bản đã tạo
        """
        logger.debug(f"🔧 generate_text_stream: auto_mcp={auto_mcp}, tool_choice={tool_choice}")
        
        tools_to_use = None
        
        # tảiMCPcông cụ
        if auto_mcp:
            tools_to_use = await self._prepare_mcp_tools(auto_mcp=auto_mcp)
            if tools_to_use:
                logger.info(f"🔧 Đã lấy {len(tools_to_use)} MCPcông cụ")

        metrics = self._build_call_metrics(
            request_mode="Văn bản streaming",
            provider=provider,
            model=model,
            prompt=prompt,
            auto_mcp=auto_mcp,
            tools_count=len(tools_to_use) if tools_to_use else 0,
            stream=True,
        )
        response_parts: List[str] = []
        latest_usage = TokenUsage()
        finish_reason = "stop"
        
        try:
            # Tạo streaming (Provider tầng xử lý gọi công cụ)
            prov = self._get_provider(provider)
            logger.debug(f"🔧 Bắt đầu tạo streaming,provider={provider or self.api_provider}, tools_count={len(tools_to_use) if tools_to_use else 0}")
            async for chunk in prov.generate_stream(
                prompt=prompt,
                model=model or self.default_model,
                temperature=temperature or self.default_temperature,
                max_tokens=max_tokens or self.default_max_tokens,
                system_prompt=system_prompt or self.default_system_prompt,
                tools=tools_to_use,
                tool_choice=tool_choice,
                user_id=self.user_id,
            ):
                if isinstance(chunk, dict):
                    if chunk.get("usage"):
                        latest_usage = TokenUsage.from_response({"usage": chunk.get("usage")})
                    if chunk.get("finish_reason"):
                        finish_reason = chunk.get("finish_reason") or finish_reason
                    continue

                if chunk:
                    metrics.mark_first_chunk()
                    metrics.chunk_count += 1
                    response_parts.append(chunk)
                yield chunk

            metrics.finish(
                success=True,
                response_length=len("".join(response_parts)),
                finish_reason=finish_reason,
                usage=latest_usage,
            )
            self._log_call_metrics(metrics)
        except Exception as e:
            metrics.finish(
                success=False,
                response_length=len("".join(response_parts)),
                finish_reason=finish_reason,
                usage=latest_usage,
                error=e,
            )
            self._log_call_metrics(metrics)
            raise

    async def call_with_json_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        expected_type: Optional[str] = None,
        auto_mcp: bool = True,
    ) -> Union[Dict, List]:
        """
        có thử lại JSON gọi (tự động hỗ trợMCPcông cụ)
        
        Args:
            prompt: Prompt người dùng
            system_prompt: Prompt hệ thống
            max_retries: Số lần thử lại tối đa
            temperature: nhiệt độ
            max_tokens: Số token tối đa
            provider: AINhà cung cấp
            model: Tên mô hình
            expected_type: Kiểu trả về mong muốn ("object"hoặc"array")
            auto_mcp: Có tự động tải khôngMCPcông cụ
            
        Returns:
            sau phân tíchJSONdữ liệu
        """
        last_response = ""
        aggregate_usage = TokenUsage()
        metrics = self._build_call_metrics(
            request_mode="JSONthử lại",
            provider=provider,
            model=model,
            prompt=prompt,
            auto_mcp=auto_mcp,
            tools_count=0,
            stream=False,
        )
        
        try:
            for attempt in range(1, max_retries + 1):
                current_prompt = prompt if attempt == 1 else self._add_json_hint(prompt, last_response, attempt)
                
                result = await self.generate_text(
                    prompt=current_prompt,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                    auto_mcp=auto_mcp,
                    handle_tool_calls=True,
                )
                aggregate_usage.add(TokenUsage.from_response(result))
                metrics.retry_count = attempt
                metrics.tools_count = max(metrics.tools_count, len(self._cached_tools) if self._cached_tools else 0)
                
                last_response = result.get("content", "")
                
                try:
                    data = parse_json(last_response)
                    if expected_type == "object" and not isinstance(data, dict):
                        raise ValueError("mong muốn object")
                    if expected_type == "array" and not isinstance(data, list):
                        raise ValueError("mong muốn array")
                    metrics.json_parse_success = True
                    metrics.finish(
                        success=True,
                        response_length=len(last_response),
                        finish_reason=result.get("finish_reason"),
                        usage=aggregate_usage,
                    )
                    self._log_call_metrics(metrics, title="AITóm tắt gọi")
                    return data
                except Exception as e:
                    metrics.json_parse_success = False
                    if attempt == max_retries:
                        raise ValueError(f"JSON Phân tích thất bại: {e}")
            
            raise ValueError("JSON gọithất bại")
        except Exception as e:
            metrics.finish(
                success=False,
                response_length=len(last_response),
                usage=aggregate_usage,
                error=e,
            )
            self._log_call_metrics(metrics, title="AITóm tắt gọi")
            raise

    @staticmethod
    def _add_json_hint(prompt: str, failed: str, attempt: int) -> str:
        return f"{prompt}\n\n⚠️ Lần thử lại thứ {attempt}, vui lòng chỉ trả về JSON thuần, không bọc markdown. Lỗi lần trước: {failed[:200]}..."

    @staticmethod
    def _clean_json_response(text: str) -> str:
        """làm sạch JSON phản hồi"""
        return clean_json_response(text)


def create_user_ai_service(
    api_provider: str,
    api_key: str,
    api_base_url: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    system_prompt: Optional[str] = None,
) -> AIService:
    """Tạo dịch vụ AI cho người dùng (không hỗ trợ MCP)"""
    return AIService(
        api_provider=api_provider,
        api_key=api_key,
        api_base_url=api_base_url,
        default_model=model_name,
        default_temperature=temperature,
        default_max_tokens=max_tokens,
        default_system_prompt=system_prompt,
    )


def create_user_ai_service_with_mcp(
    api_provider: str,
    api_key: str,
    api_base_url: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    user_id: str,
    db_session,
    system_prompt: Optional[str] = None,
    enable_mcp: bool = True,
    disable_thinking: bool = False,
) -> AIService:
    """
    tạohỗ trợMCPcủa người dùngAIdịch vụ
    
    Args:
        api_provider: AINhà cung cấp
        api_key: APIkhóa
        api_base_url: APIcơ sởURL
        model_name: Tên mô hình
        temperature: nhiệt độ
        max_tokens: Số token tối đa
        user_id: người dùngID(dùng để tảiMCPcông cụ)
        db_session: Phiên cơ sở dữ liệu
        system_prompt: Prompt hệ thống
        enable_mcp: có hay khôngbậtMCPcông cụ
        
    Returns:
        đã cấu hìnhAIServicethể hiện
    """
    return AIService(
        api_provider=api_provider,
        api_key=api_key,
        api_base_url=api_base_url,
        default_model=model_name,
        default_temperature=temperature,
        default_max_tokens=max_tokens,
        default_system_prompt=system_prompt,
        user_id=user_id,
        db_session=db_session,
        enable_mcp=enable_mcp,
        disable_thinking=disable_thinking,
    )