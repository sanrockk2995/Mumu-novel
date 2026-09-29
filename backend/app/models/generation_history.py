"""Model dữ liệu lịch sử sinh nội dung"""
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import uuid


class GenerationHistory(Base):
    """Bảng lịch sử sinh nội dung"""
    __tablename__ = "generation_history"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    prompt = Column(Text, comment="Prompt đã dùng")
    generated_content = Column(Text, comment="Nội dung đã sinh")
    model = Column(String(50), comment="Model đã dùng")
    tokens_used = Column(Integer, comment="Số token đã tiêu thụ")
    generation_time = Column(Float, comment="Thời gian sinh (giây)")
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    
    def __repr__(self):
        return f"<GenerationHistory(id={self.id}, model={self.model})>"