"""Model dữ liệu dàn ý"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Outline(Base):
    """Bảng dàn ý"""
    __tablename__ = "outlines"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False, comment="Tiêu đề dàn ý")
    content = Column(Text, comment="Nội dung dàn ý")
    structure = Column(Text, comment="Dữ liệu dàn ý cấu trúc (JSON)")
    order_index = Column(Integer, comment="Số thứ tự sắp xếp")
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    def __repr__(self):
        return f"<Outline(id={self.id}, title={self.title})>"