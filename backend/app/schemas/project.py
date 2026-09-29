"""Model Pydantic liên quan đến dự án"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime


class ProjectBase(BaseModel):
    """Model cơ bản dự án"""
    title: str = Field(..., description="Tiêu đề dự án")
    description: Optional[str] = Field(None, description="Mô tả dự án")
    theme: Optional[str] = Field(None, description="Chủ đề")
    genre: Optional[str] = Field(None, description="Thể loại truyện")
    target_words: Optional[int] = Field(None, description="Số từ mục tiêu")
    outline_mode: Literal["one-to-one", "one-to-many"] = Field(
        default="one-to-many",
        description="Chế độ dàn ý-chương: one-to-one (chế độ truyền thống, 1 dàn ý → 1 chương) hoặc one-to-many (chế độ chi tiết, 1 dàn ý → N chương)"
    )


class ProjectCreate(ProjectBase):
    """Model request tạo dự án"""
    pass


class ProjectUpdate(BaseModel):
    """Model request cập nhật dự án"""
    title: Optional[str] = None
    description: Optional[str] = None
    theme: Optional[str] = None
    genre: Optional[str] = None
    target_words: Optional[int] = None
    status: Optional[str] = None
    # wizard_status và wizard_step chỉ được sửa qua API wizard, cập nhật thông thường không được phép
    world_time_period: Optional[str] = None
    world_location: Optional[str] = None
    world_atmosphere: Optional[str] = None
    world_rules: Optional[str] = None
    chapter_count: Optional[int] = None
    narrative_perspective: Optional[str] = None
    character_count: Optional[int] = None
    # current_words tự động tính từ nội dung chương, không cho phép sửa thủ công


class ProjectResponse(ProjectBase):
    """Model response dự án"""
    id: str  # Chuỗi UUID
    status: str
    current_words: int
    wizard_status: Optional[str] = None
    wizard_step: Optional[int] = None
    world_time_period: Optional[str] = None
    world_location: Optional[str] = None
    world_atmosphere: Optional[str] = None
    world_rules: Optional[str] = None
    chapter_count: Optional[int] = None
    narrative_perspective: Optional[str] = None
    character_count: Optional[int] = None
    cover_image_url: Optional[str] = None
    cover_prompt: Optional[str] = None
    cover_status: Optional[str] = None
    cover_error: Optional[str] = None
    cover_updated_at: Optional[datetime] = None
    outline_mode: str  # Khai báo rõ để đảm bảo có trong response
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    """Model response danh sách dự án"""
    total: int
    items: list[ProjectResponse]


class ProjectWizardRequest(BaseModel):
    """Model request wizard tạo dự án"""
    title: str = Field(..., description="Tên sách")
    theme: str = Field(..., description="Chủ đề")
    genre: Optional[str] = Field(None, description="Thể loại")
    chapter_count: int = Field(..., ge=1, description="Số lượng chương")
    narrative_perspective: str = Field(..., description="Góc nhìn trần thuật")
    character_count: int = Field(5, ge=5, description="Số lượng nhân vật (ít nhất 5)")
    target_words: Optional[int] = Field(None, description="Số từ mục tiêu")
    outline_mode: Literal["one-to-one", "one-to-many"] = Field(
        default="one-to-many",
        description="Chế độ dàn ý-chương"
    )


class WorldBuildingResponse(BaseModel):
    """Model response xây dựng thế giới"""
    time_period: str = Field(..., description="Bối cảnh thời gian")
    location: str = Field(..., description="Vị trí địa lý")
    atmosphere: str = Field(..., description="Tông không khí")
    rules: str = Field(..., description="Quy tắc thế giới")