"""Model Pydantic liên quan đến quản lý quan hệ"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


# ============ Loại quan hệ ============

class RelationshipTypeResponse(BaseModel):
    """Model response loại quan hệ"""
    id: int
    name: str
    category: str
    reverse_name: Optional[str] = None
    intimacy_range: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============ Quan hệ nhân vật ============

class CharacterRelationshipBase(BaseModel):
    """Model cơ bản quan hệ nhân vật"""
    relationship_type_id: Optional[int] = Field(None, description="ID loại quan hệ")
    relationship_name: Optional[str] = Field(None, description="Tên quan hệ tùy chỉnh")
    intimacy_level: int = Field(50, ge=-100, le=100, description="Mức thân mật: -100 đến 100")
    status: str = Field("active", description="Trạng thái: active/broken/past/complicated")
    description: Optional[str] = Field(None, description="Mô tả quan hệ")
    started_at: Optional[str] = Field(None, description="Thời gian bắt đầu quan hệ (thời gian trong truyện)")
    ended_at: Optional[str] = Field(None, description="Thời gian kết thúc quan hệ")


class CharacterRelationshipCreate(CharacterRelationshipBase):
    """Model request tạo quan hệ nhân vật"""
    project_id: str = Field(..., description="ID dự án")
    character_from_id: str = Field(..., description="ID nhân vật A")
    character_to_id: str = Field(..., description="ID nhân vật B")


class CharacterRelationshipUpdate(BaseModel):
    """Model request cập nhật quan hệ nhân vật"""
    relationship_type_id: Optional[int] = None
    relationship_name: Optional[str] = None
    intimacy_level: Optional[int] = Field(None, ge=-100, le=100)
    status: Optional[str] = None
    description: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class CharacterRelationshipResponse(CharacterRelationshipBase):
    """Model response quan hệ nhân vật"""
    id: str
    project_id: str
    character_from_id: str
    character_to_id: str
    source: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class RelationshipGraphNode(BaseModel):
    """Nút đồ thị quan hệ"""
    id: str
    name: str
    type: str  # character / organization
    role_type: Optional[str] = None
    avatar: Optional[str] = None


class RelationshipGraphLink(BaseModel):
    """Đường nối đồ thị quan hệ"""
    source: str
    target: str
    relationship: str
    intimacy: int
    status: str


class RelationshipGraphData(BaseModel):
    """Dữ liệu đồ thị quan hệ"""
    nodes: List[RelationshipGraphNode]
    links: List[RelationshipGraphLink]


# ============ Tổ chức ============

class OrganizationBase(BaseModel):
    """Model cơ bản tổ chức"""
    parent_org_id: Optional[str] = Field(None, description="ID tổ chức cha")
    level: int = Field(0, description="Cấp tổ chức")
    power_level: int = Field(50, ge=0, le=100, description="Cấp độ thế lực")
    location: Optional[str] = Field(None, description="Nơi đặt")
    motto: Optional[str] = Field(None, description="Tôn chỉ tổ chức")
    color: Optional[str] = Field(None, description="Màu đại diện")


class OrganizationCreate(OrganizationBase):
    """Model request tạo tổ chức"""
    character_id: str = Field(..., description="ID nhân vật liên kết (bản ghi tổ chức)")
    project_id: str = Field(..., description="ID dự án")


class OrganizationUpdate(BaseModel):
    """Model request cập nhật tổ chức"""
    parent_org_id: Optional[str] = None
    level: Optional[int] = None
    power_level: Optional[int] = Field(None, ge=0, le=100)
    location: Optional[str] = None
    motto: Optional[str] = None
    color: Optional[str] = None


class OrganizationResponse(OrganizationBase):
    """Model response tổ chức"""
    id: str
    character_id: str
    project_id: str
    member_count: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class OrganizationDetailResponse(BaseModel):
    """Response chi tiết tổ chức (gồm thông tin cơ bản)"""
    id: str
    character_id: str
    name: str
    type: Optional[str] = None
    purpose: Optional[str] = None
    member_count: int
    power_level: int
    location: Optional[str] = None
    motto: Optional[str] = None
    color: Optional[str] = None


# ============ Thành viên tổ chức ============

class OrganizationMemberBase(BaseModel):
    """Model cơ bản thành viên tổ chức"""
    position: str = Field(..., description="Tên chức vụ")
    rank: int = Field(0, description="Cấp chức vụ")
    status: str = Field("active", description="Trạng thái: active/retired/expelled/deceased")
    joined_at: Optional[str] = Field(None, description="Thời gian gia nhập (thời gian trong truyện)")
    left_at: Optional[str] = Field(None, description="Thời gian rời đi")
    loyalty: int = Field(50, ge=0, le=100, description="Mức trung thành")
    contribution: int = Field(0, ge=0, le=100, description="Mức đóng góp")
    notes: Optional[str] = Field(None, description="Ghi chú")


class OrganizationMemberCreate(OrganizationMemberBase):
    """Model request tạo thành viên tổ chức"""
    character_id: str = Field(..., description="ID nhân vật")


class OrganizationMemberUpdate(BaseModel):
    """Model request cập nhật thành viên tổ chức"""
    position: Optional[str] = None
    rank: Optional[int] = None
    status: Optional[str] = None
    joined_at: Optional[str] = None
    left_at: Optional[str] = None
    loyalty: Optional[int] = Field(None, ge=0, le=100)
    contribution: Optional[int] = Field(None, ge=0, le=100)
    notes: Optional[str] = None


class OrganizationMemberResponse(OrganizationMemberBase):
    """Model response thành viên tổ chức"""
    id: str
    organization_id: str
    character_id: str
    source: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class OrganizationMemberDetailResponse(BaseModel):
    """Response chi tiết thành viên tổ chức (gồm thông tin nhân vật)"""
    id: str
    character_id: str
    character_name: str
    position: str
    rank: int
    loyalty: int
    contribution: int
    status: str
    joined_at: Optional[str] = None
    left_at: Optional[str] = None
    notes: Optional[str] = None