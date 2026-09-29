"""Model Pydantic liên quan đến khử "mùi AI" """
from pydantic import BaseModel, Field
from typing import Optional


class PolishRequest(BaseModel):
    """Model request khử mùi AI"""
    original_text: str = Field(..., description="Văn bản gốc (văn bản do AI sinh)")
    project_id: Optional[int] = Field(None, description="ID dự án (tùy chọn, dùng để ghi lịch sử)")
    provider: Optional[str] = Field(None, description="Nhà cung cấp AI")
    model: Optional[str] = Field(None, description="Model AI")
    temperature: Optional[float] = Field(0.8, description="Tham số temperature, khuyến nghị 0.7-0.9")


class PolishResponse(BaseModel):
    """Model response khử mùi AI"""
    original_text: str = Field(..., description="Văn bản gốc")
    polished_text: str = Field(..., description="Văn bản sau khi khử mùi")
    word_count_before: int = Field(..., description="Số từ trước xử lý")
    word_count_after: int = Field(..., description="Số từ sau xử lý")