"""Model Pydantic liên quan đến dàn ý"""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class OutlineBase(BaseModel):
    """Model cơ bản dàn ý"""
    title: str = Field(..., description="Tiêu đề chương")
    content: str = Field(..., description="Tóm tắt nội dung chương")


class OutlineCreate(BaseModel):
    """Model request tạo dàn ý"""
    project_id: str = Field(..., description="ID dự án sở hữu")
    title: str = Field(..., description="Tiêu đề chương")
    content: str = Field(..., description="Tóm tắt nội dung chương")
    order_index: int = Field(..., description="Số thứ tự chương", ge=1)
    structure: Optional[str] = Field(None, description="Dữ liệu dàn ý cấu trúc (JSON)")


class OutlineUpdate(BaseModel):
    """Model request cập nhật dàn ý"""
    title: Optional[str] = None
    content: Optional[str] = None
    structure: Optional[str] = Field(None, description="Dữ liệu dàn ý cấu trúc (JSON)")
    # Không cho phép sửa order_index qua cập nhật thông thường, chỉ có thể điều chỉnh hàng loạt qua API reorder_outlines


class OutlineResponse(BaseModel):
    """Model response dàn ý"""
    id: str
    project_id: str
    title: str
    content: str
    structure: Optional[str] = None
    order_index: int
    has_chapters: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("content", mode="before")
    @classmethod
    def normalize_legacy_null_content(cls, value: Any) -> str:
        """Tương thích nội dung dàn ý NULL từ import lịch sử hoặc phiên bản cũ."""
        return "" if value is None else value

    model_config = ConfigDict(from_attributes=True)


class OutlineGenerateRequest(BaseModel):
    """Model request AI sinh dàn ý - hỗ trợ sinh mới hoàn toàn và viết nối thông minh"""
    project_id: str = Field(..., description="ID dự án")
    genre: Optional[str] = Field(None, description="Thể loại truyện, ví dụ: huyền huyễn, đô thị, trinh thám...")
    theme: str = Field(..., description="Chủ đề truyện")
    chapter_count: int = Field(..., ge=1, description="Số lượng chương")
    narrative_perspective: str = Field(..., description="Góc nhìn trần thuật")
    world_context: Optional[dict] = Field(None, description="Bối cảnh thế giới quan")
    characters_context: Optional[list] = Field(None, description="Thông tin nhân vật")
    target_words: int = Field(100000, description="Số từ mục tiêu")
    requirements: Optional[str] = Field(None, description="Yêu cầu đặc biệt khác")
    provider: Optional[str] = Field(None, description="Nhà cung cấp AI")
    model: Optional[str] = Field(None, description="Model AI")
    
    # Tham số liên quan đến viết nối
    mode: str = Field("auto", description="Chế độ sinh: auto (tự phán đoán), new (sinh mới), continue (viết nối)")
    story_direction: Optional[str] = Field(None, description="Gợi ý hướng phát triển cốt truyện (dùng khi viết nối)")
    plot_stage: str = Field("development", description="Giai đoạn cốt truyện: development (triển khai), climax (cao trào), ending (kết thúc)")
    keep_existing: bool = Field(False, description="Có giữ dàn ý hiện có khi viết nối")
    enable_mcp: bool = Field(True, description="Có bật tăng cường công cụ MCP (tìm kiếm tài liệu tham khảo thiết kế tình tiết)")


class ChapterOutlineGenerateRequest(BaseModel):
    """Model request sinh dàn ý cho một chương đơn"""
    outline_id: str = Field(..., description="ID dàn ý")
    context: Optional[str] = Field(None, description="Bối cảnh bổ sung")
    provider: Optional[str] = Field(None, description="Nhà cung cấp AI")
    model: Optional[str] = Field(None, description="Model AI")


class OutlineListResponse(BaseModel):
    """Model response danh sách dàn ý"""
    total: int
    items: list[OutlineResponse]


