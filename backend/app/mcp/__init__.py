"""Module MCP - quản lý client MCP thống nhất

Module này cung cấp interface quản lý thống nhất cho client MCP (Model Context Protocol).

Cách dùng khuyến nghị:
    from app.mcp import mcp_client, MCPPluginConfig
    
    # Đăng ký plugin
    await mcp_client.register(MCPPluginConfig(
        user_id="user123",
        plugin_name="exa-search",
        url="http://localhost:8000/mcp"
    ))
    
    # Lấy công cụ
    tools = await mcp_client.get_tools("user123", "exa-search")
    
    # Gọi công cụ
    result = await mcp_client.call_tool("user123", "exa-search", "web_search", {"query": "..."})
    
    # Đăng ký callback thay đổi trạng thái
    from app.mcp.status_sync import register_status_sync
    register_status_sync()
"""

from .facade import mcp_client, MCPClientFacade, MCPPluginConfig, MCPError, PluginStatus
from .status_sync import register_status_sync

__all__ = [
    "mcp_client",
    "MCPClientFacade",
    "MCPPluginConfig",
    "MCPError",
    "PluginStatus",
    "register_status_sync",
]