"""Quản lý cấu hình ứng dụng"""
from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path
import logging
import os
import uuid

# Lấy thư mục gốc dự án (từ backend/app/config.py lên hai cấp)
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Module cấu hình dùng logging chuẩn (trước khi logger.py khởi tạo)
config_logger = logging.getLogger(__name__)

# Cấu hình database: PostgreSQL
# Lấy URL database từ biến môi trường
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://mumuai:password@localhost:5432/mumuai_novel")

config_logger.debug(f"Loại database: PostgreSQL")
config_logger.debug(f"URL database: {DATABASE_URL}")

class Settings(BaseSettings):
    """Cấu hình ứng dụng"""
    
    # Cấu hình ứng dụng
    app_name: str = "MuMuAINovel"
    app_version: str = "1.5.6"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False
    
    # Cấu hình log
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_to_file: bool = True  # Có xuất ra file hay không
    log_file_path: str = str(PROJECT_ROOT / "logs" / "app.log")
    log_max_bytes: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 30  # Giữ 30 file backup
    log_message_max_chars: int = 2000  # Số ký tự tối đa cho một thông báo log
    
    # Cấu hình CORS
    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
    
    # Cấu hình database - PostgreSQL
    database_url: str = DATABASE_URL
    
    # Cấu hình connection pool PostgreSQL (sau tối ưu hỗ trợ 150-200 user đồng thời)
    database_pool_size: int = 50  # Kích thước pool kết nối lõi (tối ưu: tăng từ 30 lên 50)
    database_max_overflow: int = 30  # Số kết nối tràn tối đa (tối ưu: tăng từ 20 lên 30)
    database_pool_timeout: int = 90  # Số giây timeout pool kết nối (tối ưu: tăng từ 60 lên 90)
    database_pool_recycle: int = 1800  # Số giây thu hồi kết nối (30 phút, tránh kết nối lâu bị hỏng)
    database_pool_pre_ping: bool = True  # Ping kiểm tra trước khi kết nối, đảm bảo kết nối hợp lệ
    database_pool_use_lifo: bool = True  # Dùng chiến lược LIFO để tăng tỷ lệ tái sử dụng kết nối
    
    # Cấu hình nâng cao connection pool
    database_echo_pool: bool = False  # Có ghi log connection pool hay không (dùng để debug)
    database_pool_reset_on_return: str = "rollback"  # Chiến lược reset khi trả kết nối: rollback/commit/none
    database_max_identifier_length: int = 128  # Độ dài tối đa identifier PostgreSQL
    
    # Cấu hình giám sát session
    database_session_max_active: int = 50  # Ngưỡng cảnh báo session đang hoạt động (giảm từ 100 xuống 50)
    database_session_leak_threshold: int = 100  # Ngưỡng cảnh báo nghiêm trọng rò rỉ session
    
    # Cấu hình giám sát database
    database_enable_slow_query_log: bool = True  # Bật log truy vấn chậm
    database_slow_query_threshold: float = 1.0  # Ngưỡng truy vấn chậm (giây)
    database_enable_metrics: bool = True  # Bật thu thập chỉ số hiệu năng
    
    # Cấu hình dịch vụ AI
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    xiaomi_mimo_api_key: Optional[str] = None
    xiaomi_mimo_base_url: str = "https://token-plan-cn.xiaomimimo.com/v1"
    gemini_api_key: Optional[str] = None
    gemini_base_url: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: Optional[str] = None
    default_ai_provider: str = "openai"
    default_model: str = "gpt-4"
    default_temperature: float = 0.7
    default_max_tokens: int = 32000
    # Allow Ollama / local Llama / Docker host.docker.internal as AI base URLs.
    # Default false keeps SSRF protection for public deployments.
    allow_private_ai_endpoints: bool = False
    # Comma-separated host allowlist, e.g. "host.docker.internal,127.0.0.1"
    allowed_ai_hosts: str = ""
    
    # Cấu hình MCP
    mcp_max_rounds: int = 3  # Số vòng gọi công cụ MCP tối đa (điều khiển thống nhất toàn cục)
    
    # Cấu hình LinuxDO OAuth2
    LINUXDO_CLIENT_ID: Optional[str] = None
    LINUXDO_CLIENT_SECRET: Optional[str] = None
    # Địa chỉ callback: khi triển khai Docker phải dùng domain thực hoặc IP máy chủ, không được dùng localhost
    # Phát triển cục bộ: http://localhost:8000/api/auth/callback
    # Môi trường production: https://your-domain.com/api/auth/callback hoặc http://your-ip:8000/api/auth/callback
    LINUXDO_REDIRECT_URI: Optional[str] = None
    # Cấu hình proxy riêng cho LinuxDO (chỉ dùng cho request token OAuth và thông tin người dùng, không ảnh hưởng request AI/SMTP/khác)
    # Ví dụ: http://127.0.0.1:7890
    LINUXDO_PROXY_URL: Optional[str] = None
    
    # Cấu hình URL frontend (dùng để redirect sau callback OAuth)
    # Phát triển cục bộ: http://localhost:8000
    # Môi trường production: https://your-domain.com hoặc http://your-ip:8000
    FRONTEND_URL: str = "http://localhost:8000"
    
    # Cấu hình quản trị viên ban đầu (LinuxDO user_id)
    INITIAL_ADMIN_LINUXDO_ID: Optional[str] = None
    
    # Cấu hình đăng nhập tài khoản cục bộ
    LOCAL_AUTH_ENABLED: bool = True  # Có bật đăng nhập tài khoản cục bộ hay không
    LOCAL_AUTH_USERNAME: Optional[str] = None  # Tên đăng nhập cục bộ
    LOCAL_AUTH_PASSWORD: Optional[str] = None  # Mật khẩu đăng nhập cục bộ
    LOCAL_AUTH_DISPLAY_NAME: str = "Người dùng cục bộ"  # Tên hiển thị người dùng cục bộ
    
    # Cấu hình session
    SESSION_EXPIRE_MINUTES: int = 120  # Thời gian hết hạn session (phút), mặc định 2 giờ
    SESSION_REFRESH_THRESHOLD_MINUTES: int = 30  # Ngưỡng làm mới session (phút), có thể làm mới khi thời gian còn lại ít hơn giá trị này
    SESSION_SECRET_KEY: Optional[str] = None  # Khóa ký session, môi trường production bắt buộc cấu hình thành giá trị ngẫu nhiên cường độ cao
    SESSION_COOKIE_SECURE: Optional[bool] = None  # Có ép buộc Cookie Secure hay không; khi None tự phán đoán theo DEBUG

    # Cấu hình SMTP mặc định của hệ thống (có thể bị ghi đè bởi cài đặt hệ thống của quản trị viên)
    SMTP_PROVIDER: str = "qq"
    SMTP_HOST: Optional[str] = "smtp.qq.com"
    SMTP_PORT: int = 465
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = False
    SMTP_USE_SSL: bool = True
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: str = "MuMuAINovel"
    EMAIL_AUTH_ENABLED: bool = True
    EMAIL_REGISTER_ENABLED: bool = True
    EMAIL_VERIFICATION_CODE_TTL_MINUTES: int = 10
    EMAIL_VERIFICATION_RESEND_INTERVAL_SECONDS: int = 60
    
    # Cấu hình Xưởng prompt
    WORKSHOP_MODE: str = "client"  # client: instance triển khai cục bộ, server: máy chủ trung tâm cloud
    WORKSHOP_CLOUD_URL: str = "https://mumuverse.space:1566"  # Địa chỉ dịch vụ cloud
    WORKSHOP_API_TIMEOUT: int = 30  # Thời gian timeout request API cloud (giây)
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Bỏ qua biến môi trường chưa định nghĩa, tránh lỗi xác thực


