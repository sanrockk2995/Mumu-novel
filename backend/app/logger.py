"""Module cấu hình log thống nhất - phong cách Uvicorn"""
import json
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Any, Optional


DEFAULT_LOG_MESSAGE_MAX_CHARS = 2000
DEFAULT_LOG_PREVIEW_MAX_CHARS = 300
SENSITIVE_LOG_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "bearer",
    "cookie",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
}


def _truncate_text(text: str, max_chars: Optional[int] = DEFAULT_LOG_PREVIEW_MAX_CHARS) -> str:
    """Cắt ngắn văn bản dài, giữ độ dài gốc để tiện tra soát."""
    if max_chars is None or max_chars <= 0 or len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}... [truncated, length={len(text)}]"


def safe_preview(value: Any, max_chars: int = DEFAULT_LOG_PREVIEW_MAX_CHARS) -> str:
    """Tạo bản xem trước an toàn, tránh văn bản dài đi thẳng vào log."""
    if value is None:
        return "None"
    return _truncate_text(str(value), max_chars)


def _sanitize_for_log(value: Any, depth: int = 0) -> Any:
    """Dọn đệ quy đối tượng log, tránh xuất trường nhạy cảm và toàn văn chính văn."""
    if depth > 4:
        return f"<{type(value).__name__}>"

    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            key_str = str(key)
            lower_key = key_str.lower()
            if any(sensitive_key in lower_key for sensitive_key in SENSITIVE_LOG_KEYS):
                sanitized[key_str] = "***REDACTED***"
            elif lower_key in {"content", "prompt", "system_prompt", "chapter_content", "messages", "arguments"}:
                sanitized[key_str] = summarize_log_value(item)
            else:
                sanitized[key_str] = _sanitize_for_log(item, depth + 1)
        return sanitized

    if isinstance(value, (list, tuple)):
        return [_sanitize_for_log(item, depth + 1) for item in value[:10]] + (
            [f"... {len(value) - 10} more items"] if len(value) > 10 else []
        )

    if isinstance(value, str):
        return safe_preview(value)

    return value


