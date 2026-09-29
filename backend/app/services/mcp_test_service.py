"""Dịch vụ kiểm tra plugin MCP - chuyên xử lý logic kiểm tra plugin

Sau khi tái cấu trúc, dùng facade MCPClientFacade thống nhất để quản lý mọi thao tác MCP.
"""

import time
import json
from typing import Dict, Any, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.mcp_plugin import MCPPlugin
from app.models.settings import Settings as UserSettings
from app.mcp import mcp_client, MCPPluginConfig  # dùng facade thống nhất mới
from app.services.ai_service import create_user_ai_service
from app.schemas.mcp_plugin import MCPTestResult
from app.services.prompt_service import prompt_service
from app.logger import get_logger, summarize_log_value
from app.user_manager import User

logger = get_logger(__name__)


class MCPTestService:
    """Dịch vụ kiểm tra plugin MCP (tái cấu trúc bằng facade thống nhất)"""

    def _check_plugin_registered(self, plugin: MCPPlugin, user_id: str) -> bool:
        """
        Kiểm tra plugin đã được đăng ký hay chưa (phương thức đồng bộ, không kích hoạt kết nối mới)

        Args:
            plugin: Cấu hình plugin
            user_id: người dùngID

        Returns:
            đã đăng ký hay chưa
        """
        return mcp_client.is_registered(user_id, plugin.plugin_name)

    async def test_plugin_connection(
        self,
        plugin: MCPPlugin,
        user_id: str
    ) -> MCPTestResult:
        """
        Kiểm tra kết nối đơn giản

        Lưu ý: trước khi gọi phương thức này, cần đảm bảo plugin đã được đăng ký qua tác vụ nền.

        Args:
            plugin: Cấu hình plugin
            user_id: người dùngID

        Returns:
            Kết quả kiểm tra
        """
        start_time = time.time()

        try:
            # Kiểm tra plugin đã đăng ký hay chưa (không kích hoạt kết nối mới)
            if not self._check_plugin_registered(plugin, user_id):
                return MCPTestResult(
                    success=False,
                    message="Plugin chưa được đăng ký",
                    error="MCPPhiên không tồn tại, vui lòng bật plugin trước",
                    suggestions=["Vui lòng bật plugin trước", "Nếu đã bật, vui lòng đợi một lát rồi thử lại"]
                )

            # Kiểm tra kết nối bằng facade thống nhất
            test_result = await mcp_client.test_connection(user_id, plugin.plugin_name)
            
            end_time = time.time()
            response_time = round((end_time - start_time) * 1000, 2)
            
            if test_result["success"]:
                return MCPTestResult(
                    success=True,
                    message=f"✅ Kiểm tra kết nối thành công",
                    response_time_ms=response_time,
                    tools_count=test_result.get("tools_count", 0),
                    suggestions=[
                        f"Thời gian phản hồi: {response_time}ms",
                        f"Số công cụ khả dụng: {test_result.get('tools_count', 0)}"
                    ]
                )
            else:
                return MCPTestResult(
                    success=False,
                    message="❌ Kiểm tra kết nối thất bại",
                    response_time_ms=response_time,
                    error=test_result.get("message", "Lỗi không rõ"),
                    error_type=test_result.get("error_type"),
                    suggestions=[
                        "Vui lòng kiểm tra máy chủ có đang trực tuyến không",
                        "Vui lòng xác nhậncấu hìnhchính xác",
                        "Vui lòng kiểm traAPI Keycó hợp lệ không"
                    ]
                )
                
        except Exception as e:
            end_time = time.time()
            response_time = round((end_time - start_time) * 1000, 2)
            
            logger.error(f"Kiểm tra plugin thất bại: {plugin.plugin_name}, lỗi: {e}")
            
            return MCPTestResult(
                success=False,
                message="❌ Kiểm tra thất bại",
                response_time_ms=response_time,
                error=str(e),
                error_type=type(e).__name__,
                suggestions=[
                    "Vui lòng kiểm tra máy chủ có đang trực tuyến không",
                    "Vui lòng xác nhậncấu hìnhchính xác",
                    "Vui lòng kiểm traAPI Keycó hợp lệ không"
                ]
            )
    
    async def test_plugin_with_ai(
        self,
        plugin: MCPPlugin,
        user: User,
        db_session: AsyncSession
    ) -> MCPTestResult:
        """
        Dùng AI để kiểm tra gọi công cụ thông minh
        
        Args:
            plugin: Cấu hình plugin
            user: Đối tượng người dùng
            db_session: cơ sở dữ liệuphiên
            
        Returns:
            Kết quả kiểm tra
        """
        start_time = time.time()
        
        try:
            # 1. Kiểm tra kết nối trước
            connection_result = await self.test_plugin_connection(plugin, user.user_id)
            
            if not connection_result.success:
                return connection_result
            
            # 2. Lấy danh sách công cụ bằng facade thống nhất
            tools = await mcp_client.get_tools(user.user_id, plugin.plugin_name)
            
            if not tools:
                return MCPTestResult(
                    success=False,
                    message="Plugin không cung cấp công cụ nào",
                    error="Danh sách công cụ trống",
                    response_time_ms=connection_result.response_time_ms,
                    suggestions=["Vui lòng kiểm tra cấu hình plugin", "Vui lòng xác nhậnMCPmáy chủ đang chạy bình thường"]
                )
            
            # 3. LấyAIcài đặt
            settings_result = await db_session.execute(
                select(UserSettings).where(UserSettings.user_id == user.user_id)
            )
            user_settings = settings_result.scalar_one_or_none()
            
            if not user_settings or not user_settings.api_key:
                # không cóAIcấu hình, trả về kết quả kiểm tra đơn giản
                logger.warning("Người dùng chưa cấu hìnhAIdịch vụ, bỏ qua kiểm tra thông minh")
                return MCPTestResult(
                    success=True,
                    message=f"✅ Kiểm tra kết nối thành công (chưa cấu hìnhAI, bỏ qua kiểm tra gọi công cụ)",
                    response_time_ms=connection_result.response_time_ms,
                    tools_count=len(tools),
                    suggestions=[
                        f"Kiểm tra kết nối: thành công",
                        f"Số công cụ khả dụng: {len(tools)}",
                        "Gợi ý: sau khi cấu hình dịch vụ AI có thể kiểm tra gọi công cụ thông minh"
                    ]
                )
            
            # 4. sử dụngAIChọn công cụ và tạo tham số kiểm tra
            logger.info(f"sử dụngAIPhân tích công cụ và tạo kế hoạch kiểm tra...")
            
            ai_service = create_user_ai_service(
                api_provider=user_settings.api_provider,
                api_key=user_settings.api_key,
                api_base_url=user_settings.api_base_url,
                model_name=user_settings.llm_model,
                temperature=0.3,
                max_tokens=1000
            )
            
            # Chuyển đổi bằng facade thống nhất thànhOpenAI Function Callingđịnh dạng
            openai_tools = mcp_client.format_tools_for_openai(tools, plugin.plugin_name)
            
            logger.info(f"📋 sau chuyển đổiOpenAIsố lượng công cụ: {len(openai_tools)}")
            logger.debug(f"📋 OpenAIDanh sách công cụ: {[t['function']['name'] for t in openai_tools]}")
            
            # gọiAIChọn công cụ (dùng hệ thống mẫu tùy chỉnh)
            prompts = await prompt_service.get_mcp_tool_test_prompts(
                plugin_name=plugin.plugin_name,
                user_id=user.user_id,
                db=db_session
            )
            
            # sử dụng generate_text tiến hành Function Calling(không streaming)
            ai_response = await ai_service.generate_text(
                prompt=prompts["user"],
                system_prompt=prompts["system"],
                tools=openai_tools,
                tool_choice="auto"
            )
            
            accumulated_text = ai_response.get("content", "")
            tool_calls = ai_response.get("tool_calls")
            
            # 5. kiểm traAIcó trả về gọi công cụ hay không
            if not tool_calls:
                logger.error(f"❌ AIKhông trả về gọi công cụ")
                return MCPTestResult(
                    success=False,
                    message="❌ AI Function Callingthất bại",
                    error=f"AIKhông trả về yêu cầu gọi công cụ. Phản hồi: {accumulated_text[:200] if accumulated_text else 'N/A'}",
                    tools_count=len(tools),
                    suggestions=[
                        "Vui lòng xác nhậnAImô hình hỗ trợFunction Calling",
                        f"hiện tạiProvider: {user_settings.api_provider}",
                        f"Mô hình hiện tại: {user_settings.llm_model}"
                    ]
                )
            
            # 6. Phân tích gọi công cụ
            tool_call = tool_calls[0]
            function = tool_call["function"]
            tool_name_with_prefix = function["name"]
            test_arguments = function["arguments"]
            
            if isinstance(test_arguments, str):
                try:
                    # DùngJSONphương thức làm sạch thống nhất
                    cleaned_args = ai_service._clean_json_response(test_arguments)
                    test_arguments = json.loads(cleaned_args)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ phân tíchAItham số thất bại: {e}")
                    return MCPTestResult(
                        success=False,
                        message="❌ AIĐịnh dạng tham số trả về bị lỗi",
                        error=f"Không thể phân tích tham sốJSON: {str(e)}",
                        tools_count=len(tools)
                    )
            
            # Phân tích tên plugin và tên công cụ
            try:
                _, tool_name = mcp_client.parse_function_name(tool_name_with_prefix)
            except ValueError:
                tool_name = tool_name_with_prefix
            
            logger.info(f"🤖 AICông cụ đã chọn: {tool_name}")
            logger.info(f"📝 AITóm tắt tham số đã tạo: {summarize_log_value(test_arguments)}")
            
            # 7. Gọi bằng facade thống nhấtMCPcông cụ
            call_start = time.time()
            try:
                tool_result = await mcp_client.call_tool(
                    user_id=user.user_id,
                    plugin_name=plugin.plugin_name,
                    tool_name=tool_name,
                    arguments=test_arguments
                )
                
                call_end = time.time()
                call_time = round((call_end - call_start) * 1000, 2)
                total_time = round((call_end - start_time) * 1000, 2)
                
                # Định dạng kết quả
                result_str = str(tool_result)
                if len(result_str) > 800:
                    result_preview = result_str[:800] + "\n...(Kết quả đã bị cắt ngắn)"
                else:
                    result_preview = result_str
                
                return MCPTestResult(
                    success=True,
                    message=f"✅ Function CallingKiểm tra thành công! Công cụ '{tool_name}' gọi bình thường",
                    response_time_ms=total_time,
                    tools_count=len(tools),
                    suggestions=[
                        f"🤖 AIchọn: {tool_name}",
                        f"📝 tham số: {json.dumps(test_arguments, ensure_ascii=False)}",
                        f"⏱️ Thời gian tốn: {call_time}ms",
                        f"📊 kết quả:\n{result_preview}"
                    ]
                )
                
            except Exception as call_error:
                call_end = time.time()
                total_time = round((call_end - start_time) * 1000, 2)
                
                logger.warning(f"Gọi công cụ thất bại: {tool_name}, lỗi: {call_error}")
                
                return MCPTestResult(
                    success=True,  # Kết nối thành công được tính là kiểm tra đạt
                    message=f"⚠️ Kết nối thành công, nhưng gọi công cụ thất bại",
                    response_time_ms=total_time,
                    tools_count=len(tools),
                    error=f"công cụ '{tool_name}' gọi thất bại: {str(call_error)}",
                    suggestions=[
                        f"✅ Kiểm tra kết nối: thành công",
                        f"❌ Kiểm tra gọi công cụ: thất bại",
                        f"🤖 AIchọn: {tool_name}",
                        f"❌ lỗi: {str(call_error)}",
                        "💡 Nguyên nhân có thể: API Keykhông hợp lệ, lỗi tham số hoặc giới hạn dịch vụ"
                    ]
                )
                
        except Exception as e:
            end_time = time.time()
            total_time = round((end_time - start_time) * 1000, 2)
            
            logger.error(f"Kiểm tra plugin thất bại: {plugin.plugin_name}, lỗi: {e}")
            
            return MCPTestResult(
                success=False,
                message="❌ Kiểm tra thất bại",
                response_time_ms=total_time,
                error=str(e),
                error_type=type(e).__name__,
                suggestions=[
                    "Vui lòng kiểm tra máy chủ có đang trực tuyến không",
                    "Vui lòng xác nhậncấu hìnhchính xác",
                    "Vui lòng kiểm traAPI Keycó hợp lệ không"
                ]
            )


# Thể hiện đơn nhất toàn cục
mcp_test_service = MCPTestService()
