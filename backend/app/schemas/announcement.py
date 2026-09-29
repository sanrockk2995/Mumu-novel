"""Pydantic Schema thông báo"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AnnouncementCreate(BaseModel):
    """Request tạo thông báo"""
    title: str = Field(..., max_length=120, description="Tiêu đề thông báo")
    content: str = Field(..., description="Nội dung thông báo")
    summary: Optional[str] = Field(None, max_length=255, description="Tóm tắt thông báo")
    level: str = Field(default="info", pattern="^(info|success|warning|error)$", description="Cấp độ thông báo")
    status: str = Field(default="published", pattern="^(draft|published|hidden)$", description="Trạng thái thông báo")
    pinned: bool = Field(default=False, description="Có ghim lên đầu không")
    publish_at: Optional[datetime] = Field(None, description="Thời gian phát hành")
    expire_at: Optional[datetime] = Field(None, description="Thời gian hết hạn")


class AnnouncementUpdate(BaseModel):
    """Request cập nhật thông báo"""
    title: Optional[str] = Field(None, max_length=120, description="Tiêu đề thông báo")
    content: Optional[str] = Field(None, description="Nội dung thông báo")
    summary: Optional[str] = Field(None, max_length=255, description="Tóm tắt thông báo")
    level: Optional[str] = Field(None, pattern="^(info|success|warning|error)$", description="Cấp độ thông báo")
    status: Optional[str] = Field(None, pattern="^(draft|published|hidden)$", description="Trạng thái thông báo")
    pinned: Optional[bool] = Field(None, description="Có ghim lên đầu không")
    publish_at: Optional[datetime] = Field(None, description="Thời gian phát hành")
    expire_at: Optional[datetime] = Field(None, description="Thời gian hết hạn")


class AnnouncementResponse(BaseModel):
    """Response thông báo"""
    id: str
    title: str
    content: str
    summary: Optional[str] = None
    level: str
    status: Optional[str] = None
    pinned: bool
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    publish_at: Optional[datetime] = None
    expire_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnnouncementListData(BaseModel):
    """Dữ liệu danh sách thông báo"""
    total: int
    page: int = 1
    limit: int = 20
    items: List[AnnouncementResponse]
    latest_updated_at: Optional[datetime] = None
    server_time: datetime


class AnnouncementListResponse(BaseModel):
    """Response danh sách thông báo"""
    success: bool = True
    data: AnnouncementListData


class AnnouncementStatusResponse(BaseModel):
    """Response trạng thái dịch vụ thông báo"""
    mode: str
    instance_id: str
    cloud_url: Optional[str] = None
    cloud_connected: Optional[bool] = None
