"""
API quản trị viên - chức năng quản lý người dùng
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import hashlib
import secrets
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.user_manager import user_manager
from app.user_password import password_manager
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Quản trị viên"])


# ==================== Model yêu cầu/phản hồi ====================

class CreateUserRequest(BaseModel):
    """Yêu cầu tạo người dùng"""
    username: str = Field(..., min_length=3, max_length=20, description="Tên đăng nhập")
    display_name: str = Field(..., min_length=2, max_length=50, description="Tên hiển thị")
    password: Optional[str] = Field(None, min_length=6, description="Mật khẩu ban đầu, để trống sẽ tự động tạo")
    avatar_url: Optional[str] = Field(None, description="URL ảnh đại diện")
    trust_level: int = Field(0, ge=0, le=9, description="Cấp độ tin cậy")
    is_admin: bool = Field(False, description="Có phải quản trị viên không")


class UpdateUserRequest(BaseModel):
    """Yêu cầu cập nhật người dùng"""
    display_name: Optional[str] = Field(None, min_length=2, max_length=50)
    avatar_url: Optional[str] = None
    trust_level: Optional[int] = Field(None, ge=-1, le=9)
    is_admin: Optional[bool] = Field(None, description="Có phải quản trị viên không")


class ToggleStatusRequest(BaseModel):
    """Yêu cầu chuyển đổi trạng thái người dùng"""
    is_active: bool = Field(..., description="true=bật, false=tắt")


class ResetPasswordRequest(BaseModel):
    """Yêu cầu đặt lại mật khẩu"""
    new_password: Optional[str] = Field(None, min_length=6, description="Mật khẩu mới, để trống sẽ tạo mật khẩu tạm thời")


class UserResponse(BaseModel):
    """Phản hồi thông tin người dùng"""
    user_id: str
    username: str
    display_name: str
    avatar_url: Optional[str]
    trust_level: int
    is_admin: bool
    is_active: bool
    linuxdo_id: str
    created_at: str
    last_login: Optional[str]


class CreateUserResponse(BaseModel):
    """Phản hồi tạo người dùng"""
    success: bool
    message: str
    user: dict
    default_password: Optional[str] = None


# ==================== Dependency kiểm tra quyền ====================

async def check_admin(request: Request) -> User:
    """Kiểm tra quyền quản trị viên"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Cần quyền quản trị viên")
    
    return user


# ==================== Endpoint API ====================

@router.get("/users")
async def get_users(
    admin: User = Depends(check_admin),
    db: AsyncSession = Depends(get_db)
):
    """Lấy danh sách người dùng (chỉ quản trị viên)"""
    try:
        all_users = await user_manager.get_all_users()
        
        users_data = []
        for user in all_users:
            # user_manager trả về đối tượng Pydantic User, chuyển thẳng thành dict
            user_dict = user.model_dump()
            user_dict["is_active"] = user.trust_level != -1
            users_data.append(user_dict)
        
        logger.info(f"Quản trị viên {admin.user_id} lấy danh sách người dùng, tổng cộng {len(users_data)} người dùng")
        
        return {
            "total": len(users_data),
            "users": users_data
        }
    except Exception as e:
        logger.error(f"Lấy danh sách người dùng thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lấy danh sách người dùng thất bại: {str(e)}")


