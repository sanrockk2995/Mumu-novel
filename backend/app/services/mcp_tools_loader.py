"""Trình tải công cụ MCP - cổng lấy công cụ thống nhất

Trước mỗi yêu cầu AI, tự động kiểm tra cấu hình MCP của người dùng và tải các công cụ khả dụng.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logger import get_logger
from app.models.mcp_plugin import MCPPlugin
from app.mcp import mcp_client

logger = get_logger(__name__)


@dataclass
class UserToolsCache:
    """Mục bộ nhớ đệm công cụ của người dùng"""
    tools: Optional[List[Dict[str, Any]]]
    expire_time: datetime
    hit_count: int = 0


class MCPToolsLoader:
    """
    MCPTrình tải công cụ
    
    Chịu trách nhiệm:
    1. Kiểm tra người dùng đã cấu hình và bậtMCPplugin
    2. Tải danh sách công cụ từ các plugin đã bật
    3. Chuyển đổi công cụ thànhOpenAI Function Callingđịnh dạng
    4. Lưu kết quả vào bộ nhớ đệm để tăng hiệu năng
    """
    
    _instance: Optional['MCPToolsLoader'] = None
    
    def __new__(cls):
        """Chế độ đơn nhất"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Bộ nhớ đệm công cụ của người dùng: user_id -> UserToolsCache
        self._cache: Dict[str, UserToolsCache] = {}
        # Siêu dữ liệu rủi ro chỉ để phía máy chủ phán đoán, không đưa vào định nghĩa công cụ gửi cho mô hình.
        self._tool_metadata: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        # bộ nhớ đệmTTL(5phút)
        self._cache_ttl = timedelta(minutes=5)
        
        self._initialized = True
        logger.info("✅ MCPToolsLoader Khởi tạo hoàn tất")
    
    async def has_enabled_plugins(
        self, 
        user_id: str, 
        db_session: AsyncSession
    ) -> bool:
        """
        Kiểm tra người dùng cóMCPplugin
        
        Args:
            user_id: người dùngID
            db_session: cơ sở dữ liệuphiên
            
        Returns:
            có plugin nào được bật không
        """
        try:
            query = select(MCPPlugin.id).where(
                MCPPlugin.user_id == user_id,
                MCPPlugin.enabled == True,
                MCPPlugin.plugin_type.in_(["http", "streamable_http", "sse"])
            ).limit(1)
            
            result = await db_session.execute(query)
            return result.scalar() is not None
            
        except Exception as e:
            logger.warning(f"Kiểm tra người dùngMCPplugin thất bại: {e}")
            return False
    
    async def get_user_tools(
        self,
        user_id: str,
        db_session: AsyncSession,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        LấyMCPDanh sách công cụ (OpenAIđịnh dạng)
        
        Args:
            user_id: người dùngID
            db_session: cơ sở dữ liệuphiên
            use_cache: Có dùng bộ nhớ đệm không
            force_refresh: Có buộc làm mới không
            
        Returns:
            - None: Người dùng chưa cấu hình hoặc chưa bật bất kỳMCPplugin
            - []: Có cấu hình nhưng không có công cụ khả dụng
            - List[Dict]: OpenAI Function CallingDanh sách công cụ định dạng
        """
        now = datetime.now()
        
        # Kiểm tra bộ nhớ đệm
        if use_cache and not force_refresh and user_id in self._cache:
            cache_entry = self._cache[user_id]
            if now < cache_entry.expire_time:
                cache_entry.hit_count += 1
                logger.debug(f"🎯 Trúng bộ nhớ đệm công cụ của người dùng: {user_id} (Số lần trúng: {cache_entry.hit_count})")
                return cache_entry.tools
            else:
                del self._cache[user_id]
                logger.debug(f"⏰ Bộ nhớ đệm công cụ của người dùng hết hạn: {user_id}")
        
        # Tải từ cơ sở dữ liệu
        try:
            tools = await self._load_user_tools(user_id, db_session)
            
            # Cập nhật bộ nhớ đệm
            self._cache[user_id] = UserToolsCache(
                tools=tools,
                expire_time=now + self._cache_ttl
            )
            
            if tools:
                logger.info(f"🔧 người dùng {user_id} đã tải {len(tools)} công cụ MCP")
            else:
                logger.debug(f"📭 người dùng {user_id} Không cóMCPcông cụ")
            
            return tools
            
        except Exception as e:
            logger.error(f"❌ Tải người dùngMCPcông cụthất bại: {e}")
            return None
    
    async def _load_user_tools(
        self,
        user_id: str,
        db_session: AsyncSession
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Tải từ cơ sở dữ liệu cácMCPplugin mà người dùng đã bật và lấy công cụ
        """
        # Truy vấn các plugin đã bật
        query = select(MCPPlugin).where(
            MCPPlugin.user_id == user_id,
            MCPPlugin.enabled == True,
            MCPPlugin.plugin_type.in_(["http", "streamable_http", "sse"])
        ).order_by(MCPPlugin.sort_order)
        
        result = await db_session.execute(query)
        plugins = result.scalars().all()
        
        if not plugins:
            self._tool_metadata[user_id] = {}
            return None
        
        all_tools = []
        metadata: Dict[str, Dict[str, Any]] = {}
        
        for plugin in plugins:
            try:
                # Xác định loại plugin
                plugin_type = plugin.plugin_type
                if plugin_type == "http":
                    plugin_type = "streamable_http"  # Mặc định dùngstreamable_http
                
                # Đảm bảo plugin đã đăng ký tớiMCPclient
                await mcp_client.ensure_registered(
                    user_id=user_id,
                    plugin_name=plugin.plugin_name,
                    url=plugin.server_url,
                    plugin_type=plugin_type,
                    headers=plugin.headers
                )
                
                # Lấy danh sách công cụ
                plugin_tools = await mcp_client.get_tools(user_id, plugin.plugin_name)
                
                # Chuyển đổi thànhOpenAIđịnh dạng
                formatted = mcp_client.format_tools_for_openai(plugin_tools, plugin.plugin_name)
                for source_tool, formatted_tool in zip(plugin_tools, formatted):
                    function_name = formatted_tool.get("function", {}).get("name")
                    if function_name:
                        metadata[function_name] = dict(source_tool.get("annotations") or {})
                all_tools.extend(formatted)
                
                logger.debug(f"✅ Từ plugin {plugin.plugin_name} đã tải {len(formatted)} công cụ")
                
            except Exception as e:
                logger.warning(f"⚠️ Tải plugin {plugin.plugin_name} công cụthất bại: {e}")
                continue
        
        self._tool_metadata[user_id] = metadata
        return all_tools if all_tools else None

    def get_tool_metadata(self, user_id: str, tool_name: str) -> Dict[str, Any]:
        """trả về MCP Siêu dữ liệu phía máy chủ của công cụ; trả về dict rỗng khi thiếu siêu dữ liệu."""
        return dict(self._tool_metadata.get(user_id, {}).get(tool_name) or {})
    
    def invalidate_cache(self, user_id: Optional[str] = None):
        """
        Làm bộ nhớ đệm hết hiệu lực
        
        Args:
            user_id: người dùngID, khi làNonexóa mọi bộ nhớ đệm
        """
        if user_id:
            self._tool_metadata.pop(user_id, None)
            if user_id in self._cache:
                del self._cache[user_id]
                logger.debug(f"🧹 Dọn dẹp bộ nhớ đệm công cụ của người dùng: {user_id}")
        else:
            count = len(self._cache)
            self._cache.clear()
            self._tool_metadata.clear()
            logger.info(f"🧹 Dọn dẹp mọi bộ nhớ đệm công cụ của người dùng ({count})")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Lấy thống kê bộ nhớ đệm"""
        now = datetime.now()
        return {
            "total_entries": len(self._cache),
            "total_hits": sum(e.hit_count for e in self._cache.values()),
            "cache_ttl_minutes": self._cache_ttl.total_seconds() / 60,
            "entries": [
                {
                    "user_id": uid,
                    "tools_count": len(e.tools) if e.tools else 0,
                    "hit_count": e.hit_count,
                    "expired": now >= e.expire_time,
                    "expire_time": e.expire_time.isoformat()
                }
                for uid, e in self._cache.items()
            ]
        }


# Thể hiện đơn nhất toàn cục
mcp_tools_loader = MCPToolsLoader()