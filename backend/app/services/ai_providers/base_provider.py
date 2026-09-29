"""Lớp cơ sở của AI Provider"""
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional


class BaseAIProvider(ABC):
    """Lớp cơ sở trừu tượng cho nhà cung cấp AI"""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sinh văn bản"""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Sinh streaming"""
        pass