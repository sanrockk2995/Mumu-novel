"""Điểm vào chính của ứng dụng FastAPI"""
from fastapi import FastAPI, Request, status, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
import mimetypes
import sys

from app.config import settings as config_settings
from app.database import close_db, _session_stats
from app.logger import setup_logging, get_logger
from app.middleware import RequestIDMiddleware
from app.middleware.auth_middleware import AuthMiddleware
from app.mcp import mcp_client, register_status_sync

setup_logging(
    level=config_settings.log_level,
    log_to_file=config_settings.log_to_file,
    log_file_path=config_settings.log_file_path,
    max_bytes=config_settings.log_max_bytes,
    backup_count=config_settings.log_backup_count,
    message_max_chars=config_settings.log_message_max_chars,
)
logger = get_logger(__name__)


# Không phụ thuộc registry Windows, đảm bảo script module frontend luôn trả về đúng loại MIME.
STATIC_MIME_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".wasm": "application/wasm",
}

for _suffix, _media_type in STATIC_MIME_TYPES.items():
    mimetypes.add_type(_media_type, _suffix, strict=True)


def get_static_media_type(path: Path) -> str:
    """Trả về loại MIME file tĩnh ổn định, tránh loại không xác định bị trả về text/plain."""
    return (
        STATIC_MIME_TYPES.get(path.suffix.lower())
        or mimetypes.guess_type(path.name)[0]
        or "application/octet-stream"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời ứng dụng"""
    # Đăng ký dịch vụ đồng bộ trạng thái MCP
    register_status_sync()

    # Bảo đảm an toàn: đảm bảo bảng tác vụ nền tồn tại (tương thích triển khai cũ chưa chạy migration Alembic)
    try:
        from app.database import get_engine
        from app.models.background_task import BackgroundTask
        from app.models.batch_generation_task import BatchGenerationTask
        from app.models.analysis_task import AnalysisTask
        from sqlalchemy import update as sql_update
        _startup_engine = await get_engine("system")
        async with _startup_engine.begin() as conn:
            # Chỉ tạo bảng background_tasks (nếu chưa có), không ảnh hưởng bảng khác
            await conn.run_sync(
                lambda sync_conn: BackgroundTask.__table__.create(sync_conn, checkfirst=True)
            )
            interrupted_at = datetime.now()
            await conn.execute(
                sql_update(BackgroundTask)
                .where(BackgroundTask.status.in_(["pending", "running"]))
                .values(
                    status="failed",
                    error_message="Dịch vụ khởi động lại, tác vụ nền đã bị gián đoạn",
                    status_message="Dịch vụ khởi động lại, tác vụ đã bị gián đoạn, vui lòng khởi tạo lại",
                    completed_at=interrupted_at,
                    updated_at=interrupted_at,
                )
            )
            await conn.execute(
                sql_update(BatchGenerationTask)
                .where(BatchGenerationTask.status.in_(["pending", "running"]))
                .values(
                    status="failed",
                    error_message="Dịch vụ khởi động lại, tác vụ sinh hàng loạt đã bị gián đoạn",
                    completed_at=interrupted_at,
                )
            )
            await conn.execute(
                sql_update(AnalysisTask)
                .where(AnalysisTask.status.in_(["pending", "running"]))
                .values(
                    status="failed",
                    error_message="Dịch vụ khởi động lại, tác vụ phân tích chương đã bị gián đoạn",
                    progress=0,
                    completed_at=interrupted_at,
                )
            )
        logger.info("Kiểm tra bảng tác vụ nền hoàn tất")
    except Exception as e:
        logger.warning(f"Kiểm tra bảng tác vụ nền thất bại (không ảnh hưởng khởi động): {e}")

    logger.info("Ứng dụng khởi động hoàn tất")
    
    yield
    
    # Dọn dẹp plugin MCP
    await mcp_client.cleanup()
    
    # Dọn dẹp pool HTTP client
    from app.services.ai_service import cleanup_http_clients
    await cleanup_http_clients()
    
    # Đóng kết nối database
    await close_db()
    
    logger.info("Ứng dụng đã đóng")


app = FastAPI(
    title=config_settings.app_name,
    version=config_settings.app_version,
    description="Công cụ viết tiểu thuyết AI - trợ lý sáng tác tiểu thuyết thông minh",
    lifespan=lifespan
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Xử lý lỗi kiểm tra request"""
    logger.error(f"Kiểm tra request thất bại: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Kiểm tra tham số request thất bại",
            "errors": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Xử lý mọi exception chưa được bắt"""
    logger.error(f"Exception chưa xử lý: {type(exc).__name__}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Lỗi nội bộ máy chủ",
            "message": str(exc) if config_settings.debug else "Vui lòng thử lại sau"
        }
    )

app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuthMiddleware)

if config_settings.debug:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
async def health_check():
    """Kiểm tra sức khỏe"""
    return {"status": "ok"}


@app.get("/health/db-sessions")
async def db_session_stats(request: Request):
    """
    Thống kê session database (giám sát rò rỉ kết nối)

    Trả về:
    - created: tổng số session đã tạo
    - closed: tổng số session đã đóng
    - active: số session đang hoạt động (nên gần 0)
    - errors: số lần lỗi
    - generator_exits: số lần SSE ngắt kết nối
    - last_check: thời gian kiểm tra cuối
    """
    if not getattr(request.state, "is_admin", False):
        raise HTTPException(status_code=403, detail="Cần quyền quản trị viên")
    return {
        "status": "ok",
        "session_stats": _session_stats,
        "warning": "Số session đang hoạt động quá nhiều" if _session_stats["active"] > 10 else None
    }


from app.api import (
    projects, outlines, outline_transfer, characters, chapters,
    wizard_stream, relationships, organizations,
    auth, users, settings, writing_styles, memories,
    mcp_plugins, admin, inspiration, prompt_templates,
    changelog, careers, foreshadows, prompt_workshop, book_import,
    project_covers, project_agent, tasks, skills, announcements
)

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

app.include_router(projects.router, prefix="/api")
app.include_router(project_covers.router, prefix="/api")
app.include_router(project_agent.router, prefix="/api")
app.include_router(wizard_stream.router, prefix="/api")
app.include_router(inspiration.router, prefix="/api")
app.include_router(outlines.router, prefix="/api")
app.include_router(outline_transfer.router, prefix="/api")
app.include_router(characters.router, prefix="/api")
app.include_router(careers.router, prefix="/api")  # API quản lý nghề nghiệp
app.include_router(chapters.router, prefix="/api")
app.include_router(relationships.router, prefix="/api")
app.include_router(organizations.router, prefix="/api")
app.include_router(writing_styles.router, prefix="/api")
app.include_router(memories.router)  # API quản lý ký ức (đã gồm tiền tố /api)
app.include_router(foreshadows.router)  # API quản lý phục bút (đã gồm tiền tố /api)
app.include_router(mcp_plugins.router, prefix="/api")  # API quản lý plugin MCP
app.include_router(prompt_templates.router, prefix="/api")  # API quản lý mẫu prompt
app.include_router(changelog.router, prefix="/api")  # API nhật ký cập nhật
app.include_router(skills.router)  # Skill API (đã gồm tiền tố /api)
app.include_router(prompt_workshop.router, prefix="/api")  # API xưởng prompt
app.include_router(book_import.router, prefix="/api")  # API nhập bóc sách
app.include_router(tasks.router, prefix="/api")  # API tác vụ nền
app.include_router(announcements.router, prefix="/api")  # API thông báo

if getattr(sys, "frozen", False):
    static_dir = Path(sys._MEIPASS) / "backend" / "static"
    generated_assets_root_dir = Path(sys.executable).parent / "storage"
else:
    static_dir = Path(__file__).parent.parent / "static"
    generated_assets_root_dir = Path(__file__).parent.parent / "storage"
generated_covers_dir = generated_assets_root_dir / "generated_covers"
generated_covers_dir.mkdir(parents=True, exist_ok=True)
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")
    app.mount("/generated-assets/covers", StaticFiles(directory=str(generated_covers_dir)), name="generated-covers")
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Phục vụ SPA, mọi đường dẫn phi API trả về index.html"""
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"detail": "Đường dẫn API không tồn tại"}
            )
        
        file_path = static_dir / full_path
        try:
            resolved_file = file_path.resolve()
            resolved_static = static_dir.resolve()
            resolved_file.relative_to(resolved_static)
        except ValueError:
            return JSONResponse(
                status_code=404,
                content={"detail": "Trang không tồn tại"}
            )

        if resolved_file.is_file():
            return FileResponse(
                resolved_file,
                media_type=get_static_media_type(resolved_file),
            )
        
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        
        return JSONResponse(
            status_code=404,
            content={"detail": "Trang không tồn tại"}
        )
else:
    logger.warning("Thư mục file tĩnh không tồn tại, hãy build frontend trước: cd frontend && npm run build")
    
    @app.get("/")
    async def root():
        return {
            "message": "Chào mừng đến với MuMuAINovel",
            "version": config_settings.app_version,
            "docs": "/docs",
            "notice": "Hãy build frontend trước: cd frontend && npm run build"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=config_settings.app_host,
        port=config_settings.app_port,
        reload=config_settings.debug
    )
