"""Schema Pydantic plugin MCP"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class MCPToolSchema(BaseModel):
    """Định nghĩa công cụ MCP"""
    name: str
    description: Optional[str] = None
    inputSchema: Optional[Dict[str, Any]] = None
    category: Optional[str] = None


class MCPPluginBase(BaseModel):
    """Schema cơ bản plugin"""
    plugin_name: str = Field(..., description="Định danh duy nhất plugin")
    display_name: Optional[str] = Field(None, description="Tên hiển thị")
    description: Optional[str] = Field(None, description="Mô tả plugin")
    plugin_type: str = Field(default="http", description="Loại plugin: http/stdio")
    category: str = Field(default="general", description="Phân loại")
    sort_order: int = Field(default=0, description="Thứ tự sắp xếp")


class MCPPluginCreate(MCPPluginBase):
    """Tạo plugin"""
    server_url: Optional[str] = Field(None, description="URL máy chủ (loại HTTP)")
    command: Optional[str] = Field(None, description="Lệnh khởi động (loại stdio)")
    args: Optional[List[str]] = Field(None, description="Tham số lệnh")
    env: Optional[Dict[str, str]] = Field(None, description="Biến môi trường")
    headers: Optional[Dict[str, str]] = Field(None, description="Header request HTTP")
    config: Optional[Dict[str, Any]] = Field(None, description="Cấu hình riêng của plugin")
    enabled: bool = Field(default=True, description="Có bật hay không")


class MCPPluginSimpleCreate(BaseModel):
    """Tạo plugin đơn giản (qua JSON cấu hình MCP chuẩn)"""
    config_json: str = Field(..., description="Chuỗi JSON cấu hình MCP chuẩn")
    enabled: bool = Field(default=True, description="Có bật hay không")
    category: str = Field(default="general", description="Phân loại plugin")


class MCPPluginUpdate(BaseModel):
    """Cập nhật plugin"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    server_url: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    headers: Optional[Dict[str, str]] = None
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    category: Optional[str] = None
    sort_order: Optional[int] = None


class MCPPluginResponse(BaseModel):
    """Response plugin - sau tối ưu chỉ trả các trường cần thiết"""
    id: str
    plugin_name: str
    display_name: str
    description: Optional[str] = None
    plugin_type: str
    category: str
    
    # Trường loại HTTP
    server_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    
    # Trường loại Stdio
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    
    # Trường trạng thái
    enabled: bool
    status: str
    last_error: Optional[str] = None
    last_test_at: Optional[datetime] = None
    
    # Dấu thời gian
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MCPToolCall(BaseModel):
    """Request gọi công cụ"""
    plugin_id: str = Field(..., description="ID plugin")
    tool_name: str = Field(..., description="Tên công cụ")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tham số công cụ")


class MCPTestResult(BaseModel):
    """Kết quả kiểm tra"""
    success: bool
    message: str
    response_time_ms: Optional[float] = None
    tools_count: Optional[int] = None
    tools: Optional[List[MCPToolSchema]] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    suggestions: Optional[List[str]] = None