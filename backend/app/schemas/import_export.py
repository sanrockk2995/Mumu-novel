"""Model Pydantic liên quan nhập/xuất"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ExportOptions(BaseModel):
    """Tùy chọn xuất"""
    include_generation_history: bool = Field(False, description="Có gồm lịch sử sinh không")
    include_writing_styles: bool = Field(True, description="Có gồm phong cách viết không")
    include_careers: bool = Field(True, description="Có gồm hệ thống nghề nghiệp không")
    include_memories: bool = Field(False, description="Có gồm ký ức truyện không (lượng dữ liệu có thể lớn)")
    include_plot_analysis: bool = Field(False, description="Có gồm phân tích cốt truyện không")


class ChapterExportData(BaseModel):
    """Dữ liệu xuất chương"""
    title: str
    content: Optional[str] = None
    summary: Optional[str] = None
    chapter_number: int
    word_count: int = 0
    status: str = "draft"
    created_at: Optional[str] = None
    
    # Trường mới của chức năng tinh chỉnh dàn ý
    outline_title: Optional[str] = None  # Tiêu đề dàn ý liên kết (dùng để tái tạo liên kết khi nhập)
    sub_index: Optional[int] = None  # Số thứ tự chương con dưới dàn ý
    expansion_plan: Optional[Dict[str, Any]] = None  # Chi tiết kế hoạch mở rộng (đối tượng JSON)


class CharacterExportData(BaseModel):
    """Dữ liệu xuất nhân vật"""
    name: str
    age: Optional[str] = None
    gender: Optional[str] = None
    is_organization: bool = False
    role_type: Optional[str] = None
    personality: Optional[str] = None
    background: Optional[str] = None
    appearance: Optional[str] = None
    relationships: Optional[str] = None
    traits: Optional[List[str]] = None
    organization_type: Optional[str] = None
    organization_purpose: Optional[str] = None
    organization_members: Optional[str] = None
    avatar_url: Optional[str] = None
    main_career_id: Optional[str] = None
    main_career_stage: Optional[int] = None
    sub_careers: Optional[str] = None
    # Trường riêng của tổ chức
    power_level: Optional[int] = None
    location: Optional[str] = None
    motto: Optional[str] = None
    color: Optional[str] = None
    created_at: Optional[str] = None


class OutlineExportData(BaseModel):
    """Dữ liệu xuất dàn ý"""
    title: str
    content: Optional[str] = None
    structure: Optional[str] = None
    order_index: Optional[int] = None
    created_at: Optional[str] = None


class RelationshipExportData(BaseModel):
    """Dữ liệu xuất quan hệ"""
    source_name: str
    target_name: str
    relationship_name: Optional[str] = None
    intimacy_level: int = 50
    status: str = "active"
    description: Optional[str] = None
    started_at: Optional[str] = None


class OrganizationExportData(BaseModel):
    """Dữ liệu xuất chi tiết tổ chức"""
    character_name: str
    parent_org_name: Optional[str] = None
    power_level: int = 50
    member_count: int = 0
    location: Optional[str] = None
    motto: Optional[str] = None
    color: Optional[str] = None


class OrganizationMemberExportData(BaseModel):
    """Dữ liệu xuất thành viên tổ chức"""
    organization_name: str
    character_name: str
    position: str
    rank: int = 0
    status: str = "active"
    joined_at: Optional[str] = None
    loyalty: int = 50
    contribution: int = 0
    notes: Optional[str] = None


class WritingStyleExportData(BaseModel):
    """Dữ liệu xuất phong cách viết"""
    name: str
    style_type: str
    preset_id: Optional[str] = None
    description: Optional[str] = None
    prompt_content: str
    order_index: int = 0


class GenerationHistoryExportData(BaseModel):
    """Dữ liệu xuất lịch sử sinh"""
    chapter_title: Optional[str] = None
    prompt: Optional[str] = None
    generated_content: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    generation_time: Optional[float] = None
    created_at: Optional[str] = None


class CareerExportData(BaseModel):
    """Dữ liệu xuất nghề nghiệp"""
    name: str
    type: str  # main/sub
    description: Optional[str] = None
    category: Optional[str] = None
    stages: str  # Danh sách giai đoạn định dạng JSON
    max_stage: int = 10
    requirements: Optional[str] = None
    special_abilities: Optional[str] = None
    worldview_rules: Optional[str] = None
    attribute_bonuses: Optional[str] = None
    source: str = "ai"
    created_at: Optional[str] = None


class CharacterCareerExportData(BaseModel):
    """Dữ liệu xuất liên kết nhân vật - nghề nghiệp"""
    character_name: str  # Liên kết qua tên
    career_name: str  # Liên kết qua tên
    career_type: str  # main/sub
    current_stage: int = 1
    stage_progress: int = 0
    started_at: Optional[str] = None
    reached_current_stage_at: Optional[str] = None
    notes: Optional[str] = None


class StoryMemoryExportData(BaseModel):
    """Dữ liệu xuất ký ức truyện"""
    chapter_title: Optional[str] = None  # Liên kết qua tiêu đề chương
    memory_type: str
    title: Optional[str] = None
    content: str
    full_context: Optional[str] = None
    related_characters: Optional[List[str]] = None  # Danh sách tên nhân vật
    related_locations: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    importance_score: float = 0.5
    story_timeline: int
    chapter_position: int = 0
    text_length: int = 0
    is_foreshadow: int = 0
    foreshadow_strength: Optional[float] = None
    created_at: Optional[str] = None


class PlotAnalysisExportData(BaseModel):
    """Dữ liệu xuất phân tích cốt truyện"""
    chapter_title: str  # Liên kết qua tiêu đề chương
    plot_stage: Optional[str] = None
    conflict_level: Optional[int] = None
    conflict_types: Optional[List[str]] = None
    emotional_tone: Optional[str] = None
    emotional_intensity: Optional[float] = None
    emotional_curve: Optional[Dict[str, float]] = None
    hooks: Optional[List[Dict[str, Any]]] = None
    hooks_count: int = 0
    hooks_avg_strength: Optional[float] = None
    foreshadows: Optional[List[Dict[str, Any]]] = None
    foreshadows_planted: int = 0
    foreshadows_resolved: int = 0
    plot_points: Optional[List[Dict[str, Any]]] = None
    plot_points_count: int = 0
    character_states: Optional[List[Dict[str, Any]]] = None
    scenes: Optional[List[Dict[str, Any]]] = None
    pacing: Optional[str] = None
    overall_quality_score: Optional[float] = None
    pacing_score: Optional[float] = None
    engagement_score: Optional[float] = None
    coherence_score: Optional[float] = None
    analysis_report: Optional[str] = None
    suggestions: Optional[List[str]] = None
    word_count: Optional[int] = None
    dialogue_ratio: Optional[float] = None
    description_ratio: Optional[float] = None
    created_at: Optional[str] = None


class ProjectDefaultStyleExportData(BaseModel):
    """Dữ liệu xuất phong cách mặc định dự án"""
    style_name: str  # Liên kết qua tên phong cách


class ProjectExportData(BaseModel):
    """Dữ liệu xuất đầy đủ dự án"""
    version: str = "1.1.0"  # Số phiên bản nâng cấp
    export_time: str
    project: Dict[str, Any]
    chapters: List[ChapterExportData] = []
    characters: List[CharacterExportData] = []
    outlines: List[OutlineExportData] = []
    relationships: List[RelationshipExportData] = []
    organizations: List[OrganizationExportData] = []
    organization_members: List[OrganizationMemberExportData] = []
    writing_styles: List[WritingStyleExportData] = []
    generation_history: List[GenerationHistoryExportData] = []
    # Trường mới
    careers: List[CareerExportData] = []
    character_careers: List[CharacterCareerExportData] = []
    story_memories: List[StoryMemoryExportData] = []
    plot_analysis: List[PlotAnalysisExportData] = []
    project_default_style: Optional[ProjectDefaultStyleExportData] = None


class ImportValidationResult(BaseModel):
    """Kết quả kiểm tra nhập"""
    valid: bool
    version: str
    project_name: Optional[str] = None
    statistics: Dict[str, int] = {}
    errors: List[str] = []
    warnings: List[str] = []


class ImportResult(BaseModel):
    """Kết quả nhập"""
    success: bool
    project_id: Optional[str] = None
    message: str
    statistics: Dict[str, int] = {}
    details: Optional[Dict[str, List[str]]] = None
    warnings: List[str] = []


class CharactersExportRequest(BaseModel):
    """Request xuất hàng loạt nhân vật/tổ chức"""
    character_ids: List[str] = Field(..., description="Danh sách ID nhân vật/tổ chức cần xuất")


class CharactersExportData(BaseModel):
    """Dữ liệu xuất hàng loạt nhân vật/tổ chức"""
    version: str = "1.0.0"
    export_time: str
    export_type: str = "characters"
    count: int
    data: List[CharacterExportData]


class CharactersImportResult(BaseModel):
    """Kết quả nhập nhân vật/tổ chức"""
    success: bool
    message: str
    statistics: Dict[str, int]
    details: Dict[str, List[str]]
    warnings: List[str] = []