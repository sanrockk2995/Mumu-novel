"""Schema Pydantic Xưởng prompt"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ==================== Model request ====================

class ImportRequest(BaseModel):
    """Request nhập prompt"""
    custom_name: Optional[str] = Field(None, max_length=100, description="Tên tùy chỉnh")


class DownloadRequest(BaseModel):
    """Request ghi nhận tải xuống (dùng trên cloud)"""
    instance_id: str = Field(..., description="Định danh instance")
    user_identifier: str = Field(..., description="Định danh người dùng")


class PromptSubmissionCreate(BaseModel):
    """Request gửi prompt"""
    name: str = Field(..., max_length=100, description="Tên prompt")
    description: Optional[str] = Field(None, description="Mô tả prompt")
    prompt_content: str = Field(..., description="Nội dung prompt")
    category: str = Field(default="general", max_length=50, description="Phân loại")
    tags: Optional[List[str]] = Field(None, description="Danh sách nhãn")
    author_display_name: Optional[str] = Field(None, max_length=100, description="Tên hiển thị tác giả")
    is_anonymous: bool = Field(default=False, description="Có đăng ẩn danh hay không")
    source_style_id: Optional[int] = Field(None, description="ID phong cách viết nguồn")


class ReviewRequest(BaseModel):
    """Request kiểm duyệt"""
    action: str = Field(..., pattern="^(approve|reject)$", description="Thao tác: approve/reject")
    review_note: Optional[str] = Field(None, description="Ghi chú kiểm duyệt")
    category: Optional[str] = Field(None, description="Phân loại (có thể điều chỉnh)")
    tags: Optional[List[str]] = Field(None, description="Nhãn (có thể điều chỉnh)")


class AdminItemCreate(BaseModel):
    """Quản trị viên tạo prompt"""
    name: str = Field(..., max_length=100, description="Tên prompt")
    description: Optional[str] = Field(None, description="Mô tả prompt")
    prompt_content: str = Field(..., description="Nội dung prompt")
    category: str = Field(default="general", description="Phân loại")
    tags: Optional[List[str]] = Field(None, description="Danh sách nhãn")


class AdminItemUpdate(BaseModel):
    """Quản trị viên cập nhật prompt"""
    name: Optional[str] = Field(None, max_length=100, description="Tên prompt")
    description: Optional[str] = Field(None, description="Mô tả prompt")
    prompt_content: Optional[str] = Field(None, description="Nội dung prompt")
    category: Optional[str] = Field(None, description="Phân loại")
    tags: Optional[List[str]] = Field(None, description="Danh sách nhãn")
    status: Optional[str] = Field(None, description="Trạng thái")


# ==================== Model response ====================

class PromptWorkshopItemResponse(BaseModel):
    """Response hạng mục prompt"""
    id: str
    name: str
    description: Optional[str] = None
    prompt_content: str
    category: str
    tags: Optional[List[str]] = None
    author_name: Optional[str] = None
    is_official: bool
    download_count: int
    like_count: int
    is_liked: Optional[bool] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class PromptSubmissionResponse(BaseModel):
    """Response bản ghi gửi"""
    id: str
    name: str
    description: Optional[str] = None
    prompt_content: Optional[str] = None
    category: str
    tags: Optional[List[str]] = None
    author_display_name: Optional[str] = None
    is_anonymous: bool
    status: str
    review_note: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    source_instance: Optional[str] = None
    submitter_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class CategoryInfo(BaseModel):
    """Thông tin phân loại"""
    id: str
    name: str
    count: int


class WorkshopItemsListResponse(BaseModel):
    """Response danh sách prompt"""
    success: bool = True
    data: dict  # Bao gồm total, page, limit, items, categories


class WorkshopStatusResponse(BaseModel):
    """Response trạng thái dịch vụ"""
    mode: str
    instance_id: str
    cloud_url: Optional[str] = None
    cloud_connected: Optional[bool] = None