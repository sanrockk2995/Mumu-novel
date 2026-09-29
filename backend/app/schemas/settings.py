"""Model Pydantic liên quan đến cài đặt"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class SettingsBase(BaseModel):
    """Model cơ bản cài đặt"""
    model_config = ConfigDict(protected_namespaces=())
    
    api_provider: Optional[str] = Field(default="openai", description="Nhà cung cấp API")
    api_key: Optional[str] = Field(default=None, description="Khóa API")
    api_base_url: Optional[str] = Field(default=None, description="Địa chỉ API tùy chỉnh")
    llm_model: Optional[str] = Field(default="gpt-4", description="Tên model")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="Tham số temperature")
    max_tokens: Optional[int] = Field(default=2000, ge=1, description="Số token tối đa")
    system_prompt: Optional[str] = Field(default=None, description="Prompt cấp hệ thống, dùng cho mọi lần gọi AI")
    disable_thinking: Optional[bool] = Field(default=False, description="Tắt suy luận của model: model suy luận bỏ qua giai đoạn suy nghĩ và xuất trực tiếp nội dung, giảm tiêu thụ token và thời gian chờ")
    cover_api_provider: Optional[str] = Field(default=None, description="Nhà cung cấp API ảnh bìa")
    cover_api_key: Optional[str] = Field(default=None, description="Khóa API ảnh bìa")
    cover_api_base_url: Optional[str] = Field(default=None, description="Địa chỉ API tùy chỉnh ảnh bìa")
    cover_image_model: Optional[str] = Field(default=None, description="Tên model ảnh bìa")
    cover_enabled: Optional[bool] = Field(default=False, description="Có bật sinh ảnh bìa hay không")
    preferences: Optional[str] = Field(default=None, description="Cài đặt tùy chọn khác (JSON)")


class SettingsCreate(SettingsBase):
    """Model request tạo cài đặt"""
    pass


class SettingsUpdate(SettingsBase):
    """Model request cập nhật cài đặt"""
    pass


class SettingsResponse(SettingsBase):
    """Model response cài đặt"""
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class SystemSMTPSettingsBase(BaseModel):
    """Model cơ bản cài đặt SMTP hệ thống"""
    model_config = ConfigDict(protected_namespaces=())

    smtp_provider: str = Field(default="qq", description="Nhà cung cấp SMTP")
    smtp_host: Optional[str] = Field(default=None, description="Host SMTP")
    smtp_port: int = Field(default=465, ge=1, le=65535, description="Cổng SMTP")
    smtp_username: Optional[str] = Field(default=None, description="Tên đăng nhập SMTP")
    smtp_password: Optional[str] = Field(default=None, description="Mật khẩu SMTP hoặc mã ủy quyền")
    smtp_use_tls: bool = Field(default=False, description="Có bật TLS hay không")
    smtp_use_ssl: bool = Field(default=True, description="Có bật SSL hay không")
    smtp_from_email: Optional[str] = Field(default=None, description="Email người gửi")
    smtp_from_name: str = Field(default="MuMuAINovel", description="Tên người gửi")
    email_auth_enabled: bool = Field(default=True, description="Có bật xác thực email hay không")
    email_register_enabled: bool = Field(default=True, description="Có bật đăng ký bằng email hay không")
    verification_code_ttl_minutes: int = Field(default=10, ge=1, le=120, description="Thời hạn hiệu lực mã xác minh (phút)")
    verification_resend_interval_seconds: int = Field(default=60, ge=10, le=3600, description="Khoảng cách gửi lại mã xác minh (giây)")


class SystemSMTPSettingsUpdate(SystemSMTPSettingsBase):
    """Model cập nhật cài đặt SMTP hệ thống"""
    pass


class SystemSMTPSettingsResponse(SystemSMTPSettingsBase):
    """Model response cài đặt SMTP hệ thống"""
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class SMTPTestRequest(BaseModel):
    """Model request kiểm tra SMTP"""
    model_config = ConfigDict(protected_namespaces=())

    to_email: str = Field(..., min_length=3, max_length=255, description="Email nhận kiểm tra")


# ========== Model liên quan đến preset cấu hình API ==========

class APIKeyPresetConfig(BaseModel):
    """Nội dung cấu hình preset"""
    model_config = ConfigDict(protected_namespaces=())
    
    api_provider: str = Field(..., description="Nhà cung cấp API")
    api_key: str = Field(..., description="Khóa API")
    api_base_url: Optional[str] = Field(None, description="Địa chỉ API tùy chỉnh")
    llm_model: str = Field(..., description="Tên model")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Tham số temperature")
    max_tokens: int = Field(default=2000, ge=1, description="Số token tối đa")
    system_prompt: Optional[str] = Field(default=None, description="Prompt cấp hệ thống")


class APIKeyPreset(BaseModel):
    """Preset cấu hình API"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: str = Field(..., description="ID preset")
    name: str = Field(..., min_length=1, max_length=50, description="Tên preset")
    description: Optional[str] = Field(None, max_length=200, description="Mô tả preset")
    is_active: bool = Field(default=False, description="Có kích hoạt hay không")
    created_at: datetime = Field(..., description="Thời gian tạo")
    config: APIKeyPresetConfig = Field(..., description="Nội dung cấu hình")


class PresetCreateRequest(BaseModel):
    """Request tạo preset"""
    model_config = ConfigDict(protected_namespaces=())
    
    name: str = Field(..., min_length=1, max_length=50, description="Tên preset")
    description: Optional[str] = Field(None, max_length=200, description="Mô tả preset")
    config: APIKeyPresetConfig = Field(..., description="Nội dung cấu hình")


class PresetUpdateRequest(BaseModel):
    """Request cập nhật preset"""
    model_config = ConfigDict(protected_namespaces=())
    
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="Tên preset")
    description: Optional[str] = Field(None, max_length=200, description="Mô tả preset")
    config: Optional[APIKeyPresetConfig] = Field(None, description="Nội dung cấu hình")


class PresetResponse(APIKeyPreset):
    """Response preset"""
    pass


class PresetListResponse(BaseModel):
    """Response danh sách preset"""
    model_config = ConfigDict(protected_namespaces=())
    
    presets: List[PresetResponse] = Field(..., description="Danh sách preset")
    total: int = Field(..., description="Tổng số")
    active_preset_id: Optional[str] = Field(None, description="ID preset đang kích hoạt")
    chapter_analysis_preset_id: Optional[str] = Field(None, description="ID preset dùng cho phân tích nội dung chương, trống thì dùng cấu hình API mặc định")


class ChapterAnalysisPresetSelectionRequest(BaseModel):
    """Request chọn preset phân tích nội dung chương"""
    model_config = ConfigDict(protected_namespaces=())

    preset_id: Optional[str] = Field(None, description="ID preset dùng cho phân tích nội dung chương; trống thì dùng cấu hình API mặc định")