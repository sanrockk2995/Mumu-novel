"""Schema Pydantic quản lýphục bút (gợi mở/ẩn dụ tình tiết)"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ForeshadowStatus(str, Enum):
    """Enum trạng thái phục bút"""
    PENDING = "pending"  # Chờ gieo
    PLANTED = "planted"  # Đã gieo
    RESOLVED = "resolved"  # Đã thu hồi
    PARTIALLY_RESOLVED = "partially_resolved"  # Thu hồi một phần
    ABANDONED = "abandoned"  # Đã bỏ


class ForeshadowSourceType(str, Enum):
    """Loại nguồn phục bút"""
    ANALYSIS = "analysis"  # Trích từ phân tích
    MANUAL = "manual"  # Thêm thủ công


class ForeshadowCategory(str, Enum):
    """Phân loại phục bút"""
    IDENTITY = "identity"  # Thân thế
    MYSTERY = "mystery"  # Hồi hộp
    ITEM = "item"  # Vật phẩm
    RELATIONSHIP = "relationship"  # Quan hệ
    EVENT = "event"  # Sự kiện
    ABILITY = "ability"  # Năng lực
    PROPHECY = "prophecy"  # Lời tiên tri


class ForeshadowBase(BaseModel):
    """Thông tin cơ bản phục bút"""
    title: str = Field(..., min_length=1, max_length=200, description="Tiêu đề phục bút")
    content: str = Field(..., min_length=1, description="Nội dung/mô tả chi tiết phục bút")
    hint_text: Optional[str] = Field(None, description="Văn bản ám chỉ khi gieo phục bút")
    resolution_text: Optional[str] = Field(None, description="Văn bản hé lộ khi thu hồi phục bút")
    
    # Liên kết chương
    plant_chapter_number: Optional[int] = Field(None, ge=1, description="Số chương dự kiến gieo")
    target_resolve_chapter_number: Optional[int] = Field(None, ge=1, description="Số chương dự kiến thu hồi")
    
    # Trạng thái
    is_long_term: bool = Field(False, description="Có phải phục bút dài hơi hay không")
    
    # Mức quan trọng
    importance: float = Field(0.5, ge=0.0, le=1.0, description="Điểm quan trọng 0.0-1.0")
    strength: int = Field(5, ge=1, le=10, description="Cường độ phục bút 1-10")
    subtlety: int = Field(5, ge=1, le=10, description="Độ ẩn giấu 1-10")
    
    # Thông tin liên quan
    related_characters: Optional[List[str]] = Field(None, description="Danh sách tên nhân vật liên quan")
    tags: Optional[List[str]] = Field(None, description="Danh sách nhãn")
    category: Optional[str] = Field(None, description="Phân loại")
    
    # Ghi chú
    notes: Optional[str] = Field(None, description="Ghi chú sáng tác")
    resolution_notes: Optional[str] = Field(None, description="Mô tả cách thu hồi")
    
    # Cài đặt hỗ trợ AI
    auto_remind: bool = Field(True, description="Có tự động nhắc hay không")
    remind_before_chapters: int = Field(5, ge=1, le=20, description="Nhắc trước mấy chương")
    include_in_context: bool = Field(True, description="Có đưa vào ngữ cảnh sinh hay không")


class ForeshadowCreate(ForeshadowBase):
    """Request tạo phục bút"""
    project_id: str = Field(..., description="ID dự án")


class ForeshadowUpdate(BaseModel):
    """Request cập nhật phục bút"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    hint_text: Optional[str] = None
    resolution_text: Optional[str] = None
    
    plant_chapter_number: Optional[int] = Field(None, ge=1)
    target_resolve_chapter_number: Optional[int] = Field(None, ge=1)
    
    status: Optional[ForeshadowStatus] = None
    is_long_term: Optional[bool] = None
    
    importance: Optional[float] = Field(None, ge=0.0, le=1.0)
    strength: Optional[int] = Field(None, ge=1, le=10)
    subtlety: Optional[int] = Field(None, ge=1, le=10)
    urgency: Optional[int] = Field(None, ge=0, le=3)
    
    related_characters: Optional[List[str]] = None
    related_foreshadow_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    
    notes: Optional[str] = None
    resolution_notes: Optional[str] = None
    
    auto_remind: Optional[bool] = None
    remind_before_chapters: Optional[int] = Field(None, ge=1, le=20)
    include_in_context: Optional[bool] = None


