"""Model dữ liệu cấu hình plugin MCP"""
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, Index, JSON
from sqlalchemy.sql import func
from app.database import Base
import uuid


class MCPPlugin(Base):
    """Bảng cấu hình plugin MCP"""
    __tablename__ = "mcp_plugins"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(50), nullable=False, index=True, comment="ID người dùng")
    
    # Thông tin cơ bản plugin
    plugin_name = Column(String(100), nullable=False, comment="Tên plugin (định danh duy nhất)")
    display_name = Column(String(200), nullable=False, comment="Tên hiển thị")
    description = Column(Text, comment="Mô tả plugin")
    plugin_type = Column(String(50), default="http", comment="Loại plugin: http/stdio")
    
    # Cấu hình kết nối
    server_url = Column(String(500), comment="URL máy chủ (loại HTTP)")
    command = Column(String(500), comment="Lệnh khởi động (loại stdio)")
    args = Column(JSON, comment="Tham số lệnh (loại stdio)")
    env = Column(JSON, comment="Biến môi trường")
    headers = Column(JSON, comment="Header request HTTP")
    
    # Cấu hình plugin
    config = Column(JSON, comment="Cấu hình riêng của plugin (JSON)")
    tools = Column(JSON, comment="Danh sách công cụ cung cấp")
    
    # Quản lý trạng thái
    enabled = Column(Boolean, default=True, comment="Có bật không")
    status = Column(String(50), default="inactive", comment="Trạng thái: active/inactive/error")
    last_error = Column(Text, comment="Thông tin lỗi cuối cùng")
    last_test_at = Column(DateTime, comment="Thời gian test cuối")
    
    # Sắp xếp và nhóm
    category = Column(String(100), default="general", comment="Phân loại")
    sort_order = Column(Integer, default=0, comment="Thứ tự sắp xếp")
    
    # Dấu thời gian
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    __table_args__ = (
        Index('idx_user_plugin', 'user_id', 'plugin_name', unique=True),
        Index('idx_user_enabled', 'user_id', 'enabled'),
    )
    
    def __repr__(self):
        return f"<MCPPlugin(id={self.id}, name={self.plugin_name}, enabled={self.enabled})>"