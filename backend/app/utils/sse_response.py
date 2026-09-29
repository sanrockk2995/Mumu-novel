"""Lớp công cụ response Server-Sent Events (SSE)"""
import json
import asyncio
from enum import Enum
from typing import AsyncGenerator, Dict, Any, Optional, Callable
from dataclasses import dataclass
from fastapi.responses import StreamingResponse
from app.logger import get_logger, summarize_log_value

logger = get_logger(__name__)


class ProgressStage(Enum):
    """Enum giai đoạn tiến độ chuẩn hóa"""
    # Giai đoạn khởi tạo (0-5%)
    INIT = "init"
    # Giai đoạn tải dữ liệu (5-15%)
    LOADING = "loading"
    # Giai đoạn chuẩn bị prompt (15-20%)
    PREPARING = "preparing"
    # Giai đoạn AI sinh (20-85%)
    GENERATING = "generating"
    # Giai đoạn phân tích dữ liệu (85-92%)
    PARSING = "parsing"
    # Giai đoạn lưu dữ liệu (92-98%)
    SAVING = "saving"
    # Giai đoạn hoàn thành (100%)
    COMPLETE = "complete"


@dataclass
class StageConfig:
    """Cấu hình giai đoạn"""
    start: int  # Tiến độ bắt đầu
    end: int    # Tiến độ kết thúc
    default_message: str  # Thông báo mặc định


# Cấu hình giai đoạn tiến độ chuẩn
STAGE_CONFIGS: Dict[ProgressStage, StageConfig] = {
    ProgressStage.INIT: StageConfig(0, 5, "Bắt đầu xử lý..."),
    ProgressStage.LOADING: StageConfig(5, 15, "Đang tải dữ liệu..."),
    ProgressStage.PREPARING: StageConfig(15, 20, "Đang chuẩn bị prompt AI..."),
    ProgressStage.GENERATING: StageConfig(20, 85, "AI đang sinh..."),
    ProgressStage.PARSING: StageConfig(85, 92, "Đang phân tích dữ liệu..."),
    ProgressStage.SAVING: StageConfig(92, 98, "Đang lưu vào database..."),
    ProgressStage.COMPLETE: StageConfig(100, 100, "Hoàn thành!"),
}