class ChapterPlanItem(BaseModel):
    """Hạng mục kế hoạch chương đơn"""
    sub_index: int = Field(..., description="Số thứ tự chương con", ge=1)
    title: str = Field(..., description="Tiêu đề chương")
    plot_summary: str = Field(..., description="Tóm tắt cốt truyện (200-300 từ)")
    key_events: list[str] = Field(..., description="Danh sách sự kiện then chốt")
    character_focus: list[str] = Field(..., description="Nhân vật chính liên quan")
    emotional_tone: str = Field(..., description="Tông cảm xúc")
    narrative_goal: str = Field(..., description="Mục tiêu trần thuật")
    conflict_type: str = Field(..., description="Loại xung đột")
    estimated_words: int = Field(3000, description="Số từ dự kiến", ge=1000)
    scenes: Optional[list[str]] = Field(None, description="Danh sách cảnh (tùy chọn)")


class OutlineExpansionRequest(BaseModel):
    """Model request mở rộng dàn ý thành nhiều chương (outline_id lấy từ path param)"""
    target_chapter_count: int = Field(3, description="Số chương mục tiêu", ge=1, le=10)
    expansion_strategy: str = Field("balanced", description="Chiến lược mở rộng: balanced (cân bằng), climax (trọng tâm cao trào), detail (chi tiết phong phú)")
    enable_scene_analysis: bool = Field(False, description="Có bao gồm kế hoạch cảnh hay không")
    auto_create_chapters: bool = Field(True, description="Có tự động tạo bản ghi chương hay không")
    provider: Optional[str] = Field(None, description="Nhà cung cấp AI")
    model: Optional[str] = Field(None, description="Model AI")


class OutlineExpansionResponse(BaseModel):
    """Model response mở rộng dàn ý"""
    outline_id: str = Field(..., description="ID dàn ý")
    outline_title: str = Field(..., description="Tiêu đề dàn ý")
    target_chapter_count: int = Field(..., description="Số chương mục tiêu")
    actual_chapter_count: int = Field(..., description="Số chương thực tế đã sinh")
    expansion_strategy: str = Field(..., description="Chiến lược mở rộng đã dùng")
    chapter_plans: list[ChapterPlanItem] = Field(..., description="Danh sách kế hoạch chương")
    created_chapters: Optional[list] = Field(None, description="Danh sách chương đã tạo")


class BatchOutlineExpansionRequest(BaseModel):
    """Model request mở rộng dàn ý hàng loạt"""
    project_id: str = Field(..., description="ID dự án")
    outline_ids: Optional[list[str]] = Field(None, description="Danh sách ID dàn ý cần mở rộng (trống thì mở rộng tất cả)")
    chapters_per_outline: int = Field(3, description="Số chương mục tiêu cho mỗi dàn ý", ge=1, le=10)
    expansion_strategy: str = Field("balanced", description="Chiến lược mở rộng")
    enable_scene_analysis: bool = Field(False, description="Có bao gồm kế hoạch cảnh hay không")
    auto_create_chapters: bool = Field(True, description="Có tự động tạo bản ghi chương hay không")
    provider: Optional[str] = Field(None, description="Nhà cung cấp AI")
    model: Optional[str] = Field(None, description="Model AI")


class BatchOutlineExpansionResponse(BaseModel):
    """Model response mở rộng dàn ý hàng loạt"""
    project_id: str = Field(..., description="ID dự án")
    total_outlines_expanded: int = Field(..., description="Tổng số dàn ý đã mở rộng")
    total_chapters_created: int = Field(..., description="Tổng số chương đã tạo")
    expansion_results: list[OutlineExpansionResponse] = Field(..., description="Danh sách kết quả mở rộng")
    skipped_outlines: Optional[list[dict]] = Field(None, description="Danh sách dàn ý bị bỏ qua (đã mở rộng)")


class CreateChaptersFromPlansRequest(BaseModel):
    """Model request tạo chương theo kế hoạch đã có"""
    chapter_plans: list[ChapterPlanItem] = Field(..., description="Danh sách kế hoạch chương (từ kết quả AI sinh trước đó)")


class CreateChaptersFromPlansResponse(BaseModel):
    """Model response tạo chương theo kế hoạch đã có"""
    outline_id: str = Field(..., description="ID dàn ý")
    outline_title: str = Field(..., description="Tiêu đề dàn ý")
    chapters_created: int = Field(..., description="Số chương đã tạo")
    created_chapters: list = Field(..., description="Danh sách chương đã tạo")
