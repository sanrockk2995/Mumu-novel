"""Module hàm dùng chung API

Chứa các hàm và công cụ dùng chung giữa các module API.
"""
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.models.project import Project
from app.logger import get_logger

logger = get_logger(__name__)


async def verify_project_access(
    project_id: str, 
    user_id: Optional[str], 
    db: AsyncSession
) -> Project:
    """
    Xác minh người dùng có quyền truy cập dự án đã chỉ định hay không
    
    Hàm xác minh quyền truy cập dự án thống nhất, đảm bảo:
    1. Người dùng đã đăng nhập
    2. Dự án tồn tại
    3. Người dùng có quyền truy cập dự án đó
    
    Args:
        project_id: ID dự án
        user_id: ID người dùng (lấy từ request.state.user_id)
        db: Phiên làm việc database
        
    Returns:
        Project: Trả về đối tượng dự án sau khi xác minh thành công
        
    Raises:
        HTTPException: 
            - 401: Người dùng chưa đăng nhập
            - 404: Dự án không tồn tại hoặc người dùng không có quyền truy cập
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        logger.warning(f"Truy cập dự án bị từ chối: project_id={project_id}, user_id={user_id}")
        raise HTTPException(status_code=404, detail="Dự án không tồn tại hoặc không có quyền truy cập")
    
    return project


def get_user_id(request: Request) -> Optional[str]:
    """
    Lấy ID người dùng từ request
    
    Đây là hàm tiện ích để trích xuất user_id từ request.state.
    
    Args:
        request: Đối tượng request của FastAPI
        
    Returns:
        ID người dùng, nếu chưa đăng nhập thì trả về None
    """
    return getattr(request.state, 'user_id', None)


async def verify_project_access_from_request(
    project_id: str,
    request: Request,
    db: AsyncSession
) -> Project:
    """
    Xác minh quyền truy cập dự án từ request (hàm tiện ích)
    
    Kết hợp get_user_id và verify_project_access để đơn giản hóa việc gọi.
    
    Args:
        project_id: ID dự án
        request: Đối tượng request của FastAPI
        db: Phiên làm việc database
        
    Returns:
        Project: Trả về đối tượng dự án sau khi xác minh thành công
        
    Raises:
        HTTPException: 401/404
        
    Usage:
        project = await verify_project_access_from_request(project_id, request, db)
    """
    user_id = get_user_id(request)
    return await verify_project_access(project_id, user_id, db)