class ForeshadowResponse(ForeshadowBase):
    """Response phục bút"""
    id: str
    project_id: str
    
    source_type: Optional[str] = None
    source_memory_id: Optional[str] = None
    source_analysis_id: Optional[str] = None
    
    plant_chapter_id: Optional[str] = None
    target_resolve_chapter_id: Optional[str] = None
    actual_resolve_chapter_id: Optional[str] = None
    actual_resolve_chapter_number: Optional[int] = None
    
    status: str = "pending"
    urgency: int = 0
    
    related_foreshadow_ids: Optional[List[str]] = None
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    planted_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ForeshadowListResponse(BaseModel):
    """Response danh sách phục bút"""
    total: int
    items: List[ForeshadowResponse]
    stats: Optional[dict] = None


class ForeshadowStatsResponse(BaseModel):
    """Response thống kê phục bút"""
    total: int
    pending: int
    planted: int
    resolved: int
    partially_resolved: int
    abandoned: int
    long_term_count: int
    overdue_count: int  # Số lượng quá hạn chưa thu hồi


class PlantForeshadowRequest(BaseModel):
    """Request đánh dấu gieo phục bút"""
    chapter_id: str = Field(..., description="ID chương gieo")
    chapter_number: int = Field(..., ge=1, description="Số chương gieo")
    hint_text: Optional[str] = Field(None, description="Văn bản ám chỉ")


class ResolveForeshadowRequest(BaseModel):
    """Request đánh dấu thu hồi phục bút"""
    chapter_id: str = Field(..., description="ID chương thu hồi")
    chapter_number: int = Field(..., ge=1, description="Số chương thu hồi")
    resolution_text: Optional[str] = Field(None, description="Văn bản hé lộ")
    is_partial: bool = Field(False, description="Có phải thu hồi một phần hay không")


class SyncFromAnalysisRequest(BaseModel):
    """Request đồng bộ phục bút từ phân tích"""
    chapter_ids: Optional[List[str]] = Field(None, description="Danh sách ID chương chỉ định, trống thì đồng bộ tất cả")
    overwrite_existing: bool = Field(False, description="Có ghi đè phục bút đã tồn tại hay không")
    auto_set_planted: bool = Field(True, description="Tự động đặt thành trạng thái đã gieo")


class SyncFromAnalysisResponse(BaseModel):
    """Response đồng bộ phục bút từ phân tích"""
    synced_count: int
    skipped_count: int
    resolved_count: int = 0
    new_foreshadows: List[ForeshadowResponse] = []
    skipped_reasons: List[dict] = []


class ForeshadowContextRequest(BaseModel):
    """Request lấy ngữ cảnh phục bút của chương"""
    chapter_number: int = Field(..., ge=1, description="Số chương")
    include_pending: bool = Field(True, description="Bao gồm phục bút chờ gieo")
    include_overdue: bool = Field(True, description="Bao gồm phục bút quá hạn")
    lookahead: int = Field(5, ge=1, le=20, description="Nhìn trước mấy chương")


class ForeshadowContextResponse(BaseModel):
    """Response ngữ cảnh phục bút"""
    chapter_number: int
    context_text: str
    pending_plant: List[ForeshadowResponse]  # Chương này chờ gieo
    pending_resolve: List[ForeshadowResponse]  # Sắp cần thu hồi
    overdue: List[ForeshadowResponse]  # Quá hạn chưa thu hồi
    recently_planted: List[ForeshadowResponse]  # Mới gieo gần đây (có thể dẫn dắt)