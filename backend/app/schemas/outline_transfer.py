"""Model liên quan đến nhập/xuất dàn ý."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


OutlineImportMode = Literal["append", "merge"]


class OutlineExportRequest(BaseModel):
    """Request xuất dàn ý. Khi outline_ids trống sẽ xuất toàn bộ dàn ý của dự án."""

    project_id: str = Field(..., min_length=1)
    outline_ids: Optional[list[str]] = None


class OutlineTransferItem(BaseModel):
    """Dữ liệu dàn ý có thể chuyển giữa các dự án, không chứa định danh database."""

    order_index: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    structure: Optional[str] = None


class OutlineSourceProject(BaseModel):
    """Thông tin dự án nguồn xuất, chỉ dùng cho gợi ý nhập."""

    title: str
    outline_mode: Literal["one-to-one", "one-to-many"]


class OutlineExportDocument(BaseModel):
    """File xuất chuyên dụng cho dàn ý. version là phiên bản định dạng file, không phải phiên bản ứng dụng."""

    version: str = "1.0.0"
    export_type: str = "outlines"
    export_time: datetime
    source_project: OutlineSourceProject
    count: int
    data: list[OutlineTransferItem]


class OutlineImportStatistics(BaseModel):
    total: int = 0
    will_create: int = 0
    will_update: int = 0
    will_create_chapters: int = 0


class OutlineImportPreviewResponse(BaseModel):
    valid: bool
    version: str = ""
    source_type: Literal["outlines", "project", "unknown"] = "unknown"
    source_project: Optional[OutlineSourceProject] = None
    target_outline_mode: Optional[Literal["one-to-one", "one-to-many"]] = None
    mode: OutlineImportMode
    statistics: OutlineImportStatistics = Field(default_factory=OutlineImportStatistics)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OutlineImportDetail(BaseModel):
    source_order_index: int
    target_order_index: int
    title: str
    action: Literal["created", "updated"]


class OutlineImportResult(BaseModel):
    success: bool
    message: str
    mode: OutlineImportMode
    imported: int
    updated: int
    created_chapters: int
    details: list[OutlineImportDetail] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
