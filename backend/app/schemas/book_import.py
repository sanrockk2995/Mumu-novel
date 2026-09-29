"""Schema Pydantic liên quan đến nhập sách bóc tách"""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


TaskStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
ImportMode = Literal["append", "overwrite"]
ExtractLevel = Literal["basic", "standard", "deep"]
WarningLevel = Literal["info", "warning", "error"]
BookImportExtractMode = Literal["tail", "full"]


class BookImportWarning(BaseModel):
    """Thông tin cảnh báo nhập"""
    code: str = Field(..., description="Mã cảnh báo")
    message: str = Field(..., description="Nội dung cảnh báo")
    level: WarningLevel = Field(default="warning", description="Cấp độ cảnh báo")


class ProjectSuggestion(BaseModel):
    """Thông tin gợi ý dự án (có thể sửa ở trang xem trước)"""
    title: str = Field(..., min_length=1, max_length=200, description="Tiêu đề dự án")
    description: Optional[str] = Field(None, description="Giới thiệu dự án")
    theme: Optional[str] = Field(None, description="Chủ đề")
    genre: Optional[str] = Field(None, description="Thể loại")
    narrative_perspective: str = Field(default="第三人称", description="Góc nhìn trần thuật")
    target_words: int = Field(default=100000, ge=1000, description="Số từ mục tiêu (mặc định 100 nghìn từ)")


class BookImportChapter(BaseModel):
    """Chương xem trước"""
    title: str = Field(..., min_length=1, max_length=200, description="Tiêu đề chương")
    content: str = Field(default="", description="Nội dung chính chương")
    summary: Optional[str] = Field(None, description="Tóm tắt chương")
    chapter_number: int = Field(..., ge=1, description="Số thứ tự chương")
    outline_title: Optional[str] = Field(None, description="Tiêu đề dàn ý liên kết (tùy chọn)")


class BookImportOutline(BaseModel):
    """Dàn ý xem trước"""
    title: str = Field(..., min_length=1, max_length=200, description="Tiêu đề dàn ý")
    content: Optional[str] = Field(None, description="Nội dung dàn ý")
    order_index: int = Field(..., ge=1, description="Số thứ tự sắp xếp")
    structure: Optional[dict[str, Any]] = Field(None, description="Dàn ý cấu trúc (nhất quán với cấu trúc sinh dàn ý của hệ thống)")


class BookImportTaskCreateRequest(BaseModel):
    """Request tạo tác vụ bóc tách sách"""
    extract_mode: BookImportExtractMode = Field(default="tail", description="Phạm vi trích: tail=cắt chương cuối, full=toàn bộ sách")
    tail_chapter_count: int = Field(default=10, ge=5, le=9999, description="Khi extract_mode=tail, số chương cuối cần cắt; phải là bội số của 5, vượt quá 50 sẽ xử lý như toàn bộ sách")


class BookImportTaskCreateResponse(BaseModel):
    """Response tạo tác vụ"""
    task_id: str
    status: TaskStatus


class BookImportTaskStatusResponse(BaseModel):
    """Response trạng thái tác vụ"""
    task_id: str
    status: TaskStatus
    progress: int = Field(..., ge=0, le=100)
    message: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BookImportPreviewResponse(BaseModel):
    """Response dữ liệu xem trước"""
    task_id: str
    project_suggestion: ProjectSuggestion
    chapters: list[BookImportChapter]
    outlines: list[BookImportOutline]
    warnings: list[BookImportWarning]


class BookImportApplyRequest(BaseModel):
    """Request xác nhận nhập (hỗ trợ dữ liệu đã chỉnh sửa ở frontend)"""
    project_suggestion: ProjectSuggestion
    chapters: list[BookImportChapter]
    outlines: list[BookImportOutline] = Field(default_factory=list)
    import_mode: ImportMode = Field(default="append", description="Chế độ nhập")


class BookImportApplyResponse(BaseModel):
    """Response xác nhận nhập"""
    success: bool
    project_id: str
    statistics: dict[str, int]
    warnings: list[BookImportWarning] = Field(default_factory=list)


class BookImportRetryRequest(BaseModel):
    """Request thử lại bước thất bại"""
    steps: list[str] = Field(..., min_length=1, description="Danh sách tên bước cần thử lại, ví dụ world_building / career_system / characters")
