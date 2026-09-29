"""Công cụ thống kê gọi AI và định dạng log"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TokenUsage:
    """Thống kê lượng Token sử dụng"""

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    @classmethod
    def from_response(cls, response: Optional[Dict[str, Any]]) -> "TokenUsage":
        """Trích xuất thông tin usage từ response"""
        if not response:
            return cls()

        usage = response.get("usage") or {}
        prompt_tokens = cls._to_int(usage.get("prompt_tokens"))
        completion_tokens = cls._to_int(usage.get("completion_tokens"))
        total_tokens = cls._to_int(usage.get("total_tokens"))

        return cls(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def add(self, other: "TokenUsage") -> None:
        """Cộng dồn một usage khác"""
        self.prompt_tokens = self._sum_optional(self.prompt_tokens, other.prompt_tokens)
        self.completion_tokens = self._sum_optional(self.completion_tokens, other.completion_tokens)
        self.total_tokens = self._sum_optional(self.total_tokens, other.total_tokens)

    @staticmethod
    def _sum_optional(left: Optional[int], right: Optional[int]) -> Optional[int]:
        if left is None and right is None:
            return None
        return (left or 0) + (right or 0)


@dataclass
class ToolCallMetrics:
    """Thống kê gọi tool MCP"""

    tool_calls_count: int = 0
    mcp_rounds: int = 0
    tool_error_count: int = 0
    tool_names: List[str] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)

    def add_tool_name(self, tool_name: str) -> None:
        if tool_name and tool_name not in self.tool_names:
            self.tool_names.append(tool_name)


@dataclass
class AICallMetrics:
    """Thống kê một lần gọi AI"""

    request_mode: str
    provider: str
    model: str
    user_id: Optional[str] = None
    stream: bool = False
    auto_mcp: bool = False
    tools_count: int = 0
    prompt_length: int = 0
    response_length: int = 0
    chunk_count: int = 0
    retry_count: int = 0
    json_parse_success: Optional[bool] = None
    finish_reason: Optional[str] = None
    success: bool = False
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    ttft_ms: Optional[int] = None
    duration_ms: Optional[int] = None
    has_output: bool = False
    usage: TokenUsage = field(default_factory=TokenUsage)
    tool_metrics: ToolCallMetrics = field(default_factory=ToolCallMetrics)
    started_at: float = field(default_factory=time.perf_counter)
    first_chunk_at: Optional[float] = None

    def mark_first_chunk(self) -> None:
        if self.first_chunk_at is None:
            self.first_chunk_at = time.perf_counter()
            self.ttft_ms = int((self.first_chunk_at - self.started_at) * 1000)

    def finish(
        self,
        *,
        success: bool,
        response_length: Optional[int] = None,
        finish_reason: Optional[str] = None,
        usage: Optional[TokenUsage] = None,
        error: Optional[BaseException] = None,
    ) -> None:
        self.success = success
        self.duration_ms = int((time.perf_counter() - self.started_at) * 1000)
        if response_length is not None:
            self.response_length = response_length
        self.has_output = self.response_length > 0
        if finish_reason is not None:
            self.finish_reason = finish_reason
        if usage is not None:
            self.usage = usage
        if error is not None:
            self.error_type = type(error).__name__
            self.error_message = self._truncate(str(error), 180)

    def merge_tool_metrics(self, tool_metrics: ToolCallMetrics) -> None:
        self.tool_metrics = tool_metrics
        self.usage.add(tool_metrics.usage)

    def to_log_message(self, title: str) -> str:
        fields = [
            ("Loại request", self.request_mode),
            ("Nhà cung cấp", self.provider),
            ("Model", self.model),
            ("Trạng thái", "Thành công" if self.success else "Thất bại"),
            ("TTFB", self._format_latency(self.ttft_ms, allow_empty=True)),
            ("Tổng thời gian", self._format_latency(self.duration_ms, allow_empty=False)),
            ("Số ký tự input", str(self.prompt_length)),
            ("Số ký tự output", str(self.response_length)),
            ("Token input", self._format_optional_number(self.usage.prompt_tokens)),
            ("Token output", self._format_optional_number(self.usage.completion_tokens)),
            ("Tổng Token", self._format_optional_number(self.usage.total_tokens)),
            ("Số block streaming", str(self.chunk_count) if self.stream else "Không áp dụng"),
            ("Bật MCP", "Có" if self.auto_mcp else "Không"),
            ("Số tool", str(self.tools_count)),
            ("Số lần gọi tool", str(self.tool_metrics.tool_calls_count)),
            ("Số vòng MCP", str(self.tool_metrics.mcp_rounds)),
            ("Số lần retry", str(self.retry_count) if self.retry_count else "0"),
            ("Parse JSON", self._format_json_parse_result()),
            ("Lý do kết thúc", self.finish_reason or "Không rõ"),
        ]

        if self.user_id:
            fields.append(("ID người dùng", self.user_id))
        if self.tool_metrics.tool_names:
            fields.append(("Tên tool", ",".join(self.tool_metrics.tool_names)))
        if self.error_type:
            fields.append(("Loại ngoại lệ", self.error_type))
        if self.error_message:
            fields.append(("Tóm tắt ngoại lệ", self.error_message))

        formatted = "｜".join(f"{key}={value}" for key, value in fields)
        return f"{title}｜{formatted}"

    def _format_json_parse_result(self) -> str:
        if self.json_parse_success is None:
            return "Không áp dụng"
        return "Thành công" if self.json_parse_success else "Thất bại"

    @staticmethod
    def _format_optional_number(value: Optional[int]) -> str:
        return str(value) if value is not None else "Không rõ"

    @staticmethod
    def _format_latency(value: Optional[int], allow_empty: bool) -> str:
        if value is None:
            return "Không có" if allow_empty else "Không rõ"
        if value < 1000:
            return f"{value}ms"
        return f"{value / 1000:.2f}s"

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return f"{text[:limit]}..."
