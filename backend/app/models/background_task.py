"""Model dữ liệu task nền - dùng cho task sinh AI chạy lâu"""
from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON, Text
from sqlalchemy.sql import func
from app.database import Base
import uuid


class BackgroundTask(Base):
    """Bảng task nền - theo dõi mọi task sinh chạy lâu"""
    __tablename__ = "background_tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), nullable=False, index=True, comment="ID người dùng")
    project_id = Column(String(36), nullable=False, index=True, comment="ID dự án")
    
    # Loại task
    task_type = Column(String(50), nullable=False, comment="Loại task: outline_new/outline_continue/outline_expand/chapter_generate/chapter_batch/wizard")
    
    # Trạng thái task
    status = Column(String(20), default="pending", comment="Trạng thái task: pending/running/completed/failed/cancelled")
    progress = Column(Integer, default=0, comment="Phần trăm tiến độ (0-100)")
    status_message = Column(String(500), comment="Thông điệp trạng thái hiện tại")
    
    # Đầu vào/đầu ra task
    task_input = Column(JSON, comment="Tham số đầu vào task (JSON)")
    task_result = Column(JSON, comment="Kết quả task (JSON)")
    error_message = Column(Text, comment="Thông tin lỗi")
    
    # Chi tiết tiến độ (dùng để frontend hiển thị tiến độ realtime)
    progress_details = Column(JSON, comment="Chi tiết tiến độ: {stage, message, word_count, v.v.}")
    
    # Hỗ trợ hủy
    cancel_requested = Column(Boolean, default=False, comment="Có yêu cầu hủy không")
    
    # Thông tin thử lại
    retry_count = Column(Integer, default=0, comment="Số lần đã thử lại")
    max_retries = Column(Integer, default=3, comment="Số lần thử lại tối đa")
    
    # Ghi nhận thời gian
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    started_at = Column(DateTime, comment="Thời gian bắt đầu")
    completed_at = Column(DateTime, comment="Thời gian hoàn thành")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    def __repr__(self):
        return f"<BackgroundTask(id={self.id[:8]}, type={self.task_type}, status={self.status}, progress={self.progress}%)>"