"""Model task sinh lại chương"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.sql import func
from app.database import Base
import uuid


class RegenerationTask(Base):
    """Bảng task sinh lại chương"""
    __tablename__ = "regeneration_tasks"
    
    # Thông tin cơ bản
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False, index=True)
    analysis_id = Column(String(36), nullable=True, comment="ID kết quả phân tích liên kết")
    user_id = Column(String(50), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)
    
    # Chỉ thị chỉnh sửa
    modification_instructions = Column(Text, nullable=False, comment="Chỉ thị chỉnh sửa tổng hợp")
    original_suggestions = Column(JSON, comment="Danh sách gợi ý gốc từ phân tích")
    selected_suggestion_indices = Column(JSON, comment="Chỉ số gợi ý người dùng chọn")
    custom_instructions = Column(Text, comment="Ý kiến chỉnh sửa tùy chỉnh của người dùng")
    
    # Tham số sinh
    style_id = Column(Integer, nullable=True, comment="ID phong cách viết")
    target_word_count = Column(Integer, default=3000, comment="Số chữ mục tiêu")
    focus_areas = Column(JSON, comment="Hướng tối ưu trọng điểm")
    preserve_elements = Column(JSON, comment="Cấu hình yếu tố cần giữ")
    
    # Theo dõi trạng thái
    status = Column(String(20), default='pending', comment="pending/running/completed/failed")
    progress = Column(Integer, default=0, comment="Tiến độ 0-100")
    error_message = Column(Text, nullable=True)
    
    # Phiên bản nội dung
    original_content = Column(Text, comment="Ảnh chụp nội dung chương gốc")
    original_word_count = Column(Integer, comment="Số chữ gốc")
    regenerated_content = Column(Text, comment="Nội dung sinh lại")
    regenerated_word_count = Column(Integer, comment="Số chữ nội dung mới")
    version_number = Column(Integer, default=1, comment="Số phiên bản")
    version_note = Column(String(500), comment="Ghi chú phiên bản")
    
    # Dấu thời gian
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<RegenerationTask(id={self.id[:8]}..., chapter_id={self.chapter_id[:8]}..., status={self.status})>"

