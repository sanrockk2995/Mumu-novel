"""Bảng liên kết phong cách mặc định dự án"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class ProjectDefaultStyle(Base):
    """Bảng liên kết phong cách mặc định dự án - ghi phong cách mặc định mỗi dự án chọn"""
    __tablename__ = "project_default_styles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="ID dự án")
    style_id = Column(Integer, ForeignKey("writing_styles.id", ondelete="CASCADE"), nullable=False, comment="ID phong cách")
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    # Đảm bảo mỗi dự án chỉ có một phong cách mặc định
    __table_args__ = (
        UniqueConstraint('project_id', name='uix_project_default_style'),
    )
    
    def __repr__(self):
        return f"<ProjectDefaultStyle(project_id={self.project_id}, style_id={self.style_id})>"