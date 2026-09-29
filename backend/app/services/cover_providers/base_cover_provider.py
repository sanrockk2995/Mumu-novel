"""Lớp cơ sở trừu tượng cho Provider ảnh bìa"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TypedDict


class CoverGenerationResult(TypedDict):
    """Kết quả tạo ảnh bìa"""

    content: bytes
    mime_type: str
    file_extension: str
    revised_prompt: Optional[str]
    provider: str
    model: str


class BaseCoverProvider(ABC):
    """Lớp cơ sở trừu tượng cho Provider ảnh bìa"""

    @abstractmethod
    async def generate_cover(
        self,
        *,
        prompt: str,
        model: str,
        width: int,
        height: int,
    ) -> CoverGenerationResult:
        """Tạo ảnh bìa"""
        raise NotImplementedError
