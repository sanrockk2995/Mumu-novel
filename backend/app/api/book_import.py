"""API nhập liệu tách sách"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logger import get_logger
from app.schemas.book_import import (
    BookImportApplyRequest,
    BookImportApplyResponse,
    BookImportPreviewResponse,
    BookImportRetryRequest,
    BookImportTaskCreateResponse,
    BookImportTaskCreateRequest,
    BookImportTaskStatusResponse,
)
from app.services.book_import_service import book_import_service
from app.api.settings import get_user_ai_service_from_db
from app.utils.sse_response import SSEResponse, create_sse_response

router = APIRouter(prefix="/book-import", tags=["Nhập liệu tách sách"])
logger = get_logger(__name__)

MAX_TXT_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/tasks", response_model=BookImportTaskCreateResponse, summary="Tạo tác vụ tách sách (tải lên TXT)")
async def create_book_import_task(
    request: Request,
    file: UploadFile = File(..., description="File TXT"),
    project_id: str | None = Form(default=None, description="Tham số tương thích: phiên bản hiện tại cố định tạo dự án mới, không hỗ trợ truyền vào"),
    create_new_project: bool = Form(default=True, description="Tham số tương thích: phiên bản hiện tại chỉ hỗ trợ true"),
    import_mode: str = Form(default="append", description="Chế độ nhập: append/overwrite"),
    extract_mode: str = Form(default="tail", description="Phạm vi phân tích: tail=cắt chương cuối, full=toàn bộ sách"),
    tail_chapter_count: int = Form(default=10, description="Khi extract_mode=tail, cắt số chương cuối, phải là bội số của 5; quá 50 sẽ xử lý tách toàn bộ sách"),
):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file .txt")

    if import_mode not in {"append", "overwrite"}:
        raise HTTPException(status_code=400, detail="import_mode chỉ hỗ trợ append hoặc overwrite")

    if extract_mode not in {"tail", "full"}:
        raise HTTPException(status_code=400, detail="extract_mode chỉ hỗ trợ tail hoặc full")
    if tail_chapter_count < 5:
        raise HTTPException(status_code=400, detail="tail_chapter_count không được nhỏ hơn 5")
    if tail_chapter_count % 5 != 0:
        raise HTTPException(status_code=400, detail="tail_chapter_count phải là bội số của 5")

    if tail_chapter_count > 50:
        extract_mode = "full"

    if project_id:
        raise HTTPException(status_code=400, detail="Hiện tại chỉ hỗ trợ nhập tạo dự án mới, không hỗ trợ chỉ định project_id")
    if not create_new_project:
        raise HTTPException(status_code=400, detail="Hiện tại chỉ hỗ trợ nhập tạo dự án mới")

    create_payload = BookImportTaskCreateRequest(
        extract_mode=extract_mode,
        tail_chapter_count=tail_chapter_count,
    )

    content = await file.read()
    if len(content) > MAX_TXT_SIZE:
        raise HTTPException(status_code=413, detail="Kích thước file vượt quá giới hạn 50MB")

    task = await book_import_service.create_task(
        user_id=user_id,
        filename=file.filename,
        file_content=content,
        project_id=None,
        create_new_project=True,
        import_mode=import_mode,
        extract_mode=create_payload.extract_mode,
        tail_chapter_count=create_payload.tail_chapter_count,
    )
    return task


@router.get("/tasks/{task_id}", response_model=BookImportTaskStatusResponse, summary="Truy vấn trạng thái tác vụ tách sách")
async def get_book_import_task_status(task_id: str, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    return await book_import_service.get_task_status(task_id=task_id, user_id=user_id)


@router.get("/tasks/{task_id}/preview", response_model=BookImportPreviewResponse, summary="Lấy bản xem trước tách sách")
async def get_book_import_preview(task_id: str, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    return await book_import_service.get_preview(task_id=task_id, user_id=user_id)


@router.post("/tasks/{task_id}/apply", response_model=BookImportApplyResponse, summary="Xác nhận và nhập")
async def apply_book_import(
    task_id: str,
    payload: BookImportApplyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    return await book_import_service.apply_import(
        task_id=task_id,
        user_id=user_id,
        payload=payload,
        db=db,
    )


@router.delete("/tasks/{task_id}", summary="Hủy tác vụ tách sách")
async def cancel_book_import_task(task_id: str, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    return await book_import_service.cancel_task(task_id=task_id, user_id=user_id)


@router.post("/tasks/{task_id}/apply-stream", summary="Xác nhận và nhập (tiến trình streaming SSE)")
async def apply_book_import_stream(
    task_id: str,
    payload: BookImportApplyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Giao diện streaming SSE: sau khi thực hiện nhập cơ bản, tạo từng bước thế giới quan/nghề nghiệp/nhân vật và đẩy tiến trình theo thời gian thực.
    Dùng asyncio.Queue để truyền thông báo tiến trình giữa dịch vụ và bộ tạo SSE.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # Dùng asyncio.Queue để đẩy tiến trình theo thời gian thực
    progress_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _progress_callback(message: str, progress: int, status: str = "processing") -> None:
        """Callback tiến trình: đưa vào hàng đợi để bộ tạo SSE tiêu thụ"""
        sse_msg = SSEResponse.format_sse({
            "type": "progress",
            "message": message,
            "progress": progress,
            "status": status,
        })
        await progress_queue.put(sse_msg)

    async def _run_import() -> None:
        """Thực hiện nhập trong tác vụ nền và đẩy tiến trình qua hàng đợi"""
        try:
            ai_service = await get_user_ai_service_from_db(user_id, db)
            result = await book_import_service.apply_import_stream(
                task_id=task_id,
                user_id=user_id,
                payload=payload,
                db=db,
                progress_callback=_progress_callback,
                ai_service=ai_service,
            )

            # Gửi kết quả
            await progress_queue.put(await SSEResponse.send_result({
                "success": result.success,
                "project_id": result.project_id,
                "statistics": result.statistics,
            }))
            await progress_queue.put(await SSEResponse.send_progress("Hoàn tất nhập!", 100, "success"))
            await progress_queue.put(await SSEResponse.send_done())
        except HTTPException as exc:
            await progress_queue.put(await SSEResponse.send_error(exc.detail, exc.status_code))
        except Exception as exc:
            logger.error(f"Nhập tách sách SSE thất bại: {exc}", exc_info=True)
            await progress_queue.put(await SSEResponse.send_error(str(exc), 500))
        finally:
            # Gửi tín hiệu kết thúc
            await progress_queue.put(None)

    async def _streaming_generator() -> AsyncGenerator[str, None]:
        yield await SSEResponse.send_progress("Bắt đầu nhập dữ liệu tách sách...", 0, "processing")

        # Khởi chạy tác vụ nhập nền
        import_task = asyncio.create_task(_run_import())

        try:
            while True:
                msg = await progress_queue.get()
                if msg is None:
                    break
                yield msg
        except GeneratorExit:
            import_task.cancel()
        except Exception as exc:
            logger.error(f"Bộ tạo SSE gặp ngoại lệ: {exc}", exc_info=True)
            yield await SSEResponse.send_error(str(exc), 500)

    return create_sse_response(_streaming_generator())


@router.post("/tasks/{task_id}/retry-stream", summary="Thử lại các bước tạo thất bại (tiến trình streaming SSE)")
async def retry_failed_steps_stream(
    task_id: str,
    payload: BookImportRetryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Giao diện streaming SSE: chỉ thử lại các bước tạo bằng AI bị thất bại trong quá trình nhập trước đó (thế giới quan/nghề nghiệp/nhân vật).
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    progress_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _progress_callback(message: str, progress: int, status: str = "processing") -> None:
        sse_msg = SSEResponse.format_sse({
            "type": "progress",
            "message": message,
            "progress": progress,
            "status": status,
        })
        await progress_queue.put(sse_msg)

    async def _run_retry() -> None:
        try:
            ai_service = await get_user_ai_service_from_db(user_id, db)
            result = await book_import_service.retry_failed_steps_stream(
                task_id=task_id,
                user_id=user_id,
                steps_to_retry=payload.steps,
                db=db,
                progress_callback=_progress_callback,
                ai_service=ai_service,
            )

            await progress_queue.put(await SSEResponse.send_result(result))

            if result.get("still_failed"):
                await progress_queue.put(await SSEResponse.send_progress(
                    f"Hoàn tất thử lại, vẫn còn {len(result['still_failed'])} bước thất bại",
                    100,
                    "warning",
                ))
            else:
                await progress_queue.put(await SSEResponse.send_progress("Thử lại tất cả các bước thành công!", 100, "success"))

            await progress_queue.put(await SSEResponse.send_done())
        except HTTPException as exc:
            await progress_queue.put(await SSEResponse.send_error(exc.detail, exc.status_code))
        except Exception as exc:
            logger.error(f"Thử lại tách sách SSE thất bại: {exc}", exc_info=True)
            await progress_queue.put(await SSEResponse.send_error(str(exc), 500))
        finally:
            await progress_queue.put(None)

    async def _streaming_generator() -> AsyncGenerator[str, None]:
        yield await SSEResponse.send_progress("Bắt đầu thử lại các bước tạo thất bại...", 0, "processing")

        retry_task = asyncio.create_task(_run_retry())

        try:
            while True:
                msg = await progress_queue.get()
                if msg is None:
                    break
                yield msg
        except GeneratorExit:
            retry_task.cancel()
        except Exception as exc:
            logger.error(f"Bộ tạo thử lại SSE gặp ngoại lệ: {exc}", exc_info=True)
            yield await SSEResponse.send_error(str(exc), 500)

    return create_sse_response(_streaming_generator())
