"""Route API quản lý manh mối ẩn (foreshadow)"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.database import get_db
from app.api.common import verify_project_access
from app.services.foreshadow_service import foreshadow_service
from app.schemas.foreshadow import (
    ForeshadowCreate,
    ForeshadowUpdate,
    ForeshadowResponse,
    ForeshadowListResponse,
    ForeshadowStatsResponse,
    PlantForeshadowRequest,
    ResolveForeshadowRequest,
    SyncFromAnalysisRequest,
    SyncFromAnalysisResponse,
    ForeshadowContextResponse
)
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/foreshadows", tags=["foreshadows"])


@router.get("/projects/{project_id}", response_model=ForeshadowListResponse)
async def get_project_foreshadows(
    project_id: str,
    request: Request,
    status: Optional[str] = Query(None, description="Lọc trạng thái: pending/planted/resolved/abandoned"),
    category: Optional[str] = Query(None, description="Lọc phân loại"),
    source_type: Optional[str] = Query(None, description="Lọc nguồn: analysis/manual"),
    is_long_term: Optional[bool] = Query(None, description="Có phải manh mối ẩn dài hạn không"),
    page: int = Query(1, ge=1, description="Số trang"),
    limit: int = Query(50, ge=1, le=100, description="Số lượng mỗi trang"),
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy tất cả manh mối ẩn của dự án

    Hỗ trợ lọc theo trạng thái, phân loại, nguồn, hỗ trợ phân trang
    """
    try:
        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(project_id, user_id, db)

        result = await foreshadow_service.get_project_foreshadows(
            db=db,
            project_id=project_id,
            status=status,
            category=category,
            source_type=source_type,
            is_long_term=is_long_term,
            page=page,
            limit=limit
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Lấy danh sách manh mối ẩn thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lấy danh sách manh mối ẩn thất bại: {str(e)}")


@router.get("/projects/{project_id}/stats", response_model=ForeshadowStatsResponse)
async def get_foreshadow_stats(
    project_id: str,
    request: Request,
    current_chapter: Optional[int] = Query(None, ge=1, description="Số chương hiện tại (dùng để tính quá hạn)"),
    db: AsyncSession = Depends(get_db)
):
    """Lấy thống kê manh mối ẩn của dự án"""
    try:
        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(project_id, user_id, db)

        stats = await foreshadow_service.get_stats(db, project_id, current_chapter)
        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Lấy thống kê manh mối ẩn thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lấy thống kê manh mối ẩn thất bại: {str(e)}")


@router.get("/projects/{project_id}/context/{chapter_number}", response_model=ForeshadowContextResponse)
async def get_chapter_foreshadow_context(
    project_id: str,
    chapter_number: int,
    request: Request,
    include_pending: bool = Query(True, description="Bao gồm manh mối ẩn đang chờ gieo"),
    include_overdue: bool = Query(True, description="Bao gồm manh mối ẩn quá hạn"),
    lookahead: int = Query(5, ge=1, le=20, description="Nhìn trước bao nhiêu chương"),
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy ngữ cảnh manh mối ẩn khi tạo chương

    Dùng để nhắc nhở manh mối ẩn khi tạo chương
    """
    try:
        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(project_id, user_id, db)

        context = await foreshadow_service.build_chapter_context(
            db=db,
            project_id=project_id,
            chapter_number=chapter_number,
            include_pending=include_pending,
            include_overdue=include_overdue,
            lookahead=lookahead
        )

        return context

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Lấy ngữ cảnh manh mối ẩn thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lấy ngữ cảnh manh mối ẩn thất bại: {str(e)}")


@router.get("/projects/{project_id}/pending-resolve")
async def get_pending_resolve_foreshadows(
    project_id: str,
    request: Request,
    current_chapter: int = Query(..., ge=1, description="Số chương hiện tại"),
    lookahead: int = Query(5, ge=1, le=20, description="Nhìn trước bao nhiêu chương"),
    db: AsyncSession = Depends(get_db)
):
    """Lấy danh sách manh mối ẩn đang chờ thu hồi (dùng để nhắc khi tạo chương)"""
    try:
        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(project_id, user_id, db)

        foreshadows = await foreshadow_service.get_pending_resolve_foreshadows(
            db=db,
            project_id=project_id,
            current_chapter=current_chapter,
            lookahead=lookahead
        )

        return {
            "total": len(foreshadows),
            "items": [f.to_dict() for f in foreshadows]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Lấy manh mối ẩn đang chờ thu hồi thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lấy manh mối ẩn đang chờ thu hồi thất bại: {str(e)}")


@router.get("/{foreshadow_id}", response_model=ForeshadowResponse)
async def get_foreshadow(
    foreshadow_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy chi tiết một manh mối ẩn"""
    try:
        foreshadow = await foreshadow_service.get_foreshadow(db, foreshadow_id)

        if not foreshadow:
            raise HTTPException(status_code=404, detail="Manh mối ẩn không tồn tại")

        # Xác thực quyền
        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(foreshadow.project_id, user_id, db)

        return foreshadow.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Lấy chi tiết manh mối ẩn thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lấy chi tiết manh mối ẩn thất bại: {str(e)}")


@router.post("", response_model=ForeshadowResponse)
async def create_foreshadow(
    data: ForeshadowCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo manh mối ẩn (thêm thủ công)

    Tạo một manh mối ẩn tùy chỉnh mới
    """
    try:
        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(data.project_id, user_id, db)

        foreshadow = await foreshadow_service.create_foreshadow(db, data)
        return foreshadow.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Tạo manh mối ẩn thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Tạo manh mối ẩn thất bại: {str(e)}")


@router.put("/{foreshadow_id}", response_model=ForeshadowResponse)
async def update_foreshadow(
    foreshadow_id: str,
    data: ForeshadowUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Cập nhật manh mối ẩn"""
    try:
        foreshadow = await foreshadow_service.get_foreshadow(db, foreshadow_id)

        if not foreshadow:
            raise HTTPException(status_code=404, detail="Manh mối ẩn không tồn tại")

        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(foreshadow.project_id, user_id, db)

        updated = await foreshadow_service.update_foreshadow(db, foreshadow_id, data)
        return updated.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Cập nhật manh mối ẩn thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cập nhật manh mối ẩn thất bại: {str(e)}")


@router.delete("/{foreshadow_id}")
async def delete_foreshadow(
    foreshadow_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Xóa manh mối ẩn"""
    try:
        foreshadow = await foreshadow_service.get_foreshadow(db, foreshadow_id)

        if not foreshadow:
            raise HTTPException(status_code=404, detail="Manh mối ẩn không tồn tại")

        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(foreshadow.project_id, user_id, db)

        await foreshadow_service.delete_foreshadow(db, foreshadow_id)

        return {"message": "Xóa manh mối ẩn thành công", "id": foreshadow_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Xóa manh mối ẩn thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Xóa manh mối ẩn thất bại: {str(e)}")


@router.post("/{foreshadow_id}/plant", response_model=ForeshadowResponse)
async def plant_foreshadow(
    foreshadow_id: str,
    data: PlantForeshadowRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Đánh dấu manh mối ẩn đã được gieo

    Chuyển trạng thái manh mối ẩn từ pending sang planted, ghi lại chương gieo
    """
    try:
        foreshadow = await foreshadow_service.get_foreshadow(db, foreshadow_id)

        if not foreshadow:
            raise HTTPException(status_code=404, detail="Manh mối ẩn không tồn tại")

        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(foreshadow.project_id, user_id, db)

        updated = await foreshadow_service.mark_as_planted(db, foreshadow_id, data)
        return updated.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Đánh dấu gieo manh mối ẩn thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Đánh dấu gieo manh mối ẩn thất bại: {str(e)}")


@router.post("/{foreshadow_id}/resolve", response_model=ForeshadowResponse)
async def resolve_foreshadow(
    foreshadow_id: str,
    data: ResolveForeshadowRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Đánh dấu manh mối ẩn đã được thu hồi

    Chuyển trạng thái manh mối ẩn sang resolved hoặc partially_resolved
    """
    try:
        foreshadow = await foreshadow_service.get_foreshadow(db, foreshadow_id)

        if not foreshadow:
            raise HTTPException(status_code=404, detail="Manh mối ẩn không tồn tại")

        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(foreshadow.project_id, user_id, db)

        updated = await foreshadow_service.mark_as_resolved(db, foreshadow_id, data)
        return updated.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Đánh dấu thu hồi manh mối ẩn thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Đánh dấu thu hồi manh mối ẩn thất bại: {str(e)}")


@router.post("/{foreshadow_id}/abandon", response_model=ForeshadowResponse)
async def abandon_foreshadow(
    foreshadow_id: str,
    request: Request,
    reason: Optional[str] = Query(None, description="Lý do loại bỏ"),
    db: AsyncSession = Depends(get_db)
):
    """
    Đánh dấu manh mối ẩn đã bị loại bỏ

    Quyết định không sử dụng manh mối ẩn này nữa
    """
    try:
        foreshadow = await foreshadow_service.get_foreshadow(db, foreshadow_id)

        if not foreshadow:
            raise HTTPException(status_code=404, detail="Manh mối ẩn không tồn tại")

        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(foreshadow.project_id, user_id, db)

        updated = await foreshadow_service.mark_as_abandoned(db, foreshadow_id, reason)
        return updated.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Đánh dấu loại bỏ manh mối ẩn thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Đánh dấu loại bỏ manh mối ẩn thất bại: {str(e)}")


@router.post("/projects/{project_id}/sync-from-analysis", response_model=SyncFromAnalysisResponse)
async def sync_foreshadows_from_analysis(
    project_id: str,
    data: SyncFromAnalysisRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Đồng bộ manh mối ẩn từ kết quả phân tích

    Trích xuất thông tin manh mối ẩn từ kết quả phân tích chương, đồng bộ vào bảng quản lý manh mối ẩn
    """
    try:
        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(project_id, user_id, db)

        result = await foreshadow_service.sync_from_analysis(db, project_id, data)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Đồng bộ manh mối ẩn thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Đồng bộ manh mối ẩn thất bại: {str(e)}")
