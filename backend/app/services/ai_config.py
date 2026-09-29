"""AI Quản lý cấu hình dịch vụ"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HTTPClientConfig:
    """HTTP Cấu hình client"""
    connect_timeout: float = 90.0
    read_timeout: float = 300.0
    write_timeout: float = 90.0
    pool_timeout: float = 90.0
    max_keepalive_connections: int = 50
    max_connections: int = 100
    keepalive_expiry: float = 60.0


@dataclass
class RetryConfig:
    """Cấu hình thử lại"""
    max_retries: int = 3
    base_delay: float = 0.2
    max_delay: float = 10.0
    exponential_base: int = 2
    non_retryable_status_codes: tuple = field(default_factory=lambda: (401, 403, 404))


@dataclass
class RateLimitConfig:
    """Cấu hình giới hạn tốc độ"""
    max_concurrent_requests: int = 5
    request_delay: float = 0.2


@dataclass
class AIClientConfig:
    """AI Cấu hình đầy đủ của client"""
    http: HTTPClientConfig = field(default_factory=HTTPClientConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)


# Cấu hình mặc định toàn cục
default_config = AIClientConfig()