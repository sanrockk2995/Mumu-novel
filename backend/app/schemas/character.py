"""Model Pydantic liên quan nhân vật"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class CharacterBase(BaseModel):
    """Model cơ sở nhân vật"""
    name: str = Field(..., description="Tên nhân vật/tổ chức")
    age: Optional[str] = Field(None, description="Tuổi")
    gender: Optional[str] = Field(None, description="Giới tính")
    is_organization: bool = Field(False, description="Có phải tổ chức không")
    role_type: Optional[str] = Field(None, description="Loại nhân vật: protagonist/supporting/antagonist")
    personality: Optional[str] = Field(None, description="Đặc điểm tính cách/đặc tính tổ chức")
    background: Optional[str] = Field(None, description="Câu chuyện nền")
    appearance: Optional[str] = Field(None, description="Đặc điểm ngoại hình")
    relationships: Optional[str] = Field(None, description="Quan hệ giữa người với người (JSON)")
    organization_type: Optional[str] = Field(None, description="Loại tổ chức")
    organization_purpose: Optional[str] = Field(None, description="Mục đích tổ chức")
    organization_members: Optional[str] = Field(None, description="Thành viên tổ chức (JSON)")
    traits: Optional[str] = Field(None, description="Nhãn đặc trưng (JSON)")


class CharacterCreate(BaseModel):
    """Model request tạo thủ công nhân vật"""
    project_id: str = Field(..., description="ID dự án")
    name: str = Field(..., description="Tên nhân vật/tổ chức")
    age: Optional[str] = Field(None, description="Tuổi")
    gender: Optional[str] = Field(None, description="Giới tính")
    is_organization: bool = Field(False, description="Có phải tổ chức không")
    role_type: Optional[str] = Field("supporting", description="Loại nhân vật: protagonist/supporting/antagonist")
    personality: Optional[str] = Field(None, description="Đặc điểm tính cách/đặc tính tổ chức")
    background: Optional[str] = Field(None, description="Câu chuyện nền")
    appearance: Optional[str] = Field(None, description="Đặc điểm ngoại hình")
    organization_type: Optional[str] = Field(None, description="Loại tổ chức")
    organization_purpose: Optional[str] = Field(None, description="Mục đích tổ chức")
    organization_members: Optional[str] = Field(None, description="Thành viên tổ chức (JSON)")
    traits: Optional[str] = Field(None, description="Nhãn đặc trưng (JSON)")
    avatar_url: Optional[str] = Field(None, description="URL ảnh đại diện")
    
    # Trường bổ sung của tổ chức
    power_level: Optional[int] = Field(None, description="Cấp độ thế lực tổ chức (0-100)")
    location: Optional[str] = Field(None, description="Nơi đặt tổ chức")
    motto: Optional[str] = Field(None, description="Châm ngôn/khẩu hiệu tổ chức")
    color: Optional[str] = Field(None, description="Màu đại diện tổ chức")
    
    # Trường nghề nghiệp
    main_career_id: Optional[str] = Field(None, description="ID nghề chính")
    main_career_stage: Optional[int] = Field(None, description="Giai đoạn nghề chính")
    sub_careers: Optional[str] = Field(None, description="Chuỗi JSON danh sách nghề phụ")


class CharacterUpdate(BaseModel):
    """Model request cập nhật nhân vật"""
    name: Optional[str] = None
    age: Optional[str] = None
    gender: Optional[str] = None
    is_organization: Optional[bool] = None
    role_type: Optional[str] = None
    personality: Optional[str] = None
    background: Optional[str] = None
    appearance: Optional[str] = None
    organization_type: Optional[str] = None
    organization_purpose: Optional[str] = None
    organization_members: Optional[str] = None
    traits: Optional[str] = None
    
    # Trường bổ sung của tổ chức (sẽ đồng bộ sang bảng Organization)
    power_level: Optional[int] = Field(None, description="Cấp độ thế lực tổ chức (0-100)")
    location: Optional[str] = Field(None, description="Nơi đặt tổ chức")
    motto: Optional[str] = Field(None, description="Châm ngôn/khẩu hiệu tổ chức")
    color: Optional[str] = Field(None, description="Màu đại diện tổ chức")
    
    # Trường nghề nghiệp (sẽ đồng bộ sang bảng CharacterCareer)
    main_career_id: Optional[str] = Field(None, description="ID nghề chính")
    main_career_stage: Optional[int] = Field(None, description="Giai đoạn nghề chính")
    sub_careers: Optional[str] = Field(None, description="Chuỗi JSON danh sách nghề phụ")


class CharacterResponse(CharacterBase):
    """Model response nhân vật"""
    id: str
    project_id: str
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Trường bổ sung của tổ chức (liên kết từ bảng Organization)
    power_level: Optional[int] = Field(None, description="Cấp độ thế lực tổ chức (0-100)")
    location: Optional[str] = Field(None, description="Nơi đặt tổ chức")
    motto: Optional[str] = Field(None, description="Châm ngôn/khẩu hiệu tổ chức")
    color: Optional[str] = Field(None, description="Màu đại diện tổ chức")
    
    # Trường thông tin nghề nghiệp
    main_career_id: Optional[str] = Field(None, description="ID nghề chính")
    main_career_stage: Optional[int] = Field(None, description="Giai đoạn nghề chính")
    sub_careers: Optional[List[Dict[str, Any]]] = Field(None, description="Danh sách nghề phụ")
    
    # Trạng thái sống của nhân vật/tổ chức
    status: Optional[str] = Field("active", description="Trạng thái: active/deceased/missing/retired/destroyed")
    status_changed_chapter: Optional[int] = Field(None, description="Số chương thay đổi trạng thái")
    
    # Trường theo dõi trạng thái tâm lý
    current_state: Optional[str] = Field(None, description="Trạng thái tâm lý hiện tại của nhân vật")
    state_updated_chapter: Optional[int] = Field(None, description="Số chương cập nhật trạng thái tâm lý lần cuối")
    
    model_config = ConfigDict(from_attributes=True)


class CharacterGenerateRequest(BaseModel):
    """Model request AI sinh nhân vật"""
    project_id: str = Field(..., description="ID dự án")
    name: Optional[str] = Field(None, description="Tên nhân vật")
    role_type: Optional[str] = Field(None, description="Loại nhân vật")
    background: Optional[str] = Field(None, description="Nền nhân vật")
    requirements: Optional[str] = Field(None, description="Yêu cầu đặc biệt")
    enable_mcp: bool = Field(True, description="Có bật tăng cường công cụ MCP không (tìm tham khảo nguyên mẫu nhân vật)")


class CharacterListResponse(BaseModel):
    """Model response danh sách nhân vật"""
    total: int
    items: List[CharacterResponse]