"""Định nghĩa Schema liên quan đến sinh lại chương"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class PreserveElementsConfig(BaseModel):
    """Cấu hình phần tử giữ lại"""
    preserve_structure: bool = Field(False, description="Có giữ cấu trúc tổng thể hay không")
    preserve_dialogues: List[str] = Field(default_factory=list, description="Từ khóa đoạn hội thoại cần giữ lại")
    preserve_plot_points: List[str] = Field(default_factory=list, description="Từ khóa điểm tình tiết cần giữ lại")
    preserve_character_traits: bool = Field(True, description="Giữ nhất quán tính cách nhân vật")


class ChapterRegenerateRequest(BaseModel):
    """Request sinh lại chương"""
    
    # Nguồn sửa đổi
    modification_source: str = Field("custom", description="Nguồn sửa đổi: custom/analysis_suggestions/mixed")
    
    # Dựa trên gợi ý phân tích
    selected_suggestion_indices: Optional[List[int]] = Field(None, description="Danh sách chỉ số gợi ý đã chọn")
    
    # Chỉ thị sửa đổi tùy chỉnh
    custom_instructions: Optional[str] = Field(None, description="Yêu cầu sửa đổi tùy chỉnh của người dùng")
    
    # Cấu hình giữ lại
    preserve_elements: Optional[PreserveElementsConfig] = Field(None, description="Cấu hình phần tử giữ lại")
    
    # Tham số sinh
    style_id: Optional[int] = Field(None, description="ID phong cách viết")
    target_word_count: int = Field(3000, description="Số từ mục tiêu", ge=500, le=10000)
    focus_areas: List[str] = Field(default_factory=list, description="Hướng tối ưu trọng điểm")
    
    # Quản lý phiên bản
    save_as_version: bool = Field(True, description="Có lưu thành phiên bản mới hay không")
    version_note: Optional[str] = Field(None, description="Mô tả phiên bản", max_length=500)
    auto_apply: bool = Field(False, description="Có tự động áp dụng (thay thế nội dung hiện tại) hay không")


class RegenerationTaskResponse(BaseModel):
    """Response tác vụ sinh lại"""
    task_id: str
    chapter_id: str
    status: str
    message: str
    estimated_time_seconds: int = 120


class RegenerationTaskStatus(BaseModel):
    """Trạng thái tác vụ sinh lại"""
    task_id: str
    chapter_id: str
    status: str
    progress: int
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Thông tin kết quả
    original_word_count: Optional[int] = None
    regenerated_word_count: Optional[int] = None
    version_number: Optional[int] = None

