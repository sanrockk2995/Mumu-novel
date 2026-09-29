"""Model Pydantic liên quan đến chương"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChapterBase(BaseModel):
    """Model cơ bản chương"""
    title: str = Field(..., description="Tiêu đề chương")
    chapter_number: int = Field(..., description="Số thứ tự chương")
    content: Optional[str] = Field(None, description="Nội dung chương")
    summary: Optional[str] = Field(None, description="Tóm tắt chương")
    word_count: Optional[int] = Field(0, description="Số từ")
    status: Optional[str] = Field("draft", description="Trạng thái chương")
    outline_id: Optional[str] = Field(None, description="ID dàn ý liên kết")
    sub_index: Optional[int] = Field(1, description="Số thứ tự chương con dưới dàn ý")
    expansion_plan: Optional[str] = Field(None, description="Chi tiết kế hoạch mở rộng (JSON)")


class ChapterCreate(BaseModel):
    """Model request tạo chương"""
    project_id: str = Field(..., description="ID dự án sở hữu")
    title: str = Field(..., description="Tiêu đề chương")
    chapter_number: int = Field(..., description="Số thứ tự chương")
    content: Optional[str] = Field(None, description="Nội dung chương")
    summary: Optional[str] = Field(None, description="Tóm tắt chương")
    status: Optional[str] = Field("draft", description="Trạng thái chương")
    outline_id: Optional[str] = Field(None, description="ID dàn ý liên kết")
    sub_index: Optional[int] = Field(1, description="Số thứ tự chương con dưới dàn ý")
    expansion_plan: Optional[str] = Field(None, description="Chi tiết kế hoạch mở rộng (JSON)")


class ChapterUpdate(BaseModel):
    """Model request cập nhật chương"""
    title: Optional[str] = None
    content: Optional[str] = None
    # Không cho phép sửa chapter_number, chỉ có thể điều chỉnh qua sắp xếp lại của dàn ý
    summary: Optional[str] = None
    # word_count tự động tính, không cho phép sửa thủ công
    status: Optional[str] = None


class ChapterResponse(BaseModel):
    """Model response chương"""
    id: str
    project_id: str
    title: str
    chapter_number: int
    content: Optional[str] = None
    summary: Optional[str] = None
    word_count: int = 0
    status: str
    outline_id: Optional[str] = None
    sub_index: Optional[int] = 1
    expansion_plan: Optional[str] = None
    outline_title: Optional[str] = None  # Tiêu đề dàn ý (join từ bảng Outline)
    outline_order: Optional[int] = None  # Số thứ tự dàn ý (join từ bảng Outline)
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ChapterListResponse(BaseModel):
    """Model response danh sách chương"""
    total: int
    items: list[ChapterResponse]


class AnalysisTaskStatusResponse(BaseModel):
    """Response trạng thái tác vụ phân tích chương đơn"""
    has_task: bool
    task_id: Optional[str] = None
    chapter_id: str
    status: str
    progress: int = 0
    error_message: Optional[str] = None
    auto_recovered: bool = False
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class BatchAnalysisStatusRequest(BaseModel):
    """Request truy vấn hàng loạt trạng thái phân tích"""
    chapter_ids: Optional[List[str]] = Field(None, description="Danh sách ID chương cần truy vấn; trống thì truy vấn toàn bộ chương của dự án")


class BatchAnalysisStatusResponse(BaseModel):
    """Response truy vấn hàng loạt trạng thái phân tích"""
    project_id: str
    total: int
    items: Dict[str, AnalysisTaskStatusResponse]


class BatchAnalyzeUnanalyzedRequest(BaseModel):
    """Request phân tích một lần các chương chưa phân tích"""
    chapter_ids: Optional[List[str]] = Field(None, description="Tùy chọn: giới hạn danh sách ID chương cần phân tích; trống thì tự nhận diện toàn bộ chương chưa phân tích trong dự án")


class BatchAnalyzeUnanalyzedResponse(BaseModel):
    """Response phân tích một lần các chương chưa phân tích"""
    project_id: str
    total_candidates: int = Field(0, description="Tổng số chương ứng viên (chương có nội dung)")
    total_started: int = Field(0, description="Số tác vụ phân tích đã khởi động lần này")
    total_skipped_no_content: int = Field(0, description="Bỏ qua: số chương không có nội dung")
    total_skipped_running: int = Field(0, description="Bỏ qua: số chương đang phân tích")
    total_already_completed: int = Field(0, description="Bỏ qua: số chương đã hoàn thành phân tích")
    started_tasks: Dict[str, AnalysisTaskStatusResponse] = Field(default_factory=dict, description="Map trạng thái tác vụ phân tích đã khởi động lần này")


class ChapterGenerateRequest(BaseModel):
    """Model request AI sinh nội dung chương"""
    style_id: Optional[int] = Field(None, description="ID phong cách viết, không cung cấp thì không dùng phong cách nào")
    target_word_count: Optional[int] = Field(
        3000,
        description="Số từ mục tiêu, mặc định 3000 từ",
        ge=500,   # Tối thiểu 500 từ
        le=10000  # Tối đa 10000 từ
    )
    enable_mcp: bool = Field(True, description="Có bật tăng cường công cụ MCP (tìm kiếm tài liệu tham khảo)")
    model: Optional[str] = Field(None, description="Chỉ định model AI sử dụng, không cung cấp thì dùng model mặc định của người dùng")
    narrative_perspective: Optional[str] = Field(None, description="Góc nhìn xưng tạm thời: first_person/third_person/omniscient, không cung cấp thì dùng mặc định của dự án")
    skill_key: Optional[str] = Field(None, description="Định danh Skill, khi chỉ định sẽ dùng workflow của Skill đó hướng dẫn sáng tác")


class BatchGenerateRequest(BaseModel):
    """Model request sinh chương hàng loạt"""
    start_chapter_number: int = Field(..., description="Số thứ tự chương bắt đầu")
    count: int = Field(..., description="Số lượng chương cần sinh", ge=1, le=20)
    style_id: Optional[int] = Field(None, description="ID phong cách viết")
    target_word_count: Optional[int] = Field(
        3000,
        description="Số từ mục tiêu, mặc định 3000 từ",
        ge=500,
        le=10000
    )
    enable_analysis: bool = Field(True, description="Có bật phân tích đồng bộ hay không")
    enable_mcp: bool = Field(True, description="Có bật tăng cường công cụ MCP (tìm kiếm tài liệu tham khảo)")
    max_retries: int = Field(3, description="Số lần thử lại tối đa cho mỗi chương", ge=0, le=5)
    model: Optional[str] = Field(None, description="Chỉ định model AI sử dụng, không cung cấp thì dùng model mặc định của người dùng")
    narrative_perspective: Optional[str] = Field(None, description="Chỉ định tạm thời ngôi trần thuật, không cung cấp thì dùng mặc định của dự án")
    skill_key: Optional[str] = Field(None, description="Định danh Skill, khi chỉ định sẽ dùng workflow của Skill đó hướng dẫn sáng tác")


class BatchGenerateResponse(BaseModel):
    """Model response sinh hàng loạt"""
    batch_id: str = Field(..., description="ID lô")
    message: str = Field(..., description="Thông báo response")
    chapters_to_generate: list[dict] = Field(..., description="Danh sách chương chờ sinh")
    estimated_time_minutes: int = Field(..., description="Thời gian ước tính (phút)")


class BatchGenerateStatusResponse(BaseModel):
    """Model response trạng thái sinh hàng loạt"""
    batch_id: str
    status: str
    total: int
    completed: int
    current_chapter_id: Optional[str] = None
    current_chapter_number: Optional[int] = None
    current_retry_count: Optional[int] = None
    max_retries: Optional[int] = None
    failed_chapters: list[dict] = []
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class SceneData(BaseModel):
    """Model dữ liệu cảnh"""
    location: str = Field(..., description="Địa điểm cảnh")
    characters: List[str] = Field(..., description="Danh sách nhân vật tham gia")
    purpose: str = Field(..., description="Mục đích cảnh")


class ExpansionPlanUpdate(BaseModel):
    """Model cập nhật kế hoạch chương"""
    summary: Optional[str] = Field(None, description="Tóm tắt tình tiết chương")
    key_events: Optional[List[str]] = Field(None, description="Danh sách sự kiện then chốt")
    character_focus: Optional[List[str]] = Field(None, description="Danh sách nhân vật liên quan")
    emotional_tone: Optional[str] = Field(None, description="Tông cảm xúc")
    narrative_goal: Optional[str] = Field(None, description="Mục tiêu trần thuật")
    conflict_type: Optional[str] = Field(None, description="Loại xung đột")
    estimated_words: Optional[int] = Field(None, description="Số từ dự kiến", ge=500, le=10000)
    scenes: Optional[List[SceneData]] = Field(None, description="Danh sách cảnh")
    
    model_config = ConfigDict(json_schema_extra={
            "example": {
                "key_events": ["Nhân vật chính gặp thử thách", "Khoảnh khắc quyết định then chốt"],
                "character_focus": ["Trương Tam", "Lý Tứ"],
                "emotional_tone": "Căng thẳng gay cấn",
                "narrative_goal": "Thúc đẩy cốt truyện chính",
                "conflict_type": "Xung đột nội tâm",
                "estimated_words": 3000,
                "scenes": [
                    {
                        "location": "Quảng trường thành phố",
                        "characters": ["Trương Tam", "Lý Tứ"],
                        "purpose": "Lần đầu gặp mặt"
                    }
                ]
            }
        })


class ExpansionPlanResponse(BaseModel):
    """Model response kế hoạch chương"""
    id: str = Field(..., description="ID chương")
    expansion_plan: Optional[Dict[str, Any]] = Field(None, description="Dữ liệu kế hoạch")
    message: str = Field(..., description="Thông báo response")


class PartialRegenerateRequest(BaseModel):
    """Tham số request viết lại cục bộ"""
    selected_text: str = Field(..., description="Nội dung văn bản gốc được chọn")
    start_position: int = Field(..., description="Vị trí bắt đầu trong nội dung chương (chỉ số ký tự)", ge=0)
    end_position: int = Field(..., description="Vị trí kết thúc trong nội dung chương (chỉ số ký tự)", ge=0)
    user_instructions: str = Field(..., description="Yêu cầu chỉnh sửa của người dùng", min_length=1, max_length=1000)
    
    # Tham số tùy chọn
    context_chars: int = Field(
        500,
        description="Độ dài cắt ngữ cảnh (mỗi đầu cắt bao nhiêu ký tự)",
        ge=100,
        le=2000
    )
    style_id: Optional[int] = Field(None, description="ID phong cách viết, không cung cấp thì dùng phong cách mặc định của dự án")
    length_mode: Optional[str] = Field(
        "similar",
        description="Chế độ điều chỉnh số từ: similar (giữ gần như cũ)/expand (mở rộng thích hợp)/condense (cô đọng)/custom (tùy chỉnh)"
    )
    target_word_count: Optional[int] = Field(
        None,
        description="Chỉ định số từ mục tiêu (chỉ hiệu lực khi length_mode là custom)",
        ge=10,
        le=5000
    )
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "selected_text": "Lâm Tiêu vung kiếm chém về phía kẻ địch, kiếm quang sắc bén, một chiêu chế địch.",
            "start_position": 1234,
            "end_position": 1260,
            "user_instructions": "Thêm miêu tả đánh nhau tinh tế hơn, thêm hoạt động tâm lý của nhân vật chính",
            "context_chars": 500,
            "length_mode": "expand"
        }
    })


class PartialRegenerateResponse(BaseModel):
    """Model response viết lại cục bộ"""
    success: bool = Field(..., description="Có thành công hay không")
    new_text: str = Field(..., description="Nội dung mới sau khi viết lại")
    word_count: int = Field(..., description="Số từ nội dung mới")
    original_word_count: int = Field(..., description="Số từ văn bản gốc")
    message: str = Field("Viết lại thành công", description="Thông báo response")
