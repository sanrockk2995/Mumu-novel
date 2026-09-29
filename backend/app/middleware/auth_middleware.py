"""
Middleware xác thực - trích thông tin người dùng từ Cookie và inject vào request.state
Hỗ trợ request proxy từ instance khác (chức năng xưởng prompt)
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.user_manager import user_manager
from app.logger import get_logger
from app.security import verify_session_token

logger = get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware xác thực"""
    
    async def dispatch(self, request: Request, call_next):
        """
        Xử lý request, trích ID người dùng từ Cookie hoặc Header và inject vào request.state

        Với request proxy liên quan xưởng prompt (có Header X-Instance-ID),
        đọc định danh người dùng từ Header thay vì Cookie.
        """
        # Kiểm tra có phải request proxy từ instance khác không (xưởng prompt)
        instance_id = request.headers.get("X-Instance-ID")
        is_workshop_path = request.url.path.startswith("/api/prompt-workshop")
        
        if instance_id and is_workshop_path:
            # Request proxy từ instance khác
            header_user_id = request.headers.get("X-User-ID")
            
            request.state.is_proxy_request = True
            request.state.proxy_instance_id = instance_id
            
            if header_user_id:
                # Có định danh người dùng, dùng thông tin người dùng của proxy
                request.state.user_id = header_user_id  # Đây là định dạng "instance:user_id"
                request.state.user = None  # Request proxy không có đối tượng User thực
                request.state.is_admin = False
            else:
                # Không có định danh người dùng, truy cập ẩn danh
                request.state.user_id = None
                request.state.user = None
                request.state.is_admin = False
        else:
            # Request cục bộ hoặc đường dẫn phi xưởng, dùng xác thực Cookie
            request.state.is_proxy_request = False
            request.state.proxy_instance_id = None
            
            # Ưu tiên xác minh Cookie session có chữ ký; không còn tin user_id dạng text mà client có thể giả mạo.
            user_id = verify_session_token(request.cookies.get("session_token"))
            
            if user_id:
                user = await user_manager.get_user(user_id)
                if user:
                    # Kiểm tra người dùng có bị cấm không (trust_level = -1)
                    if user.trust_level == -1:
                        logger.warning(f"Người dùng bị cấm cố truy cập: {user_id} ({user.username})")
                        # Xóa trạng thái người dùng, coi như chưa đăng nhập
                        request.state.user_id = None
                        request.state.user = None
                        request.state.is_admin = False
                    else:
                        # Người dùng bình thường, inject trạng thái
                        request.state.user_id = user_id
                        request.state.user = user
                        request.state.is_admin = user.is_admin
                else:
                    # Người dùng không tồn tại, xóa trạng thái
                    request.state.user_id = None
                    request.state.user = None
                    request.state.is_admin = False
            else:
                # Chưa đăng nhập
                request.state.user_id = None
                request.state.user = None
                request.state.is_admin = False
        
        # Tiếp tục xử lý request
        response = await call_next(request)
        return response
