"""Model Pydantic liên quan nghề nghiệp"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class CareerStage(BaseModel):
    """Model giai đoạn nghề nghiệp"""
    level: int = Field(..., description="Cấp giai đoạn")
    name: str = Field(..., description="Tên giai đoạn")
    description: Optional[str] = Field(None, description="Mô tả giai đoạn")


class CareerBase(BaseModel):
    """Model cơ sở nghề nghiệp"""
    name: str = Field(..., description="Tên nghề nghiệp")
    type: str = Field(..., description="Loại nghề nghiệp: main(nghề chính)/sub(nghề phụ)")
    description: Optional[str] = Field(None, description="Mô tả nghề nghiệp")
    category: Optional[str] = Field(None, description="Phân loại nghề nghiệp")
    stages: List[CareerStage] = Field(..., description="Danh sách giai đoạn nghề nghiệp")
    max_stage: int = Field(10, description="Số giai đoạn tối đa")
    requirements: Optional[str] = Field(None, description="Yêu cầu/hạn chế nghề nghiệp")
    special_abilities: Optional[str] = Field(None, description="Mô tả năng lực đặc biệt")
    worldview_rules: Optional[str] = Field(None, description="Liên kết quy tắc thế giới quan")
    attribute_bonuses: Optional[Dict[str, str]] = Field(None, description="Cộng thuộc tính")


class CareerCreate(CareerBase):
    """Model request tạo nghề nghiệp"""
    project_id: str = Field(..., description="ID dự án")
    source: str = Field("manual", description="Nguồn: ai/manual")


class CareerUpdate(BaseModel):
    """Model request cập nhật nghề nghiệp"""
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    stages: Optional[List[CareerStage]] = None
    max_stage: Optional[int] = None
    requirements: Optional[str] = None
    special_abilities: Optional[str] = None
    worldview_rules: Optional[str] = None
    attribute_bonuses: Optional[Dict[str, str]] = None


class CareerResponse(BaseModel):
    """Model response nghề nghiệp"""
    id: str
    project_id: str
    name: str
    type: str
    description: Optional[str] = None
    category: Optional[str] = None
    stages: List[CareerStage]
    max_stage: int
    requirements: Optional[str] = None
    special_abilities: Optional[str] = None
    worldview_rules: Optional[str] = None
    attribute_bonuses: Optional[Dict[str, str]] = None
    source: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class CareerListResponse(BaseModel):
    """Model response danh sách nghề nghiệp"""
    total: int
    main_careers: List[CareerResponse] = Field(default_factory=list, description="Danh sách nghề chính")
    sub_careers: List[CareerResponse] = Field(default_factory=list, description="Danh sách nghề phụ")


class CareerGenerateRequest(BaseModel):
    """Model request AI sinh hệ thống nghề nghiệp"""
    project_id: str = Field(..., description="ID dự án")
    main_career_count: int = Field(5, description="Số lượng nghề chính", ge=1, le=20)
    sub_career_count: int = Field(8, description="Số lượng nghề phụ", ge=0, le=30)
    user_requirements: str = Field("", description="Yêu cầu bổ sung của người dùng")
    enable_mcp: bool = Field(False, description="Có bật tăng cường công cụ MCP không")


# ===== Liên quan liên kết nhân vật - nghề nghiệp =====

class CharacterCareerBase(BaseModel):
    """Model cơ sở liên kết nhân vật - nghề nghiệp"""
    career_id: str = Field(..., description="ID nghề nghiệp")
    career_type: str = Field(..., description="main(nghề chính)/sub(nghề phụ)")
    current_stage: int = Field(1, description="Giai đoạn hiện tại", ge=1)
    stage_progress: int = Field(0, description="Tiến độ trong giai đoạn (0-100)", ge=0, le=100)
    started_at: Optional[str] = Field(None, description="Thời gian bắt đầu tu luyện")
    reached_current_stage_at: Optional[str] = Field(None, description="Thời gian đến giai đoạn hiện tại")
    notes: Optional[str] = Field(None, description="Ghi chú")


class CharacterCareerCreate(CharacterCareerBase):
    """Model request tạo liên kết nhân vật - nghề nghiệp"""
    character_id: str = Field(..., description="ID nhân vật")


class CharacterCareerUpdate(BaseModel):
    """Model request cập nhật liên kết nhân vật - nghề nghiệp"""
    current_stage: Optional[int] = Field(None, ge=1)
    stage_progress: Optional[int] = Field(None, ge=0, le=100)
    reached_current_stage_at: Optional[str] = None
    notes: Optional[str] = None


class CharacterCareerDetail(BaseModel):
    """Model chi tiết nghề nghiệp nhân vật (gồm thông tin nghề nghiệp)"""
    id: str
    character_id: str
    career_id: str
    career_name: str = Field(..., description="Tên nghề nghiệp")
    career_type: str
    current_stage: int
    stage_name: str = Field(..., description="Tên giai đoạn hiện tại")
    stage_description: Optional[str] = Field(None, description="Mô tả giai đoạn hiện tại")
    stage_progress: int
    max_stage: int = Field(..., description="Giai đoạn tối đa của nghề này")
    started_at: Optional[str] = None
    reached_current_stage_at: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CharacterCareerResponse(BaseModel):
    """Model response nghề nghiệp nhân vật"""
    main_career: Optional[CharacterCareerDetail] = Field(None, description="Nghề chính")
    sub_careers: List[CharacterCareerDetail] = Field(default_factory=list, description="Danh sách nghề phụ")


class SetMainCareerRequest(BaseModel):
    """Model request đặt nghề chính"""
    career_id: str = Field(..., description="ID nghề nghiệp")
    current_stage: int = Field(1, description="Giai đoạn hiện tại", ge=1)
    started_at: Optional[str] = Field(None, description="Thời gian bắt đầu tu luyện")


class AddSubCareerRequest(BaseModel):
    """Model request thêm nghề phụ"""
    career_id: str = Field(..., description="ID nghề nghiệp")
    current_stage: int = Field(1, description="Giai đoạn hiện tại", ge=1)
    started_at: Optional[str] = Field(None, description="Thời gian bắt đầu tu luyện")


class UpdateCareerStageRequest(BaseModel):
    """Model request cập nhật giai đoạn nghề nghiệp"""
    current_stage: int = Field(..., description="Giai đoạn mới", ge=1)
    stage_progress: int = Field(0, description="Tiến độ giai đoạn", ge=0, le=100)
    reached_current_stage_at: Optional[str] = Field(None, description="Thời gian đến")
    notes: Optional[str] = Field(None, description="Ghi chú")