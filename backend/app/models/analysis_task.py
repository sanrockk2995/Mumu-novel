"""Model tác vụ phân tích - theo dõi trạng thái tác vụ phân tích chương bất đồng bộ"""
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.database import Base
import uuid


class AnalysisTask(Base):
    """
    Bảng tác vụ phân tích - theo dõi trạng thái thực thi tác vụ phân tích bất đồng bộ
    
    Luồng chuyển trạng thái: pending -> running -> completed/failed
    """
    __tablename__ = "analysis_tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="ID tác vụ")
    chapter_id = Column(String(36), ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False, comment="ID chương")
    user_id = Column(String(50), nullable=False, comment="ID người dùng")
    project_id = Column(String(36), nullable=False, comment="ID dự án")
    
    # Trạng thái tác vụ
    status = Column(String(20), nullable=False, default='pending', comment="Trạng thái tác vụ: pending/running/completed/failed")
    progress = Column(Integer, default=0, comment="Tiến độ 0-100")
    error_message = Column(Text, nullable=True, comment="Thông báo lỗi")
    
    # Dấu thời gian
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    started_at = Column(DateTime, nullable=True, comment="Thời gian bắt đầu thực thi")
    completed_at = Column(DateTime, nullable=True, comment="Thời gian hoàn thành")

    # Thời gian lưu trữ khỏi panel tác vụ. Lưu trữ chỉ ẩn bản ghi tác vụ, không ảnh hưởng việc đánh giá trạng thái phân tích chương.
    archived_at = Column(DateTime, nullable=True, comment="Thời gian lưu trữ khỏi panel tác vụ")
    
    # Index tối ưu truy vấn
    __table_args__ = (
        Index('idx_chapter_id_created', 'chapter_id', 'created_at'),
        Index('idx_status', 'status'),
        Index('idx_analysis_task_panel', 'project_id', 'user_id', 'archived_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AnalysisTask(id={self.id[:8]}..., chapter_id={self.chapter_id[:8]}..., status={self.status})>"
