"""Model dữ liệu xưởng prompt"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, JSON, ForeignKey, Index
from sqlalchemy.sql import func
from app.database import Base


class PromptWorkshopItem(Base):
    """Hạng mục xưởng prompt - prompt công khai đã qua kiểm duyệt"""
    __tablename__ = "prompt_workshop_items"
    
    id = Column(String(36), primary_key=True, comment="UUID")
    name = Column(String(100), nullable=False, comment="Tên prompt")
    description = Column(Text, comment="Mô tả prompt")
    prompt_content = Column(Text, nullable=False, comment="Nội dung prompt")
    category = Column(String(50), default="general", comment="Phân loại")
    tags = Column(JSON, comment="Mảng nhãn")
    author_id = Column(String(255), comment="Định danh người dùng tác giả (ID instance:ID người dùng)")
    author_name = Column(String(100), comment="Tên hiển thị tác giả")
    source_instance = Column(String(255), comment="Định danh instance nguồn")
    is_official = Column(Boolean, default=False, comment="Có phải prompt chính thức không")
    download_count = Column(Integer, default=0, comment="Số lần tải/nhập")
    like_count = Column(Integer, default=0, comment="Số lượt thích")
    status = Column(String(20), default="active", comment="Trạng thái: active/hidden/deprecated")
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    __table_args__ = (
        Index('idx_workshop_items_category', 'category'),
        Index('idx_workshop_items_status', 'status'),
        Index('idx_workshop_items_download_count', 'download_count'),
        Index('idx_workshop_items_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<PromptWorkshopItem(id={self.id}, name={self.name})>"


class PromptSubmission(Base):
    """Prompt người dùng gửi chờ kiểm duyệt"""
    __tablename__ = "prompt_submissions"
    
    id = Column(String(36), primary_key=True, comment="UUID")
    submitter_id = Column(String(255), nullable=False, comment="Định danh người gửi (ID instance:ID người dùng)")
    submitter_name = Column(String(100), comment="Tên hiển thị người gửi")
    source_instance = Column(String(255), nullable=False, comment="Định danh instance nguồn")
    name = Column(String(100), nullable=False, comment="Tên prompt")
    description = Column(Text, comment="Mô tả prompt")
    prompt_content = Column(Text, nullable=False, comment="Nội dung prompt")
    category = Column(String(50), default="general", comment="Phân loại")
    tags = Column(JSON, comment="Mảng nhãn")
    author_display_name = Column(String(100), comment="Tên tác giả muốn hiển thị")
    is_anonymous = Column(Boolean, default=False, comment="Có đăng ẩn danh không")
    
    # Liên quan kiểm duyệt
    status = Column(String(20), default="pending", comment="Trạng thái: pending/approved/rejected")
    reviewer_id = Column(String(100), comment="ID người kiểm duyệt (quản trị viên đám mây)")
    review_note = Column(Text, comment="Ghi chú kiểm duyệt (lý do từ chối v.v.)")
    reviewed_at = Column(DateTime, comment="Thời gian kiểm duyệt")
    workshop_item_id = Column(String(36), comment="ID hạng mục xưởng liên kết sau khi duyệt")
    
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    __table_args__ = (
        Index('idx_submissions_submitter', 'submitter_id'),
        Index('idx_submissions_source', 'source_instance'),
        Index('idx_submissions_status', 'status'),
        Index('idx_submissions_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<PromptSubmission(id={self.id}, name={self.name}, status={self.status})>"


class PromptWorkshopLike(Base):
    """Bản ghi lượt thích prompt"""
    __tablename__ = "prompt_workshop_likes"
    
    id = Column(String(36), primary_key=True, comment="UUID")
    user_identifier = Column(String(255), nullable=False, comment="Định danh người dùng (ID instance:ID người dùng)")
    workshop_item_id = Column(String(36), ForeignKey("prompt_workshop_items.id", ondelete="CASCADE"), nullable=False, comment="ID hạng mục xưởng")
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    
    __table_args__ = (
        Index('idx_likes_user_item', 'user_identifier', 'workshop_item_id', unique=True),
    )
    
    def __repr__(self):
        return f"<PromptWorkshopLike(user={self.user_identifier}, item={self.workshop_item_id})>"