def safe_json_preview(value: Any, max_chars: int = 500) -> str:
    """Tạo bản xem trước JSON an toàn dễ đọc, không serialize được thì dùng bản xem trước chuỗi."""
    try:
        text = json.dumps(_sanitize_for_log(value), ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    return _truncate_text(text, max_chars)


def summarize_log_value(value: Any) -> str:
    """Trả về tóm tắt cấu trúc của giá trị, không xuất nội dung chính văn."""
    if value is None:
        return "None"
    if isinstance(value, str):
        return f"str(length={len(value)})"
    if isinstance(value, dict):
        fields = []
        for key, item in list(value.items())[:20]:
            if isinstance(item, str):
                fields.append(f"{key}:str(length={len(item)})")
            elif isinstance(item, (list, tuple, set)):
                fields.append(f"{key}:{type(item).__name__}(length={len(item)})")
            elif isinstance(item, dict):
                fields.append(f"{key}:dict(keys={len(item)})")
            else:
                fields.append(f"{key}:{type(item).__name__}")
        suffix = f", +{len(value) - 20} keys" if len(value) > 20 else ""
        return f"dict(keys={len(value)}, fields=[{', '.join(fields)}{suffix}])"
    if isinstance(value, (list, tuple, set)):
        item_types = sorted({type(item).__name__ for item in value})
        return f"{type(value).__name__}(length={len(value)}, item_types={item_types})"
    return type(value).__name__


class UvicornFormatter(logging.Formatter):
    """Bộ định dạng log phong cách Uvicorn"""
    
    # Màu cấp độ log (mã escape ANSI)
    COLORS = {
        'DEBUG': '\033[36m',      # Màu xanh lơ
        'INFO': '\033[32m',       # Màu xanh lá
        'WARNING': '\033[33m',    # Màu vàng
        'ERROR': '\033[31m',      # Màu đỏ
        'CRITICAL': '\033[35m',   # Màu tím
    }
    RESET = '\033[0m'
    
    def __init__(self, use_colors: bool = True, max_message_chars: int = DEFAULT_LOG_MESSAGE_MAX_CHARS):
        """
        Khởi tạo bộ định dạng
        
        Args:
            use_colors: có dùng màu không (console dùng, file không dùng)
        """
        super().__init__()
        self.use_colors = use_colors
        self.max_message_chars = max_message_chars
    
    def format(self, record):
        """Định dạng bản ghi log theo phong cách Uvicorn"""
        # Lấy tên cấp độ log
        levelname = record.levelname
        
        # Thêm màu (nếu bật và terminal hỗ trợ)
        if self.use_colors and sys.stderr.isatty():
            colored_level = f"{self.COLORS.get(levelname, '')}{levelname}{self.RESET}"
        else:
            colored_level = levelname
        
        # Thêm ID truy vết request (nếu có)
        request_id = getattr(record, 'request_id', None)
        request_id_str = f" [{request_id}]" if request_id else ""
        
        # Định dạng timestamp (YYYY-MM-DD HH:MM:SS)
        timestamp = self.formatTime(record, self.datefmt)
        
        message = _truncate_text(record.getMessage(), self.max_message_chars)
        # Định dạng phong cách Uvicorn: INFO:     [2024-01-01 12:00:00] module_name - message [request_id]
        # Chú ý: sau INFO có 5 dấu cách để căn chỉnh
        return f"{colored_level}:     [{timestamp}] {record.name}{request_id_str} - {message}"


# Cờ toàn cục, tránh khởi tạo lặp
_logging_configured = False

def setup_logging(
    level: str = "INFO",
    log_to_file: bool = False,
    log_file_path: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 30,
    message_max_chars: int = DEFAULT_LOG_MESSAGE_MAX_CHARS,
):
    """
    Cấu hình hệ thống log thống nhất phong cách Uvicorn
    
    Args:
        level: cấp độ log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: có xuất ra file không
        log_file_path: đường dẫn file log
        max_bytes: số byte tối đa mỗi file log (mặc định 10MB)
        backup_count: số file sao lưu giữ lại (mặc định 30)
        message_max_chars: số ký tự tối đa mỗi thông điệp log (mặc định 2000)
    """
    global _logging_configured
    
    # Nếu đã cấu hình rồi, trả về luôn
    if _logging_configured:
        return logging.getLogger()
    
    # Lấy root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Xóa handler đã có, tránh lặp
    root_logger.handlers.clear()
    
    if message_max_chars <= 0:
        message_max_chars = DEFAULT_LOG_MESSAGE_MAX_CHARS

    # 1. Tạo handler console (có màu)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(getattr(logging, level.upper()))
    console_formatter = UvicornFormatter(use_colors=True, max_message_chars=message_max_chars)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 2. Tạo handler file (nếu bật)
    if log_to_file and log_file_path:
        # Đảm bảo thư mục log tồn tại
        log_file = Path(log_file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Dùng RotatingFileHandler để xoay vòng log
        file_handler = RotatingFileHandler(
            filename=log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        
        # Log file không dùng màu
        file_formatter = UvicornFormatter(use_colors=False, max_message_chars=message_max_chars)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Ghi thông tin cấu hình log
        root_logger.info(f"Đã bật xuất log ra file: {log_file_path}")
        root_logger.info(f"Cấu hình xoay vòng log: mỗi file tối đa {max_bytes / 1024 / 1024:.1f}MB, giữ {backup_count} bản sao lưu")
        root_logger.info(f"Độ dài tối đa mỗi thông điệp log: {message_max_chars} ký tự")
    
    # Cấu hình cấp độ log của thư viện bên thứ ba
    _configure_third_party_loggers()
    
    # Đánh dấu đã cấu hình
    _logging_configured = True
    
    return root_logger


def _configure_third_party_loggers():
    """Cấu hình cấp độ log của thư viện bên thứ ba"""
    # SQLAlchemy - tắt log SQL
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)
    
    # aiosqlite - SQLite bất đồng bộ, tắt log DEBUG
    logging.getLogger('aiosqlite').setLevel(logging.WARNING)
    
    # Watchfiles - giám sát file khi dev, hạ cấp độ
    logging.getLogger('watchfiles').setLevel(logging.WARNING)
    
    # httpx/httpcore - HTTP client, tắt log DEBUG
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    
    # openai/anthropic - thư viện client AI
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('anthropic').setLevel(logging.WARNING)
    
    # Module ứng dụng - log thống kê AI cần giữ xuất cấp INFO
    logging.getLogger('app.services.ai_service').setLevel(logging.INFO)
    logging.getLogger('app.api.wizard').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Lấy logger theo tên chỉ định
    
    Args:
        name: tên logger, thường dùng __name__
        
    Returns:
        Thể hiện logger đã cấu hình
    """
    return logging.getLogger(name)
