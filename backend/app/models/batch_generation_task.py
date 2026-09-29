"""Model dữ liệu tác vụ sinh hàng loạt"""
from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON
from sqlalchemy.sql import func
from app.database import Base
import uuid


class BatchGenerationTask(Base):
    """Bảng tác vụ sinh hàng loạt"""
    __tablename__ = "batch_generation_tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), nullable=False, comment="ID dự án")
    user_id = Column(String(100), nullable=False, comment="ID người dùng")
    
    # Cấu hình tác vụ
    start_chapter_number = Column(Integer, nullable=False, comment="Số thứ tự chương bắt đầu")
    chapter_count = Column(Integer, nullable=False, comment="Số lượng chương cần sinh")
    chapter_ids = Column(JSON, nullable=False, comment="Danh sách ID chương cần sinh")
    style_id = Column(Integer, comment="ID phong cách viết sử dụng")
    target_word_count = Column(Integer, default=3000, comment="Số từ mục tiêu")
    enable_analysis = Column(Boolean, default=False, comment="Có bật phân tích đồng bộ hay không")
    
    # Trạng thái tác vụ
    status = Column(String(20), default="pending", comment="Trạng thái tác vụ: pending/running/completed/failed/cancelled")
    total_chapters = Column(Integer, default=0, comment="Tổng số chương")
    completed_chapters = Column(Integer, default=0, comment="Số chương đã hoàn thành")
    failed_chapters = Column(JSON, default=list, comment="Danh sách thông tin chương thất bại")
    current_chapter_id = Column(String(36), comment="ID chương đang sinh")
    current_chapter_number = Column(Integer, comment="Số thứ tự chương đang sinh")
    current_retry_count = Column(Integer, default=0, comment="Số lần thử lại của chương hiện tại")
    max_retries = Column(Integer, default=3, comment="Số lần thử lại tối đa")
    
    # Ghi thời gian
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    started_at = Column(DateTime, comment="Thời gian bắt đầu")
    completed_at = Column(DateTime, comment="Thời gian hoàn thành")
    
    # Thông báo lỗi
    error_message = Column(String(500), comment="Thông báo lỗi")
    
    def __repr__(self):
        return f"<BatchGenerationTask(id={self.id}, status={self.status}, completed={self.completed_chapters}/{self.total_chapters})>"