class WizardProgressTracker:
    """
    Trình theo dõi tiến độ wizard - quản lý chuẩn hóa việc đẩy tiến độ SSE

    Ví dụ sử dụng:
        tracker = WizardProgressTracker("Thế giới quan")
        yield await tracker.start()
        yield await tracker.loading("Đang tải thông tin dự án")
        yield await tracker.preparing()
        async for chunk in ai_stream:
            yield await tracker.generating_chunk(chunk, len(accumulated))
        yield await tracker.parsing()
        yield await tracker.saving("Đang lưu dữ liệu thế giới quan")
        yield await tracker.complete()
    """
    
    def __init__(self, task_name: str = "Nhiệm vụ"):
        """
        Khởi tạo trình theo dõi tiến độ

        Args:
            task_name: Tên nhiệm vụ, dùng làm tiền tố thông báo
        """
        self.task_name = task_name
        self.current_stage = ProgressStage.INIT
        self.current_progress = 0
        self._last_generating_progress = 20  # Giá trị tiến độ cuối của giai đoạn sinh
    
    def _get_stage_progress(
        self,
        stage: ProgressStage,
        sub_progress: float = 0.0
    ) -> int:
        """
        Tính giá trị tiến độ trong giai đoạn

        Args:
            stage: Giai đoạn hiện tại
            sub_progress: Tiến độ con trong giai đoạn (0.0-1.0)

        Returns:
            Giá trị tiến độ tổng (0-100)
        """
        config = STAGE_CONFIGS[stage]
        if sub_progress <= 0:
            return config.start
        if sub_progress >= 1:
            return config.end
        return config.start + int((config.end - config.start) * sub_progress)
    
    async def start(self, message: str = None) -> str:
        """Giai đoạn bắt đầu"""
        self.current_stage = ProgressStage.INIT
        self.current_progress = 0
        msg = message or f"Bắt đầu sinh {self.task_name}..."
        return await SSEResponse.send_progress(msg, 0, "processing")
    
    async def loading(self, message: str = None, sub_progress: float = 0.5) -> str:
        """Giai đoạn tải dữ liệu"""
        self.current_stage = ProgressStage.LOADING
        progress = self._get_stage_progress(ProgressStage.LOADING, sub_progress)
        self.current_progress = progress
        msg = message or STAGE_CONFIGS[ProgressStage.LOADING].default_message
        return await SSEResponse.send_progress(msg, progress, "processing")
    
    async def preparing(self, message: str = None) -> str:
        """Giai đoạn chuẩn bị prompt"""
        self.current_stage = ProgressStage.PREPARING
        progress = self._get_stage_progress(ProgressStage.PREPARING, 0.5)
        self.current_progress = progress
        msg = message or STAGE_CONFIGS[ProgressStage.PREPARING].default_message
        return await SSEResponse.send_progress(msg, progress, "processing")
    
    async def generating(
        self,
        current_chars: int = 0,
        estimated_total: int = 5000,
        message: str = None,
        retry_count: int = 0,
        max_retries: int = 3
    ) -> str:
        """
        Cập nhật tiến độ giai đoạn AI sinh

        Args:
            current_chars: Số ký tự đã sinh hiện tại
            estimated_total: Tổng số ký tự ước tính
            message: Thông báo tùy chỉnh
            retry_count: Số lần thử lại hiện tại
            max_retries: Số lần thử lại tối đa
        """
        self.current_stage = ProgressStage.GENERATING
        
        # Tính tiến độ sinh (0.0-1.0)
        sub_progress = min(current_chars / max(estimated_total, 1), 1.0)
        progress = self._get_stage_progress(ProgressStage.GENERATING, sub_progress)
        
        # Đảm bảo tiến độ tăng đơn điệu
        if progress < self._last_generating_progress:
            progress = self._last_generating_progress
        else:
            self._last_generating_progress = progress
        
        self.current_progress = progress
        
        # Xây dựng thông báo
        retry_suffix = f" (Thử lại {retry_count}/{max_retries})" if retry_count > 0 else ""
        if message:
            msg = f"{message}{retry_suffix}"
        else:
            msg = f"Đang sinh {self.task_name}... ({current_chars} ký tự){retry_suffix}"
        
        return await SSEResponse.send_progress(msg, progress, "processing")
    
    async def generating_chunk(self, chunk: str) -> str:
        """Gửi khối nội dung đã sinh"""
        return await SSEResponse.send_chunk(chunk)
    
    async def parsing(self, message: str = None, sub_progress: float = 0.5) -> str:
        """Giai đoạn phân tích dữ liệu"""
        self.current_stage = ProgressStage.PARSING
        progress = self._get_stage_progress(ProgressStage.PARSING, sub_progress)
        self.current_progress = progress
        msg = message or f"Đang phân tích dữ liệu {self.task_name}..."
        return await SSEResponse.send_progress(msg, progress, "processing")
    
    async def saving(self, message: str = None, sub_progress: float = 0.5) -> str:
        """Giai đoạn lưu dữ liệu"""
        self.current_stage = ProgressStage.SAVING
        progress = self._get_stage_progress(ProgressStage.SAVING, sub_progress)
        self.current_progress = progress
        msg = message or f"Đang lưu {self.task_name} vào database..."
        return await SSEResponse.send_progress(msg, progress, "processing")
    
    async def complete(self, message: str = None) -> str:
        """Giai đoạn hoàn thành"""
        self.current_stage = ProgressStage.COMPLETE
        self.current_progress = 100
        msg = message or f"{self.task_name} đã sinh xong!"
        return await SSEResponse.send_progress(msg, 100, "success")
    
    async def warning(self, message: str) -> str:
        """Gửi thông báo cảnh báo (giữ tiến độ hiện tại)"""
        return await SSEResponse.send_progress(
            f"⚠️ {message}",
            self.current_progress,
            "warning"
        )
    
    async def retry(self, retry_count: int, max_retries: int, reason: str = "Chuẩn bị thử lại") -> str:
        """Gửi thông báo thử lại"""
        return await SSEResponse.send_progress(
            f"⚠️ {reason}... ({retry_count}/{max_retries})",
            self.current_progress,
            "warning"
        )
    
    async def error(self, error_message: str, code: int = 500) -> str:
        """Gửi thông báo lỗi"""
        return await SSEResponse.send_error(error_message, code)
    
    async def result(self, data: Dict[str, Any]) -> str:
        """Gửi dữ liệu kết quả"""
        return await SSEResponse.send_result(data)
    
    async def done(self) -> str:
        """Gửi tín hiệu hoàn thành"""
        return await SSEResponse.send_done()
    
    async def heartbeat(self) -> str:
        """Gửi heartbeat"""
        return await SSEResponse.send_heartbeat()
    
    def reset_generating_progress(self):
        """Đặt lại tiến độ giai đoạn sinh (dùng khi thử lại)"""
        self._last_generating_progress = 20