@router.post("/users")
async def create_user(
    data: CreateUserRequest,
    admin: User = Depends(check_admin),
    db: AsyncSession = Depends(get_db)
):
    """Thêm người dùng (chỉ quản trị viên)"""
    try:
        # Kiểm tra tên đăng nhập đã tồn tại chưa
        all_users = await user_manager.get_all_users()
        for user in all_users:
            if user.username == data.username:
                raise HTTPException(status_code=409, detail="Tên đăng nhập đã tồn tại")
        
        # Tạo ID người dùng
        user_id = f"admin_created_{hashlib.md5(data.username.encode()).hexdigest()[:16]}"
        
        # Tạo người dùng
        new_user = await user_manager.create_or_update_from_linuxdo(
            linuxdo_id=user_id,
            username=data.username,
            display_name=data.display_name,
            avatar_url=data.avatar_url,
            trust_level=data.trust_level
        )
        
        # Thiết lập cờ quản trị viên
        if data.is_admin:
            # Cập nhật trực tiếp trường is_admin trong database
            async with await user_manager._get_session() as session:
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                db_user = result.scalar_one_or_none()
                if db_user:
                    db_user.is_admin = True
                    await session.commit()
                    new_user.is_admin = True
        
        # Đặt mật khẩu
        actual_password = await password_manager.set_password(
            user_id=new_user.user_id,
            username=data.username,
            password=data.password
        )
        
        # Settings sẽ được tự động tạo khi lần đầu truy cập trang cài đặt (khởi tạo trễ)
        
        logger.info(f"Quản trị viên {admin.user_id} đã tạo người dùng mới {new_user.user_id} ({data.username})")
        
        return CreateUserResponse(
            success=True,
            message="Tạo người dùng thành công",
            user=new_user.model_dump(),
            default_password=actual_password if not data.password else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tạo người dùng thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Tạo người dùng thất bại: {str(e)}")


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    data: UpdateUserRequest,
    admin: User = Depends(check_admin),
    db: AsyncSession = Depends(get_db)
):
    """Chỉnh sửa thông tin người dùng (chỉ quản trị viên)"""
    try:
        # Lấy người dùng mục tiêu
        target_user = await user_manager.get_user(user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
        
        # Cập nhật thông tin người dùng
        async with await user_manager._get_session() as session:
            result = await session.execute(
                select(User).where(User.user_id == user_id)
            )
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
            
            # Cập nhật các trường
            if data.display_name is not None:
                db_user.display_name = data.display_name
            if data.avatar_url is not None:
                db_user.avatar_url = data.avatar_url
            if data.trust_level is not None:
                db_user.trust_level = data.trust_level
            if data.is_admin is not None:
                # Kiểm tra có phải quản trị viên cuối cùng không
                if db_user.is_admin and not data.is_admin:
                    all_users = await user_manager.get_all_users()
                    admin_count = sum(1 for u in all_users if u.is_admin)
                    if admin_count <= 1:
                        raise HTTPException(status_code=400, detail="Không thể hủy quyền của quản trị viên cuối cùng")
                db_user.is_admin = data.is_admin
            
            await session.commit()
            await session.refresh(db_user)
        
        logger.info(f"Quản trị viên {admin.user_id} đã cập nhật thông tin của người dùng {user_id}")
        
        updated_user = await user_manager.get_user(user_id)
        user_dict = updated_user.model_dump()
        user_dict["is_active"] = updated_user.trust_level != -1
        
        return {
            "success": True,
            "message": "Cập nhật thông tin người dùng thành công",
            "user": user_dict
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cập nhật người dùng thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cập nhật người dùng thất bại: {str(e)}")


@router.post("/users/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: str,
    data: ToggleStatusRequest,
    admin: User = Depends(check_admin),
    db: AsyncSession = Depends(get_db)
):
    """Chuyển đổi trạng thái người dùng (bật/tắt) (chỉ quản trị viên)"""
    try:
        # Không được vô hiệu hóa chính mình
        if user_id == admin.user_id:
            raise HTTPException(status_code=400, detail="Không thể vô hiệu hóa tài khoản của chính mình")
        
        # Lấy người dùng mục tiêu
        target_user = await user_manager.get_user(user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
        
        # Cập nhật trạng thái
        async with await user_manager._get_session() as session:
            result = await session.execute(
                select(User).where(User.user_id == user_id)
            )
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
            
            if data.is_active:
                # Bật người dùng: khôi phục trust_level về 0 (hoặc giá trị trước đó)
                db_user.trust_level = 0
            else:
                # Vô hiệu hóa người dùng: đặt trust_level thành -1
                db_user.trust_level = -1
            
            await session.commit()
        
        status_text = "Bật" if data.is_active else "Vô hiệu hóa"
        logger.info(f"Quản trị viên {admin.user_id} đã {status_text} người dùng {user_id}")
        
        return {
            "success": True,
            "message": f"Đã {status_text} người dùng",
            "is_active": data.is_active
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chuyển đổi trạng thái người dùng thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chuyển đổi trạng thái người dùng thất bại: {str(e)}")


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    data: ResetPasswordRequest,
    admin: User = Depends(check_admin),
    db: AsyncSession = Depends(get_db)
):
    """Đặt lại mật khẩu người dùng (chỉ quản trị viên)"""
    try:
        # Lấy người dùng mục tiêu
        target_user = await user_manager.get_user(user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
        
        # Đặt lại mật khẩu
        generated_password = data.new_password
        if not generated_password:
            generated_password = secrets.token_urlsafe(12)

        await password_manager.set_password(
            user_id=user_id,
            username=target_user.username,
            password=generated_password
        )
        
        logger.info(f"Quản trị viên {admin.user_id} đã đặt lại mật khẩu của người dùng {user_id}")
        
        return {
            "success": True,
            "message": "Đặt lại mật khẩu thành công",
            "temporary_password": generated_password if not data.new_password else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Đặt lại mật khẩu thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Đặt lại mật khẩu thất bại: {str(e)}")


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: User = Depends(check_admin),
    db: AsyncSession = Depends(get_db)
):
    """Xóa người dùng (chỉ quản trị viên, dùng cẩn thận)"""
    try:
        # Không được xóa chính mình
        if user_id == admin.user_id:
            raise HTTPException(status_code=400, detail="Không thể xóa tài khoản của chính mình")
        
        # Lấy người dùng mục tiêu
        target_user = await user_manager.get_user(user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
        
        # Kiểm tra có phải quản trị viên cuối cùng không
        if target_user.is_admin:
            all_users = await user_manager.get_all_users()
            admin_count = sum(1 for u in all_users if u.is_admin)
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="Không thể xóa tài khoản quản trị viên cuối cùng")
        
        # Xóa người dùng (bao gồm bản ghi mật khẩu)
        async with await user_manager._get_session() as session:
            # Xóa bản ghi người dùng
            result = await session.execute(
                select(User).where(User.user_id == user_id)
            )
            db_user = result.scalar_one_or_none()
            if db_user:
                await session.delete(db_user)
            
            # Xóa bản ghi mật khẩu
            from app.models.user import UserPassword
            result = await session.execute(
                select(UserPassword).where(UserPassword.user_id == user_id)
            )
            pwd_record = result.scalar_one_or_none()
            if pwd_record:
                await session.delete(pwd_record)
            
            await session.commit()
        
        logger.warning(f"Quản trị viên {admin.user_id} đã xóa người dùng {user_id}")
        
        return {
            "success": True,
            "message": "Đã xóa người dùng"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Xóa người dùng thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Xóa người dùng thất bại: {str(e)}")
