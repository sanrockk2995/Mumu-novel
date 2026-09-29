"""Model dữ liệu chương"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Chapter(Base):
    """Bảng chương"""
    __tablename__ = "chapters"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False, comment="Số thứ tự chương")
    title = Column(String(200), nullable=False, comment="Tiêu đề chương")
    content = Column(Text, comment="Nội dung chương")
    summary = Column(Text, comment="Tóm tắt chương")
    word_count = Column(Integer, default=0, comment="Thống kê số chữ")
    status = Column(String(20), default="draft", comment="Trạng thái chương")
    
    # Trường liên kết dàn ý (thực hiện quan hệ một-nhiều)
    outline_id = Column(String(36), ForeignKey("outlines.id", ondelete="SET NULL"), nullable=True, comment="ID dàn ý liên kết")
    sub_index = Column(Integer, default=1, comment="Số thứ tự chương con dưới dàn ý")
    
    # Dữ liệu kế hoạch mở rộng dàn ý (định dạng JSON)
    expansion_plan = Column(Text, comment="Chi tiết kế hoạch mở rộng (JSON): gồm key_events, character_focus, emotional_tone v.v.")
    
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    def __repr__(self):
        return f"<Chapter(id={self.id}, chapter_number={self.chapter_number}, title={self.title}, outline_id={self.outline_id})>"