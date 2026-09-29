"""Middleware ID theo dõi request"""
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware ID theo dõi request

    Sinh ID duy nhất cho mỗi request, thêm vào ngữ cảnh log
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Xử lý request, thêm ID theo dõi

        Args:
            request: Đối tượng request
            call_next: Bộ xử lý tiếp theo

        Returns:
            Đối tượng response
        """
        # Lấy ID theo dõi từ header request, hoặc sinh mới
        request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        
        # Lưu ID request vào request.state, tiện truy cập sau
        request.state.request_id = request_id
        
        # Tạo bộ lọc log, tự động thêm request_id vào bản ghi log
        log_filter = RequestIDFilter(request_id)
        
        # Lấy logger gốc và thêm bộ lọc
        root_logger = logging.getLogger()
        root_logger.addFilter(log_filter)
        
        try:
            # Xử lý request
            response = await call_next(request)
            
            # Thêm ID request vào header response
            response.headers['X-Request-ID'] = request_id
            
            return response
        finally:
            # Gỡ bộ lọc, tránh ảnh hưởng request khác
            root_logger.removeFilter(log_filter)


class RequestIDFilter(logging.Filter):
    """Bộ lọc log, thêm thuộc tính request_id cho bản ghi log"""
    
    def __init__(self, request_id: str):
        """
        Khởi tạo bộ lọc

        Args:
            request_id: ID theo dõi request
        """
        super().__init__()
        self.request_id = request_id
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Thêm thuộc tính request_id cho bản ghi log

        Args:
            record: Bản ghi log

        Returns:
            True (không lọc log nào)
        """
        record.request_id = self.request_id
        return True