# Tạo instance cấu hình toàn cục
settings = Settings()
config_logger.info(f"Tải cấu hình hoàn tất: {settings.app_name} v{settings.app_version}")
config_logger.debug(f"Chế độ debug: {settings.debug}")
config_logger.debug(f"Nhà cung cấp AI: {settings.default_ai_provider}")


# ==================== Định danh instance Xưởng prompt ====================

def get_or_create_instance_id() -> str:
    """Lấy hoặc tạo định danh duy nhất của instance

    - Chế độ Server: dùng cố định "server" làm định danh, đảm bảo phân biệt với mọi instance Client
    - Chế độ Client: đọc từ file .instance_id hoặc tự sinh định danh duy nhất
    """
    # Chế độ Server dùng định danh cố định
    if settings.WORKSHOP_MODE.lower() == "server":
        config_logger.info("Chế độ Server: dùng định danh instance cố định 'server'")
        return "server"
    
    # Chế độ Client: đọc từ file hoặc sinh mới
    instance_file = PROJECT_ROOT / ".instance_id"
    if instance_file.exists():
        with open(instance_file, 'r') as f:
            instance_id = f.read().strip()
            if instance_id and instance_id != "server":  # Đảm bảo không xung đột với server
                return instance_id
    
    # Sinh ID instance mới
    instance_id = str(uuid.uuid4())[:12]
    try:
        with open(instance_file, 'w') as f:
            f.write(instance_id)
        config_logger.info(f"Sinh định danh instance mới: {instance_id}")
    except Exception as e:
        config_logger.warning(f"Không thể lưu định danh instance vào file: {e}")
    
    return instance_id

INSTANCE_ID = get_or_create_instance_id()

def is_workshop_server() -> bool:
    """Phán đoán instance hiện tại có phải server xưởng hay không"""
    return settings.WORKSHOP_MODE.lower() == "server"

config_logger.info(f"Chế độ Xưởng prompt: {settings.WORKSHOP_MODE}, ID instance: {INSTANCE_ID}")