class SSEResponse:
    """Trình xây dựng response SSE"""
    
    @staticmethod
    def format_sse(data: Dict[str, Any], event: Optional[str] = None) -> str:
        """
        Định dạng thông báo SSE

        Args:
            data: Dict dữ liệu cần gửi
            event: Loại sự kiện (tùy chọn)

        Returns:
            Chuỗi thông báo SSE đã định dạng
        """
        try:
            message = ""
            if event:
                message += f"event: {event}\n"
            message += f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            return message
        except Exception as e:
            logger.error(f"❌ Định dạng SSE thất bại: {type(e).__name__}: {e}")
            logger.error(f"   Kiểu data: {type(data)}")
            logger.error(f"   Tóm tắt data: {summarize_log_value(data)}")
            # Trả về thông báo lỗi thay vì crash
            error_message = ""
            if event:
                error_message += f"event: {event}\n"
            error_message += f'data: {{"type": "error", "error": "Định dạng SSE thất bại: {str(e)}", "code": 500}}\n\n'
            return error_message
    
    @staticmethod
    async def send_progress(
        message: str,
        progress: int,
        status: str = "processing"
    ) -> str:
        """
        Gửi thông báo tiến độ

        Args:
            message: Thông báo tiến độ
            progress: Phần trăm tiến độ (0-100)
            status: Trạng thái (processing/success/error)
        """
        return SSEResponse.format_sse({
            "type": "progress",
            "message": message,
            "progress": progress,
            "status": status
        })
    
    @staticmethod
    async def send_chunk(content: str) -> str:
        """
        Gửi khối nội dung (dùng để stream nội dung AI sinh)

        Args:
            content: Khối nội dung
        """
        return SSEResponse.format_sse({
            "type": "chunk",
            "content": content
        })
    
    @staticmethod
    async def send_result(data: Dict[str, Any]) -> str:
        """
        Gửi kết quả cuối cùng

        Args:
            data: Dữ liệu kết quả
        """
        return SSEResponse.format_sse({
            "type": "result",
            "data": data
        })
    
    @staticmethod
    async def send_event(event: str, data: Dict[str, Any]) -> str:
        """
        Gửi thông báo SSE loại sự kiện tùy chỉnh

        Args:
            event: Tên loại sự kiện
            data: Dữ liệu sự kiện
        """
        return SSEResponse.format_sse(data, event=event)
    
    @staticmethod
    async def send_error(error: str, code: int = 500) -> str:
        """
        Gửi thông báo lỗi

        Args:
            error: Mô tả lỗi
            code: Mã lỗi
        """
        return SSEResponse.format_sse({
            "type": "error",
            "error": error,
            "code": code
        })
    
    @staticmethod
    async def send_done() -> str:
        """Gửi thông báo hoàn thành"""
        return SSEResponse.format_sse({
            "type": "done"
        })
    
    @staticmethod
    async def send_heartbeat() -> str:
        """Gửi thông báo heartbeat (giữ kết nối hoạt động)"""
        return ": heartbeat\n\n"


