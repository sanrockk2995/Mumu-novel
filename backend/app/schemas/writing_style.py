"""Schema phong cách viết"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class WritingStyleBase(BaseModel):
    """Model cơ bản phong cách viết"""
    name: str = Field(..., description="Tên phong cách")
    style_type: str = Field(..., description="Loại phong cách: preset/custom")
    preset_id: Optional[str] = Field(None, description="ID phong cách preset")
    description: Optional[str] = Field(None, description="Mô tả phong cách")
    prompt_content: str = Field(..., description="Nội dung prompt phong cách")


class WritingStyleCreate(BaseModel):
    """Tạo phong cách viết (chỉ dùng để tạo phong cách tùy chỉnh của người dùng)"""
    name: str = Field(..., description="Tên phong cách")
    style_type: Optional[str] = Field(None, description="Loại phong cách: preset/custom")
    preset_id: Optional[str] = Field(None, description="ID phong cách preset")
    description: Optional[str] = Field(None, description="Mô tả phong cách")
    prompt_content: str = Field(..., description="Nội dung prompt phong cách")


class WritingStyleUpdate(BaseModel):
    """Cập nhật phong cách viết"""
    name: Optional[str] = None
    description: Optional[str] = None
    prompt_content: Optional[str] = None


class SetDefaultStyleRequest(BaseModel):
    """Request đặt phong cách mặc định"""
    project_id: str = Field(..., description="ID dự án")


class WritingStyleResponse(BaseModel):
    """Response phong cách viết"""
    id: int
    user_id: Optional[str] = None  # NULL nghĩa là phong cách preset toàn cục
    name: str
    style_type: str
    preset_id: Optional[str] = None
    description: Optional[str] = None
    prompt_content: str
    is_default: bool
    order_index: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class WritingStyleListResponse(BaseModel):
    """Response danh sách phong cách viết"""
    total: int
    styles: list[WritingStyleResponse]