"""Hằng số cấu hình module MCP"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MCPConfig:
    """Hằng số cấu hình module MCP (bất biến)"""
    
    # Cấu hình connection pool
    MAX_CLIENTS: int = 1000  # Số lượng client tối đa
    CLIENT_TTL_SECONDS: int = 3600  # Thời gian hết hạn client (1 giờ)
    IDLE_TIMEOUT_SECONDS: int = 1800  # Timeout nhàn rỗi (30 phút)
    
    # Cấu hình kiểm tra sức khỏe
    HEALTH_CHECK_INTERVAL_SECONDS: int = 60  # Khoảng cách kiểm tra sức khỏe
    ERROR_RATE_CRITICAL: float = 0.7  # Ngưỡng tỷ lệ lỗi nghiêm trọng
    ERROR_RATE_WARNING: float = 0.4  # Ngưỡng tỷ lệ lỗi cảnh báo
    MIN_REQUESTS_FOR_HEALTH_CHECK: int = 10  # Số request tối thiểu để kiểm tra sức khỏe
    
    # Cấu hình tác vụ dọn dẹp
    CLEANUP_INTERVAL_SECONDS: int = 300  # Khoảng cách tác vụ dọn dẹp (5 phút)
    
    # Cấu hình cache
    TOOL_CACHE_TTL_MINUTES: int = 10  # TTL cache định nghĩa công cụ
    
    # Cấu hình thử lại
    MAX_RETRIES: int = 3  # Số lần thử lại tối đa
    BASE_RETRY_DELAY_SECONDS: float = 1.0  # Độ trễ thử lại cơ bản
    MAX_RETRY_DELAY_SECONDS: float = 10.0  # Độ trễ thử lại tối đa
    
    # Cấu hình timeout
    DEFAULT_TIMEOUT_SECONDS: float = 60.0  # Thời gian timeout mặc định
    TOOL_CALL_TIMEOUT_SECONDS: float = 60.0  # Thời gian timeout gọi công cụ
    
    # Cấu hình log
    LOG_TOOL_ARGUMENTS: bool = True  # Có ghi log tham số công cụ hay không
    LOG_TOOL_RESULTS: bool = False  # Có ghi log kết quả công cụ hay không (có thể rất lớn)


# Instance cấu hình toàn cục
mcp_config = MCPConfig()