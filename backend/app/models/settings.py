"""Model dữ liệu cài đặt"""
from sqlalchemy import Column, String, Text, Float, Integer, DateTime, Boolean, Index
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Settings(Base):
    """Bảng cài đặt"""
    __tablename__ = "settings"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(50), nullable=False, unique=True, index=True, comment="ID người dùng")
    api_provider = Column(String(50), default="openai", comment="Nhà cung cấp API")
    api_key = Column(String(500), comment="Khóa API")
    api_base_url = Column(String(500), comment="Địa chỉ API tùy chỉnh")
    llm_model = Column(String(100), default="gpt-4", comment="Tên model")
    temperature = Column(Float, default=0.7, comment="Tham số temperature")
    max_tokens = Column(Integer, default=2000, comment="Số token tối đa")
    system_prompt = Column(Text, comment="Prompt cấp hệ thống, mỗi lần gọi AI đều dùng")
    disable_thinking = Column(Boolean, default=False, server_default="0", nullable=False, comment="Có tắt suy nghĩ của model không (bật thì model dạng suy nghĩ bỏ qua giai đoạn suy nghĩ, xuất thẳng chính văn)")

    # Cấu hình sinh ảnh bìa
    cover_api_provider = Column(String(50), comment="Nhà cung cấp API ảnh bìa")
    cover_api_key = Column(String(500), comment="Khóa API ảnh bìa")
    cover_api_base_url = Column(String(500), comment="Địa chỉ API tùy chỉnh ảnh bìa")
    cover_image_model = Column(String(100), comment="Tên model ảnh bìa")
    cover_enabled = Column(Boolean, default=False, server_default="0", nullable=False, comment="Có bật sinh ảnh bìa không")

    # Cấu hình SMTP cấp hệ thống (chỉ quản trị viên duy trì)
    smtp_provider = Column(String(50), default="qq", server_default="qq", nullable=False, comment="Nhà cung cấp SMTP")
    smtp_host = Column(String(255), comment="Host SMTP")
    smtp_port = Column(Integer, default=465, server_default="465", nullable=False, comment="Cổng SMTP")
    smtp_username = Column(String(255), comment="Tên người dùng SMTP")
    smtp_password = Column(String(500), comment="Mật khẩu hoặc mã ủy quyền SMTP")
    smtp_use_tls = Column(Boolean, default=False, server_default="0", nullable=False, comment="Có bật TLS không")
    smtp_use_ssl = Column(Boolean, default=True, server_default="1", nullable=False, comment="Có bật SSL không")
    smtp_from_email = Column(String(255), comment="Email người gửi")
    smtp_from_name = Column(String(255), default="MuMuAINovel", server_default="MuMuAINovel", nullable=False, comment="Tên người gửi")
    email_auth_enabled = Column(Boolean, default=True, server_default="1", nullable=False, comment="Có bật xác thực email không")
    email_register_enabled = Column(Boolean, default=True, server_default="1", nullable=False, comment="Có bật đăng ký email không")
    verification_code_ttl_minutes = Column(Integer, default=10, server_default="10", nullable=False, comment="Thời hạn hiệu lực mã xác minh (phút)")
    verification_resend_interval_seconds = Column(Integer, default=60, server_default="60", nullable=False, comment="Khoảng cách gửi lại mã xác minh (giây)")

    preferences = Column(Text, comment="Cài đặt sở thích khác (JSON)")
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
    )
    
    def __repr__(self):
        return f"<Settings(id={self.id}, user_id={self.user_id}, api_provider={self.api_provider})>"