async def create_sse_generator(
    async_gen: AsyncGenerator[str, None],
    show_progress: bool = True
) -> AsyncGenerator[str, None]:
    """
    Tạo wrapper generator SSE

    Args:
        async_gen: Generator bất đồng bộ
        show_progress: Có hiển thị tiến độ hay không

    Yields:
        Thông báo SSE đã định dạng
    """
    try:
        if show_progress:
            yield await SSEResponse.send_progress("Bắt đầu sinh...", 0)
        
        # Tích lũy nội dung để tính tiến độ
        accumulated_content = ""
        chunk_count = 0
        
        async for chunk in async_gen:
            chunk_count += 1
            accumulated_content += chunk
            
            # Gửi khối nội dung
            yield await SSEResponse.send_chunk(chunk)
            
            # Mỗi 10 khối gửi một heartbeat
            if chunk_count % 10 == 0:
                yield await SSEResponse.send_heartbeat()
        
        if show_progress:
            yield await SSEResponse.send_progress("Sinh hoàn thành", 100, "success")
        
        # Gửi tín hiệu hoàn thành
        yield await SSEResponse.send_done()
        
    except Exception as e:
        logger.error(f"Lỗi generator SSE: {str(e)}")
        yield await SSEResponse.send_error(str(e))


class _HeartbeatSentinel:
    """Đối tượng sentinel heartbeat, dùng để đánh dấu sự kiện heartbeat (không phải nội dung AI)"""
    pass

HEARTBEAT = _HeartbeatSentinel()


async def wrap_stream_with_heartbeat(
    async_gen: AsyncGenerator,
    heartbeat_interval: float = 15.0
) -> AsyncGenerator:
    """
    Bọc generator bất đồng bộ, sinh sentinel heartbeat khi chờ dữ liệu để tránh ngắt kết nối do timeout.

    Cách dùng:
        async for chunk in wrap_stream_with_heartbeat(
            ai_service.generate_text_stream(prompt),
            heartbeat_interval=15
        ):
            if chunk is HEARTBEAT:
                yield await tracker.heartbeat()
                continue
            # chunk là dữ liệu AI gốc
    """
    ait = async_gen.__aiter__()
    while True:
        try:
            item = await asyncio.wait_for(ait.__anext__(), timeout=heartbeat_interval)
            yield item
        except asyncio.TimeoutError:
            # Chờ timeout, sinh sentinel heartbeat
            yield HEARTBEAT
        except StopAsyncIteration:
            return


def create_sse_response(generator: AsyncGenerator[str, None]) -> StreamingResponse:
    """
    Tạo SSE StreamingResponse - tương thích giao thức HTTP/2

    Args:
        generator: Generator thông báo SSE

    Returns:
        Đối tượng StreamingResponse

    Lưu ý:
    - HTTP/2 không hỗ trợ header Connection, đã loại bỏ
    - Chỉ định rõ charset=utf-8 để đảm bảo mã hóa đúng
    - Thêm header CORS để hỗ trợ request cross-domain
    """
    async def wrapper():
        """Bọc generator để bắt GeneratorExit khi khởi tạo StreamingResponse"""
        try:
            async for chunk in generator:
                yield chunk
        except GeneratorExit:
            # StreamingResponse khi khởi tạo sẽ kiểm tra kiểu, gây ra GeneratorExit
            # Đây là hành vi bình thường, không cần ghi log cảnh báo
            pass
    
    return StreamingResponse(
        wrapper(),
        media_type="text/event-stream; charset=utf-8",  # Chỉ định rõ charset
        headers={
            "Cache-Control": "no-cache, no-transform",  # Tắt cache và chuyển đổi
            # Loại bỏ Connection: keep-alive (không tương thích HTTP/2)
            "X-Accel-Buffering": "no",  # Tắt buffer nginx
            "Access-Control-Allow-Origin": "*",  # Hỗ trợ CORS
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )
