"""Facade thống nhất client MCP - lối vào duy nhất cho mọi thao tác MCP

Module này cung cấp interface client MCP (Model Context Protocol) thống nhất,
tích hợp quản lý kết nối, thao tác công cụ, chuyển đổi định dạng, cache và thu thập chỉ số.

Ví dụ sử dụng:
    from app.mcp import mcp_client, MCPPluginConfig
    
    # Đăng ký plugin
    await mcp_client.register(MCPPluginConfig(
        user_id="user123",
        plugin_name="exa-search",
        url="http://localhost:8000/mcp"
    ))
    
    # Lấy danh sách công cụ
    tools = await mcp_client.get_tools("user123", "exa-search")
    
    # Gọi công cụ
    result = await mcp_client.call_tool("user123", "exa-search", "web_search", {"query": "..."})
    
    # Đăng ký callback thay đổi trạng thái
    async def on_status_change(event):
        print(f"Plugin {event['plugin_name']} trạng thái: {event['old_status']} -> {event['new_status']}")
    
    mcp_client.register_status_callback(on_status_change)
"""

from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum
import asyncio
import time
import json

from mcp import ClientSession, types
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.sse import sse_client
from anyio import ClosedResourceError

from app.mcp.config import mcp_config
from app.logger import get_logger, summarize_log_value

logger = get_logger(__name__)


# ==================== Cấu trúc dữ liệu ====================

class PluginStatus(str, Enum):
    """Enum trạng thái plugin"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    ERROR = "error"


# Kiểu callback thay đổi trạng thái
StatusCallback = Callable[[Dict[str, Any]], Awaitable[None]]


@dataclass
class MCPPluginConfig:
    """Cấu hình plugin MCP"""
    user_id: str
    plugin_name: str
    url: str
    plugin_type: str = "streamable_http"  # streamable_http, sse, http
    headers: Optional[Dict[str, str]] = None
    env: Optional[Dict[str, str]] = None
    timeout: float = 60.0


@dataclass
class SessionInfo:
    """Thông tin session"""
    session: ClientSession
    url: str
    plugin_type: str = "streamable_http"
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)
    request_count: int = 0
    error_count: int = 0
    status: str = "active"  # active, degraded, error
    _context_stack: List = field(default_factory=list)
    _expiry_warned: bool = False
    
    @property
    def error_rate(self) -> float:
        """Tính tỷ lệ lỗi"""
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count


@dataclass
class ToolCacheEntry:
    """Hạng mục cache công cụ"""
    tools: List[Dict[str, Any]]
    expire_time: datetime
    hit_count: int = 0


@dataclass
class ToolMetrics:
    """Chỉ số gọi công cụ"""
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0.0
    last_call_time: Optional[datetime] = None
    
    @property
    def avg_duration_ms(self) -> float:
        """Thời gian gọi trung bình"""
        return self.total_duration_ms / self.total_calls if self.total_calls > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        """Tỷ lệ thành công"""
        return self.success_calls / self.total_calls if self.total_calls > 0 else 0.0
    
    def record_success(self, duration_ms: float):
        """Ghi nhận lần gọi thành công"""
        self.total_calls += 1
        self.success_calls += 1
        self.total_duration_ms += duration_ms
        self.last_call_time = datetime.now()
    
    def record_failure(self, duration_ms: float):
        """Ghi nhận lần gọi thất bại"""
        self.total_calls += 1
        self.failed_calls += 1
        self.total_duration_ms += duration_ms
        self.last_call_time = datetime.now()


class MCPError(Exception):
    """Exception thao tác MCP"""
    pass


# ==================== Facade thống nhất ====================

class MCPClientFacade:
    """
    Facade thống nhất client MCP

    Đây là lối vào duy nhất cho mọi thao tác MCP, cung cấp:
    1. Quản lý kết nối (đăng ký, hủy đăng ký, kiểm tra)
    2. Thao tác công cụ (lấy, gọi, gọi hàng loạt)
    3. Chuyển đổi định dạng (MCP ↔ OpenAI Function Calling)
    4. Cache và chỉ số

    Mẫu thiết kế:
    - Mẫu singleton: instance duy nhất toàn cục
    - Mẫu facade: interface đối ngoại thống nhất

    An toàn luồng:
    - Dùng asyncio.Lock bảo vệ thao tác session
    - Dùng lock chi tiết cấp người dùng để tránh nghẽn
    """
    
    _instance: Optional['MCPClientFacade'] = None
    
    def __new__(cls):
        """Mẫu singleton"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Quản lý session
        self._sessions: Dict[str, SessionInfo] = {}
        self._session_lock = asyncio.Lock()
        self._user_locks: Dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()
        
        # Cache công cụ
        self._tool_cache: Dict[str, ToolCacheEntry] = {}
        self._cache_ttl = timedelta(minutes=mcp_config.TOOL_CACHE_TTL_MINUTES)
        
        # Chỉ số gọi
        self._metrics: Dict[str, ToolMetrics] = defaultdict(ToolMetrics)
        
        # Tác vụ nền
        self._cleanup_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._tasks_started = False
        
        # Callback thay đổi trạng thái
        self._status_callbacks: List[StatusCallback] = []
        
        self._initialized = True
        logger.info("✅ MCPClientFacade khởi tạo hoàn tất")
    
    def _get_key(self, user_id: str, plugin_name: str) -> str:
        """Sinh khóa session"""
        return f"{user_id}:{plugin_name}"
    
    async def _get_user_lock(self, user_id: str) -> asyncio.Lock:
        """Lấy lock riêng của người dùng (lock chi tiết)"""
        async with self._locks_lock:
            if user_id not in self._user_locks:
                self._user_locks[user_id] = asyncio.Lock()
            return self._user_locks[user_id]
    
    def _ensure_background_tasks(self):
        """Đảm bảo tác vụ nền đã khởi động (khởi tạo chậm)"""
        if not self._tasks_started:
            try:
                loop = asyncio.get_running_loop()
                if self._cleanup_task is None:
                    self._cleanup_task = asyncio.create_task(self._cleanup_loop())
                    logger.info("✅ Tác vụ dọn dẹp nền MCP đã khởi động")
                
                if self._health_check_task is None:
                    self._health_check_task = asyncio.create_task(self._health_check_loop())
                    logger.info("✅ Tác vụ kiểm tra sức khỏe MCP đã khởi động")
                
                self._tasks_started = True
            except RuntimeError:
                # Không có event loop đang chạy, thử lại sau
                pass
    
    async def _cleanup_loop(self):
        """Dọn dẹp nền session hết hạn"""
        while True:
            try:
                await asyncio.sleep(mcp_config.CLEANUP_INTERVAL_SECONDS)
                await self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Lỗi bất thường tác vụ dọn dẹp: {e}")
    
    async def _health_check_loop(self):
        """Kiểm tra sức khỏe nền"""
        while True:
            try:
                await asyncio.sleep(mcp_config.HEALTH_CHECK_INTERVAL_SECONDS)
                await self._check_session_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Lỗi bất thường tác vụ kiểm tra sức khỏe: {e}")
    
    async def _cleanup_expired_sessions(self):
        """Dọn dẹp session hết hạn"""
        now = time.time()
        expired_keys = []
        
        async with self._session_lock:
            for key, session in list(self._sessions.items()):
                if now - session.last_access > mcp_config.CLIENT_TTL_SECONDS:
                    expired_keys.append(key)
        
        if expired_keys:
            logger.info(f"🧹 Dọn dẹp {len(expired_keys)} session MCP hết hạn")
            for key in expired_keys:
                user_id = key.split(':', 1)[0]
                user_lock = await self._get_user_lock(user_id)
                async with user_lock:
                    await self._close_session_unsafe(key)
    
    async def _check_session_health(self):
        """Kiểm tra trạng thái sức khỏe session"""
        async with self._session_lock:
            for key, session in list(self._sessions.items()):
                # Kiểm tra tỷ lệ lỗi
                if session.request_count > mcp_config.MIN_REQUESTS_FOR_HEALTH_CHECK:
                    old_status = session.status
                    user_id, plugin_name = key.split(':', 1)
                    
                    if session.error_rate > mcp_config.ERROR_RATE_CRITICAL:
                        if session.status != "error":
                            session.status = "error"
                            logger.error(f"❌ Session {key} tỷ lệ lỗi quá cao ({session.error_rate:.1%})")
                            await self._emit_status_change(user_id, plugin_name, old_status, "error",
                                f"Tỷ lệ lỗi quá cao: {session.error_rate:.1%}")
                    elif session.error_rate > mcp_config.ERROR_RATE_WARNING:
                        if session.status == "active":
                            session.status = "degraded"
                            logger.warning(f"⚠️ Session {key} sức khỏe suy giảm ({session.error_rate:.1%})")
                            await self._emit_status_change(user_id, plugin_name, old_status, "degraded",
                                f"Tỷ lệ lỗi khá cao: {session.error_rate:.1%}")
                    elif session.status == "degraded":
                        session.status = "active"
                        logger.info(f"✅ Session {key} đã phục hồi bình thường")
                        await self._emit_status_change(user_id, plugin_name, old_status, "active", "Đã phục hồi bình thường")
    
    # ==================== Quản lý kết nối ====================
    
    async def register(self, config: MCPPluginConfig) -> bool:
        """
        Đăng ký plugin MCP và thiết lập kết nối

        Args:
            config: Cấu hình plugin

        Returns:
            Có đăng ký thành công hay không
        """
        self._ensure_background_tasks()

        key = self._get_key(config.user_id, config.plugin_name)
        user_lock = await self._get_user_lock(config.user_id)

        async with user_lock:
            # Nếu đã tồn tại, đóng trước
            if key in self._sessions:
                await self._close_session_unsafe(key)

            stream_ctx = None
            session = None
            
            try:
                logger.info(f"🔗 Kết nối máy chủ MCP: {config.plugin_name} -> {config.url} (loại: {config.plugin_type})")

                # Chọn client theo loại
                if config.plugin_type == "sse":
                    # Client SSE - trả về 2 giá trị
                    stream_ctx = sse_client(
                        url=config.url,
                        headers=config.headers,
                        timeout=config.timeout
                    )
                    read, write = await stream_ctx.__aenter__()
                else:
                    # Client streamable_http (mặc định, cũng dùng cho loại http) - trả về 3 giá trị
                    stream_ctx = streamablehttp_client(
                        url=config.url,
                        headers=config.headers,
                        timeout=config.timeout
                    )
                    read, write, _ = await stream_ctx.__aenter__()
                
                session = ClientSession(read, write)
                await session.__aenter__()
                await session.initialize()
                
                now = time.time()
                info = SessionInfo(
                    session=session,
                    url=config.url,
                    plugin_type=config.plugin_type,
                    created_at=now,
                    last_access=now,
                    _context_stack=[('stream', stream_ctx), ('session', session)]
                )
                
                async with self._session_lock:
                    self._sessions[key] = info
                
                logger.info(f"✅ Thiết lập session MCP thành công: {key}")
                await self._emit_status_change(config.user_id, config.plugin_name, "inactive", "active", "Kết nối thành công")
                return True

            except ExceptionGroup as eg:
                # Xử lý nhóm exception của TaskGroup, trích thông tin lỗi chi tiết
                error_details = []
                for exc in eg.exceptions:
                    error_details.append(f"{type(exc).__name__}: {exc}")
                error_msg = "; ".join(error_details)
                logger.error(f"❌ Kết nối MCP thất bại {key}: Exception TaskGroup - {error_msg}")
                
                # Dọn dẹp context đã tạo trong cùng task, tránh dọn dẹp cancel scope xuyên task
                await self._cleanup_contexts_in_task(session, stream_ctx)
                
                await self._emit_status_change(config.user_id, config.plugin_name, "inactive", "error", error_msg)
                return False

            except Exception as e:
                logger.error(f"❌ Kết nối MCP thất bại {key}: {type(e).__name__}: {e}")
                
                # Dọn dẹp context đã tạo trong cùng task, tránh dọn dẹp cancel scope xuyên task
                await self._cleanup_contexts_in_task(session, stream_ctx)
                
                await self._emit_status_change(config.user_id, config.plugin_name, "inactive", "error", str(e))
                return False
    
    async def unregister(self, user_id: str, plugin_name: str):
        """
        Hủy đăng ký plugin MCP

        Args:
            user_id: ID người dùng
            plugin_name: Tên plugin
        """
        key = self._get_key(user_id, plugin_name)
        user_lock = await self._get_user_lock(user_id)
        
        old_status = self._sessions.get(key, SessionInfo(session=None, url="")).status if key in self._sessions else "active"
        
        async with user_lock:
            await self._close_session_unsafe(key)
            self._invalidate_cache(key)
        
        await self._emit_status_change(user_id, plugin_name, old_status, "inactive", "Đã hủy đăng ký")
    
    async def _cleanup_contexts_in_task(self, session, stream_ctx):
        """Dọn dẹp context đã tạo trong task hiện tại (phương thức bất đồng bộ)

        Khi kết nối MCP thất bại, context (cancel scope) phải được dọn dẹp trong cùng task với lúc tạo.
        Vì xử lý exception và tạo context ở cùng một task, có thể await __aexit__ an toàn ở đây.
        """
        # Dọn dẹp session trước, rồi đến stream (thứ tự LIFO)
        if session is not None:
            try:
                await session.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"Dọn dẹp context session: {e}")
        
        if stream_ctx is not None:
            try:
                await stream_ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"Dọn dẹp context stream: {e}")
        
        logger.debug("Đã dọn dẹp context MCP trong task hiện tại")
    
    async def _close_session_unsafe(self, key: str):
        """Đóng session (không khóa user, cần caller đảm bảo an toàn luồng)"""
        async with self._session_lock:
            info = self._sessions.pop(key, None)
        
        if info:
            # Dọn dẹp context theo thứ tự LIFO
            for ctx_type, ctx in reversed(info._context_stack):
                try:
                    await ctx.__aexit__(None, None, None)
                except RuntimeError as e:
                    if "cancel scope" in str(e).lower() or "different task" in str(e).lower():
                        logger.debug(f"Bỏ qua cảnh báo chuyển task khi dọn dẹp context {ctx_type}: {e}")
                    else:
                        logger.error(f"Dọn dẹp context {ctx_type} thất bại: {e}")
                except Exception as e:
                    logger.debug(f"Dọn dẹp context {ctx_type}: {e}")
            
            logger.info(f"🗑️ Đóng session MCP: {key}")
    
    async def _get_session(self, user_id: str, plugin_name: str) -> ClientSession:
        """
        Lấy session

        Args:
            user_id: ID người dùng
            plugin_name: Tên plugin

        Returns:
            Instance ClientSession

        Raises:
            ValueError: Session không tồn tại
        """
        key = self._get_key(user_id, plugin_name)
        
        info = self._sessions.get(key)
        if not info:
            raise ValueError(f"Session MCP không tồn tại: {plugin_name}, vui lòng gọi register() trước")
        
        if info.status == "error":
            logger.warning(f"⚠️ Session {key} đang ở trạng thái lỗi, có thể cần đăng ký lại")
        
        info.last_access = time.time()
        info.request_count += 1
        return info.session

    def is_registered(self, user_id: str, plugin_name: str) -> bool:
        """
        Kiểm tra plugin đã đăng ký chưa (phương thức đồng bộ, chỉ kiểm tra trạng thái bộ nhớ)

        Args:
            user_id: ID người dùng
            plugin_name: Tên plugin

        Returns:
            Đã đăng ký và trạng thái bình thường hay chưa
        """
        key = self._get_key(user_id, plugin_name)
        info = self._sessions.get(key)
        return info is not None and info.status != "error"

    def get_session_status(self, user_id: str, plugin_name: str) -> Optional[str]:
        """
        Lấy trạng thái session (phương thức đồng bộ)

        Args:
            user_id: ID người dùng
            plugin_name: Tên plugin

        Returns:
            Trạng thái session, trả về None nếu không tồn tại
        """
        key = self._get_key(user_id, plugin_name)
        info = self._sessions.get(key)
        return info.status if info else None

    async def ensure_registered(
        self,
        user_id: str,
        plugin_name: str,
        url: str,
        plugin_type: str = "streamable_http",
        headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Đảm bảo plugin đã đăng ký (tự động đăng ký nếu chưa)

        Args:
            user_id: ID người dùng
            plugin_name: Tên plugin
            url: URL máy chủ
            plugin_type: Loại plugin (streamable_http, sse, http)
            headers: Header HTTP

        Returns:
            Có thành công hay không
        """
        key = self._get_key(user_id, plugin_name)
        
        if key in self._sessions:
            info = self._sessions[key]
            # Kiểm tra URL và loại có thay đổi không
            if info.url == url and info.plugin_type == plugin_type and info.status != "error":
                return True
        
        # Đăng ký
        return await self.register(MCPPluginConfig(
            user_id=user_id,
            plugin_name=plugin_name,
            url=url,
            plugin_type=plugin_type,
            headers=headers
        ))
    
    async def test_connection(self, user_id: str, plugin_name: str) -> Dict[str, Any]:
        """
        Kiểm tra kết nối

        Args:
            user_id: ID người dùng
            plugin_name: Tên plugin

        Returns:
            Dict kết quả kiểm tra
        """
        start = time.time()
        
        try:
            session = await self._get_session(user_id, plugin_name)
            result = await session.list_tools()
            
            tools = [
                {"name": t.name, "description": t.description or ""}
                for t in result.tools
            ]
            
            return {
                "success": True,
                "message": "Kết nối thành công",
                "response_time_ms": round((time.time() - start) * 1000, 2),
                "tools_count": len(tools),
                "tools": tools
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "response_time_ms": round((time.time() - start) * 1000, 2),
                "error_type": type(e).__name__
            }
    
    # ==================== Thao tác công cụ ====================
    
    async def get_tools(
        self, 
        user_id: str, 
        plugin_name: str,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Lấy danh sách công cụ

        Args:
            user_id: ID người dùng
            plugin_name: Tên plugin
            use_cache: Có dùng cache hay không

        Returns:
            Danh sách công cụ [{"name": ..., "description": ..., "inputSchema": ...}]
        """
        cache_key = self._get_key(user_id, plugin_name)
        now = datetime.now()
        
        # Kiểm tra cache
        if use_cache and cache_key in self._tool_cache:
            entry = self._tool_cache[cache_key]
            if now < entry.expire_time:
                entry.hit_count += 1
                logger.debug(f"🎯 Cache công cụ trúng: {cache_key} (số lần trúng: {entry.hit_count})")
                return entry.tools
            else:
                del self._tool_cache[cache_key]
                logger.debug(f"⏰ Cache công cụ hết hạn: {cache_key}")
        
        # Lấy từ máy chủ
        session = await self._get_session(user_id, plugin_name)
        result = await session.list_tools()
        
        tools = []
        for tool in result.tools:
            annotations = getattr(tool, "annotations", None)
            if annotations is not None and hasattr(annotations, "model_dump"):
                annotations = annotations.model_dump(exclude_none=True)
            elif annotations is not None and not isinstance(annotations, dict):
                annotations = {
                    key: value for key, value in vars(annotations).items()
                    if not key.startswith("_") and value is not None
                }
            tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema,
                "annotations": annotations or {},
            })
        
        # Cập nhật cache
        self._tool_cache[cache_key] = ToolCacheEntry(
            tools=tools,
            expire_time=now + self._cache_ttl
        )
        
        logger.info(f"Đã lấy {len(tools)} công cụ: {plugin_name}")
        return tools
    
    async def call_tool(
        self,
        user_id: str,
        plugin_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: Optional[float] = None,
        max_reconnect_attempts: int = 2
    ) -> Any:
        """
        Gọi một công cụ đơn

        Args:
            user_id: ID người dùng
            plugin_name: Tên plugin
            tool_name: Tên công cụ
            arguments: Tham số công cụ
            timeout: Thời gian timeout (giây)
            max_reconnect_attempts: Số lần thử kết nối lại tối đa

        Returns:
            Kết quả thực thi công cụ
        """
        tool_key = f"{plugin_name}.{tool_name}"
        start_time = time.time()
        actual_timeout = timeout or mcp_config.TOOL_CALL_TIMEOUT_SECONDS
        
        for attempt in range(max_reconnect_attempts + 1):
            try:
                session = await self._get_session(user_id, plugin_name)
                
                logger.info(f"Gọi công cụ: {tool_key}")
                logger.debug(f"  Tóm tắt tham số: {summarize_log_value(arguments)}")
                
                # Gọi có timeout
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments),
                    timeout=actual_timeout
                )
                
                # Xử lý kết quả trả về
                output = self._extract_tool_result(result)
                
                # Ghi nhận chỉ số thành công
                duration_ms = (time.time() - start_time) * 1000
                self._metrics[tool_key].record_success(duration_ms)
                
                logger.info(f"✅ Gọi công cụ thành công: {tool_key} ({duration_ms:.2f}ms)")
                return output
                
            except asyncio.TimeoutError:
                duration_ms = (time.time() - start_time) * 1000
                self._metrics[tool_key].record_failure(duration_ms)
                raise MCPError(f"Gọi công cụ timeout (>{actual_timeout} giây)")
                
            except ClosedResourceError as e:
                # Kết nối đã đóng, thử kết nối lại
                if attempt < max_reconnect_attempts:
                    logger.warning(f"⚠️ Kết nối MCP đã đóng, thử kết nối lại (lần {attempt + 1}/{max_reconnect_attempts})")
                    key = self._get_key(user_id, plugin_name)
                    
                    # Lưu thông tin session cũ để đăng ký lại
                    old_info = None
                    async with self._session_lock:
                        if key in self._sessions:
                            old_info = self._sessions[key]
                    
                    # Đóng session cũ
                    try:
                        await self._close_session_unsafe(key)
                    except Exception as close_err:
                        logger.debug(f"Lỗi khi đóng session cũ: {close_err}")
                    
                    # Dùng thông tin session cũ để đăng ký lại
                    url = old_info.url if old_info else ""
                    plugin_type = old_info.plugin_type if old_info else "streamable_http"
                    
                    if url:
                        success = await self.ensure_registered(
                            user_id, plugin_name, url, plugin_type
                        )
                        if success:
                            logger.info(f"✅ Thiết lập lại session MCP thành công: {key}")
                            await asyncio.sleep(0.5)
                            continue
                    
                    # Nếu không lấy được thông tin cũ hoặc đăng ký lại thất bại, chờ rồi thử lại
                    await asyncio.sleep(0.5)
                    continue
                else:
                    duration_ms = (time.time() - start_time) * 1000
                    self._metrics[tool_key].record_failure(duration_ms)
                    raise MCPError(f"Kết nối đã đóng và kết nối lại thất bại (đã thử {max_reconnect_attempts} lần)")
            
            except ValueError as e:
                # Session không tồn tại, thử đăng ký lại
                if "Session MCP không tồn tại" in str(e) and attempt < max_reconnect_attempts:
                    logger.warning(f"⚠️ Session MCP không tồn tại, thử đăng ký lại (lần {attempt + 1}/{max_reconnect_attempts})")
                    
                    # Thử lấy thông tin session để đăng ký lại
                    key = self._get_key(user_id, plugin_name)
                    old_info = None
                    async with self._session_lock:
                        if key in self._sessions:
                            old_info = self._sessions[key]
                    
                    url = old_info.url if old_info else ""
                    plugin_type = old_info.plugin_type if old_info else "streamable_http"
                    
                    if url:
                        success = await self.ensure_registered(
                            user_id, plugin_name, url, plugin_type
                        )
                        if success:
                            logger.info(f"✅ Đăng ký lại session MCP thành công: {key}")
                            await asyncio.sleep(0.5)
                            continue
                    
                    await asyncio.sleep(0.5)
                    continue
                else:
                    duration_ms = (time.time() - start_time) * 1000
                    self._metrics[tool_key].record_failure(duration_ms)
                    raise MCPError(f"Session không tồn tại: {e}")
                    
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self._metrics[tool_key].record_failure(duration_ms)
                
                # Cập nhật đếm lỗi session
                key = self._get_key(user_id, plugin_name)
                if key in self._sessions:
                    session_info = self._sessions[key]
                    session_info.error_count += 1
                    
                    # Kiểm tra có cần cập nhật trạng thái không
                    if session_info.request_count >= mcp_config.MIN_REQUESTS_FOR_HEALTH_CHECK:
                        old_status = session_info.status
                        if session_info.error_rate > mcp_config.ERROR_RATE_CRITICAL and old_status != "error":
                            session_info.status = "error"
                            asyncio.create_task(self._emit_status_change(
                                user_id, plugin_name, old_status, "error", f"Tỷ lệ lỗi quá cao: {session_info.error_rate:.1%}"
                            ))
                        elif session_info.error_rate > mcp_config.ERROR_RATE_WARNING and old_status == "active":
                            session_info.status = "degraded"
                            asyncio.create_task(self._emit_status_change(
                                user_id, plugin_name, old_status, "degraded", f"Tỷ lệ lỗi khá cao: {session_info.error_rate:.1%}"
                            ))
                
                error_msg = str(e)
                error_type = type(e).__name__
                
                # Kiểm tra có phải lỗi phân tích JSON (lỗi nội bộ MCP SDK) không
                if "parsing JSON" in error_msg.lower() or "json" in error_msg.lower():
                    logger.error(f"❌ Gọi công cụ thất bại (lỗi phân tích JSON): {tool_key}: {e}")
                    raise MCPError(f"Định dạng response của máy chủ MCP không đúng, vui lòng kiểm tra trạng thái máy chủ hoặc thử lại sau")
                
                logger.error(f"❌ Gọi công cụ thất bại: {tool_key} [{error_type}]: {e}")
                raise MCPError(f"Gọi công cụ thất bại: {error_msg}")
        
        raise MCPError("Gọi công cụ thất bại: lỗi không xác định")
    
    def _extract_tool_result(self, result) -> Any:
        """Trích nội dung thực tế từ kết quả MCP"""
        if result.content:
            for content in result.content:
                if isinstance(content, types.TextContent):
                    return content.text
                elif isinstance(content, types.ImageContent):
                    return {
                        "type": "image",
                        "data": content.data,
                        "mimeType": content.mimeType
                    }
            return result.content[0] if result.content else None
        
        if hasattr(result, 'structuredContent') and result.structuredContent:
            return result.structuredContent
        
        return None
    
    async def batch_call_tools(
        self,
        user_id: str,
        tool_calls: List[Dict[str, Any]],
        max_concurrent: int = 2,
        timeout: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Thực thi hàng loạt các lệnh gọi công cụ do AI trả về

        Args:
            user_id: ID người dùng
            tool_calls: Danh sách lệnh gọi công cụ do AI trả về, định dạng:
                [{"id": "...", "function": {"name": "plugin_tool", "arguments": "{...}"}}]
            max_concurrent: Số lượng đồng thời tối đa
            timeout: Thời gian timeout cho từng công cụ

        Returns:
            Danh sách kết quả gọi công cụ
        """
        if not tool_calls:
            return []
        
        logger.info(f"Bắt đầu thực thi {len(tool_calls)} lệnh gọi công cụ (đồng thời tối đa={max_concurrent})")
        
        results = []
        
        for i in range(0, len(tool_calls), max_concurrent):
            batch = tool_calls[i:i+max_concurrent]
            batch_num = i // max_concurrent + 1
            total_batches = (len(tool_calls) + max_concurrent - 1) // max_concurrent
            
            logger.info(f"Thực thi lô công cụ {batch_num}/{total_batches}, số lượng: {len(batch)}")
            
            tasks = [
                self._execute_single_tool_call(user_id, tc, timeout)
                for tc in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for j, result in enumerate(batch_results):
                tc = batch[j]
                if isinstance(result, Exception):
                    results.append({
                        "tool_call_id": tc.get("id", f"call_{i+j}"),
                        "role": "tool",
                        "name": tc["function"]["name"],
                        "content": f"Gọi công cụ thất bại: {str(result)}",
                        "success": False,
                        "error": str(result)
                    })
                else:
                    results.append(result)
            
            # Trì hoãn giữa các lô, tránh giới hạn API
            if i + max_concurrent < len(tool_calls):
                await asyncio.sleep(0.3)
        
        return results
    
    async def _execute_single_tool_call(
        self, 
        user_id: str, 
        tool_call: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Thực thi một lệnh gọi công cụ đơn"""
        tool_call_id = tool_call.get("id", "unknown")
        function_name = tool_call["function"]["name"]
        
        try:
            # Phân tích tên plugin và tên công cụ
            plugin_name, tool_name = self.parse_function_name(function_name)
            
            # Phân tích tham số
            arguments = tool_call["function"]["arguments"]
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            
            # Gọi công cụ
            result = await self.call_tool(
                user_id=user_id,
                plugin_name=plugin_name,
                tool_name=tool_name,
                arguments=arguments,
                timeout=timeout
            )
            
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": function_name,
                "content": json.dumps(result, ensure_ascii=False) if result else "",
                "success": True
            }
            
        except json.JSONDecodeError as e:
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": function_name,
                "content": f"Phân tích JSON tham số thất bại: {str(e)}",
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": function_name,
                "content": f"Gọi công cụ thất bại: {str(e)}",
                "success": False,
                "error": str(e)
            }
    
    # ==================== Chuyển đổi định dạng ====================
    
    def format_tools_for_openai(
        self, 
        tools: List[Dict[str, Any]], 
        plugin_name: str
    ) -> List[Dict[str, Any]]:
        """
        Chuyển công cụ MCP sang định dạng OpenAI Function Calling

        Args:
            tools: Danh sách công cụ MCP
            plugin_name: Tên plugin (làm tiền tố)

        Returns:
            Danh sách công cụ định dạng OpenAI
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": f"{plugin_name}_{tool['name']}",
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {
                        "type": "object",
                        "properties": {},
                        "required": []
                    })
                }
            }
            for tool in tools
        ]
    
    def parse_function_name(self, function_name: str) -> tuple:
        """
        Phân tích tên hàm thành tên plugin và tên công cụ

        Hỗ trợ hai định dạng:
        - "plugin_tool" (phân cách bằng gạch dưới)
        - "plugin.tool" (phân cách bằng dấu chấm)

        Args:
            function_name: Tên công cụ

        Returns:
            (plugin_name, tool_name)

        Raises:
            ValueError: Định dạng không hợp lệ
        """
        # Ưu tiên thử tách bằng gạch dưới
        if "_" in function_name:
            parts = function_name.split("_", 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                return (parts[0], parts[1])
        
        # Nếu tách bằng gạch dưới thất bại, thử tách bằng dấu chấm
        if "." in function_name:
            parts = function_name.split(".", 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                logger.debug(f"🔧 Tên công cụ dùng dấu chấm phân cách: {function_name} -> plugin={parts[0]}, tool={parts[1]}")
                return (parts[0], parts[1])
        
        raise ValueError(f"Định dạng tên công cụ không hợp lệ: {function_name}, phải là định dạng 'plugin_tool' hoặc 'plugin.tool'")
    
    def build_tool_context(
        self, 
        tool_results: List[Dict[str, Any]], 
        format: str = "markdown"
    ) -> str:
        """
        Định dạng kết quả công cụ thành ngữ cảnh

        Args:
            tool_results: Danh sách kết quả gọi công cụ
            format: Định dạng đầu ra (markdown/json/plain)

        Returns:
            Chuỗi ngữ cảnh đã định dạng
        """
        if not tool_results:
            return ""
        
        if format == "markdown":
            return self._build_markdown_context(tool_results)
        elif format == "json":
            return json.dumps(tool_results, ensure_ascii=False, indent=2)
        else:
            return self._build_plain_context(tool_results)
    
    def _build_markdown_context(self, tool_results: List[Dict[str, Any]]) -> str:
        """Xây dựng ngữ cảnh công cụ định dạng Markdown"""
        lines = ["## 🔧 Kết quả gọi công cụ\n"]
        
        for i, result in enumerate(tool_results, 1):
            tool_name = result.get("name", "unknown")
            success = result.get("success", False)
            content = result.get("content", "")
            
            status_emoji = "✅" if success else "❌"
            lines.append(f"### {status_emoji} {i}. {tool_name}\n")
            
            if success:
                # Thử làm đẹp nội dung JSON
                try:
                    content_obj = json.loads(content)
                    content = json.dumps(content_obj, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                lines.append(f"```json\n{content}\n```\n")
            else:
                lines.append(f"**Lỗi**: {content}\n")
        
        return "\n".join(lines)
    
    def _build_plain_context(self, tool_results: List[Dict[str, Any]]) -> str:
        """Xây dựng ngữ cảnh công cụ định dạng văn bản thuần"""
        lines = ["=== Kết quả gọi công cụ ===\n"]
        
        for i, result in enumerate(tool_results, 1):
            tool_name = result.get("name", "unknown")
            success = result.get("success", False)
            content = result.get("content", "")
            
            status = "Thành công" if success else "Thất bại"
            lines.append(f"{i}. {tool_name} - {status}")
            lines.append(f"   Kết quả: {content}\n")
        
        return "\n".join(lines)
    
    # ==================== Cache và chỉ số ====================
    
    def _invalidate_cache(self, key: str):
        """Vô hiệu hóa cache"""
        if key in self._tool_cache:
            del self._tool_cache[key]
            logger.debug(f"🧹 Đã dọn dẹp cache: {key}")
    
    def clear_cache(
        self, 
        user_id: Optional[str] = None, 
        plugin_name: Optional[str] = None
    ):
        """
        Dọn dẹp cache

        Args:
            user_id: ID người dùng (tùy chọn)
            plugin_name: Tên plugin (tùy chọn)
        """
        if user_id and plugin_name:
            key = self._get_key(user_id, plugin_name)
            self._invalidate_cache(key)
            logger.info(f"🧹 Đã dọn dẹp cache: {key}")
        elif user_id:
            keys = [k for k in self._tool_cache if k.startswith(f"{user_id}:")]
            for k in keys:
                del self._tool_cache[k]
            logger.info(f"🧹 Đã dọn dẹp cache người dùng: {user_id} ({len(keys)} cái)")
        else:
            count = len(self._tool_cache)
            self._tool_cache.clear()
            logger.info(f"🧹 Đã dọn dẹp tất cả cache ({count} cái)")
    
    def get_metrics(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Lấy chỉ số gọi

        Args:
            tool_name: Tên công cụ (tùy chọn)

        Returns:
            Dict chỉ số
        """
        if tool_name and tool_name in self._metrics:
            m = self._metrics[tool_name]
            return {
                tool_name: {
                    "total_calls": m.total_calls,
                    "success_calls": m.success_calls,
                    "failed_calls": m.failed_calls,
                    "success_rate": round(m.success_rate, 3),
                    "avg_duration_ms": round(m.avg_duration_ms, 2),
                    "last_call_time": m.last_call_time.isoformat() if m.last_call_time else None
                }
            }
        
        return {
            k: {
                "total_calls": m.total_calls,
                "success_calls": m.success_calls,
                "failed_calls": m.failed_calls,
                "success_rate": round(m.success_rate, 3),
                "avg_duration_ms": round(m.avg_duration_ms, 2),
                "last_call_time": m.last_call_time.isoformat() if m.last_call_time else None
            }
            for k, m in self._metrics.items()
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Lấy thống kê cache"""
        return {
            "total_entries": len(self._tool_cache),
            "total_hits": sum(e.hit_count for e in self._tool_cache.values()),
            "cache_ttl_minutes": self._cache_ttl.total_seconds() / 60,
            "entries": [
                {
                    "key": k,
                    "tools_count": len(e.tools),
                    "hit_count": e.hit_count,
                    "expire_time": e.expire_time.isoformat()
                }
                for k, e in self._tool_cache.items()
            ]
        }
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Lấy thống kê session"""
        return {
            "total_sessions": len(self._sessions),
            "sessions": [
                {
                    "key": k,
                    "url": s.url,
                    "status": s.status,
                    "request_count": s.request_count,
                    "error_count": s.error_count,
                    "error_rate": round(s.error_rate, 3),
                    "created_at": datetime.fromtimestamp(s.created_at).isoformat(),
                    "last_access": datetime.fromtimestamp(s.last_access).isoformat()
                }
                for k, s in self._sessions.items()
            ]
        }
    
    # ==================== Callback trạng thái ====================
    
    def register_status_callback(self, callback: StatusCallback):
        """Đăng ký callback thay đổi trạng thái"""
        if callback not in self._status_callbacks:
            self._status_callbacks.append(callback)
            logger.info(f"✅ Đã đăng ký callback thay đổi trạng thái: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")
    
    def unregister_status_callback(self, callback: StatusCallback):
        """Hủy đăng ký callback thay đổi trạng thái"""
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)
    
    async def _emit_status_change(
        self,
        user_id: str,
        plugin_name: str,
        old_status: str,
        new_status: str,
        reason: str = ""
    ):
        """Kích hoạt sự kiện thay đổi trạng thái"""
        if old_status == new_status:
            return
        
        event = {
            "user_id": user_id,
            "plugin_name": plugin_name,
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"📢 Thay đổi trạng thái: {plugin_name} [{old_status} -> {new_status}] {reason}")
        
        for callback in self._status_callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Thực thi callback trạng thái thất bại: {e}")
    
    # ==================== Vòng đời ====================
    
    async def cleanup(self):
        """Dọn dẹp tất cả tài nguyên"""
        # Dừng tác vụ nền
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Đóng tất cả session
        async with self._session_lock:
            keys = list(self._sessions.keys())
        
        for key in keys:
            await self._close_session_unsafe(key)
        
        # Dọn dẹp cache
        self._tool_cache.clear()
        
        self._tasks_started = False
        logger.info("✅ Tài nguyên MCPClientFacade đã được dọn dẹp")


# ==================== Singleton toàn cục ====================

mcp_client = MCPClientFacade()
