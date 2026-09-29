"""Model dữ liệu template prompt"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base
import uuid


class PromptTemplate(Base):
    """Bảng template prompt"""
    __tablename__ = "prompt_templates"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(50), nullable=False, index=True, comment="ID người dùng")
    template_key = Column(String(100), nullable=False, comment="Tên khóa template")
    template_name = Column(String(200), nullable=False, comment="Tên hiển thị template")
    template_content = Column(Text, nullable=False, comment="Nội dung template")
    description = Column(Text, comment="Mô tả template")
    category = Column(String(50), comment="Phân loại template")
    parameters = Column(Text, comment="Định nghĩa tham số template (JSON)")
    is_active = Column(Boolean, default=True, comment="Có bật hay không")
    is_system_default = Column(Boolean, default=False, comment="Có phải template mặc định của hệ thống")
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    __table_args__ = (
        Index('idx_user_template', 'user_id', 'template_key', unique=True),
    )
    
    def __repr__(self):
        return f"<PromptTemplate(id={self.id}, user_id={self.user_id}, template_key={self.template_key})>"