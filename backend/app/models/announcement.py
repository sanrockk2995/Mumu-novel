"""Model dữ liệu thông báo"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base


class Announcement(Base):
    """Thông báo hệ thống"""
    __tablename__ = "announcements"

    id = Column(String(36), primary_key=True, comment="UUID")
    title = Column(String(120), nullable=False, comment="Tiêu đề thông báo")
    content = Column(Text, nullable=False, comment="Nội dung thông báo")
    summary = Column(String(255), comment="Tóm tắt thông báo")
    level = Column(String(20), default="info", nullable=False, comment="Cấp độ: info/success/warning/error")
    status = Column(String(20), default="published", nullable=False, comment="Trạng thái: draft/published/hidden")
    pinned = Column(Boolean, default=False, nullable=False, comment="Có ghim lên đầu hay không")
    author_id = Column(String(100), comment="ID quản trị viên đăng")
    author_name = Column(String(100), comment="Tên hiển thị quản trị viên đăng")
    publish_at = Column(DateTime, server_default=func.now(), comment="Thời gian đăng")
    expire_at = Column(DateTime, comment="Thời gian hết hạn")
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")

    __table_args__ = (
        Index("idx_announcements_status", "status"),
        Index("idx_announcements_publish_at", "publish_at"),
        Index("idx_announcements_updated_at", "updated_at"),
        Index("idx_announcements_pinned", "pinned"),
    )

    def __repr__(self):
        return f"<Announcement(id={self.id}, title={self.title})>"
