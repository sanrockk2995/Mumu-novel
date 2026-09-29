"""Model Pydantic liên quan mẫu prompt"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class PromptTemplateBase(BaseModel):
    """Model cơ sở mẫu prompt"""
    template_key: str = Field(..., description="Tên key mẫu")
    template_name: str = Field(..., description="Tên hiển thị mẫu")
    template_content: str = Field(..., description="Nội dung mẫu")
    description: Optional[str] = Field(None, description="Mô tả mẫu")
    category: Optional[str] = Field(None, description="Phân loại mẫu")
    parameters: Optional[str] = Field(None, description="Định nghĩa tham số mẫu (JSON)")
    is_active: bool = Field(True, description="Có bật không")


class PromptTemplateCreate(PromptTemplateBase):
    """Model request tạo mẫu prompt"""
    pass


class PromptTemplateUpdate(BaseModel):
    """Model request cập nhật mẫu prompt"""
    template_name: Optional[str] = Field(None, description="Tên hiển thị mẫu")
    template_content: Optional[str] = Field(None, description="Nội dung mẫu")
    description: Optional[str] = Field(None, description="Mô tả mẫu")
    category: Optional[str] = Field(None, description="Phân loại mẫu")
    parameters: Optional[str] = Field(None, description="Định nghĩa tham số mẫu (JSON)")
    is_active: Optional[bool] = Field(None, description="Có bật không")


class PromptTemplateResponse(PromptTemplateBase):
    """Model response mẫu prompt"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    is_system_default: bool
    created_at: datetime
    updated_at: datetime


class PromptTemplateListResponse(BaseModel):
    """Response danh sách mẫu prompt"""
    templates: List[PromptTemplateResponse]
    total: int
    categories: List[str]


class PromptTemplateCategoryResponse(BaseModel):
    """Response phân loại mẫu prompt"""
    category: str
    count: int
    templates: List[PromptTemplateResponse]


class PromptTemplateExportItem(BaseModel):
    """Model hạng mục xuất mẫu prompt"""
    template_key: str = Field(..., description="Tên key mẫu")
    template_name: str = Field(..., description="Tên hiển thị mẫu")
    template_content: str = Field(..., description="Nội dung mẫu")
    description: Optional[str] = Field(None, description="Mô tả mẫu")
    category: Optional[str] = Field(None, description="Phân loại mẫu")
    parameters: Optional[str] = Field(None, description="Định nghĩa tham số mẫu (JSON)")
    is_active: bool = Field(True, description="Có bật không")
    is_customized: bool = Field(..., description="Có phải người dùng tùy chỉnh không (false=mặc định hệ thống, true=người dùng tùy chỉnh)")
    system_content_hash: Optional[str] = Field(None, description="Giá trị hash nội dung mặc định hệ thống, dùng để so sánh")


class PromptTemplateExport(BaseModel):
    """Model xuất mẫu prompt"""
    templates: List[PromptTemplateExportItem]
    export_time: datetime
    version: str = "2.0"
    statistics: Optional[dict] = Field(None, description="Thông tin thống kê xuất")


class PromptTemplateImportResult(BaseModel):
    """Kết quả nhập mẫu prompt"""
    message: str
    statistics: dict = Field(..., description="Thông tin thống kê nhập")
    converted_templates: List[dict] = Field(default_factory=list, description="Danh sách mẫu bị chuyển thành tùy chỉnh")


class PromptTemplatePreviewRequest(BaseModel):
    """Request xem trước mẫu prompt"""
    template_content: str = Field(..., description="Nội dung mẫu")
    parameters: dict = Field(..., description="Dict tham số")
